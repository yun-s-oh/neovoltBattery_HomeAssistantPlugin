"""Validation logic for Byte-Watt data."""
import math
import logging
import time
from typing import Dict, Any, Tuple, Optional, List, Deque
from collections import deque

_LOGGER = logging.getLogger(__name__)


class EnergyDataValidator:
    """Enhanced class for validating energy data from the Byte-Watt API."""
    
    def __init__(self, 
                 max_soc_change_rate: float = 3.0,  # % per minute - decreased to catch more spikes
                 power_balance_tolerance: float = 1.0,  # Increased tolerance for power imbalance
                 anomaly_std_dev_threshold: float = 3.0,  # Flag if > 3.0 standard deviations from mean
                 window_size: int = 10,  # Increased window size for better statistical analysis
                 max_power_rating: float = 8000,  # Maximum inverter power (W)
                 battery_capacity: float = 10000,  # Battery capacity (Wh)
                 power_contingency: float = 1.5,  # Contingency factor for power limits
                 min_power_threshold: float = 500,  # Minimum power threshold for balance checks
                 max_time_gap: float = 600,  # Maximum time gap in seconds to consider for validation
                 ema_alpha: float = 0.2,  # Reduced alpha for more stable EMA
                 max_allowed_soc_jump: float = 15.0,  # Maximum allowed SOC jump in any case
                 soc_history_size: int = 20):  # Size of SOC history deque for median filtering
        
        # Core parameters
        self.max_soc_change_rate = max_soc_change_rate
        self.power_balance_tolerance = power_balance_tolerance
        self.anomaly_std_dev_threshold = anomaly_std_dev_threshold
        self.window_size = window_size
        self.max_power_rating = max_power_rating
        self.battery_capacity = battery_capacity
        self.power_contingency = power_contingency
        self.min_power_threshold = min_power_threshold
        self.max_time_gap = max_time_gap
        self.ema_alpha = ema_alpha
        
        # State tracking
        self.valid_data_points = []
        self.soc_ema = None  # Exponential moving average for SOC
        self.last_validation_result = True  # For hysteresis
        self.last_checked_timestamp = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.max_allowed_soc_jump = max_allowed_soc_jump
        self.soc_history_size = soc_history_size
        
        # More robust SOC tracking
        self.soc_history = deque(maxlen=soc_history_size)
        self.soc_median = None
        self.last_valid_soc = None
        self.last_valid_soc_timestamp = 0
        self.soc_trend = 0  # Direction: 1=up, -1=down, 0=stable
        self.suspected_spike = False
        
        # Power state tracking
        self.is_charging = False
        self.is_discharging = False
        self.battery_power_history = deque(maxlen=soc_history_size)
        
    def get_median(self, values: List[float]) -> float:
        """Calculate median value from a list of numbers."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n == 0:
            return 0
        if n % 2 == 1:
            return sorted_values[n // 2]
        else:
            return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    
    def update_exponential_moving_average(self, new_value: float, current_ema: Optional[float] = None) -> float:
        """Update the exponential moving average with a new value."""
        if current_ema is None:
            return new_value
        return self.ema_alpha * new_value + (1 - self.ema_alpha) * current_ema
    
    def determine_power_state(self, data: Dict[str, Any]) -> None:
        """Determine if the battery is charging, discharging, or idle."""
        battery_power = data.get('pbat', 0)
        
        # Add to history
        self.battery_power_history.append(battery_power)
        
        # Update charging/discharging state
        if battery_power > 200:  # Positive = charging
            self.is_charging = True
            self.is_discharging = False
        elif battery_power < -200:  # Negative = discharging
            self.is_charging = False
            self.is_discharging = True
        else:  # Near zero = idle
            self.is_charging = False
            self.is_discharging = False
    
    def update_soc_tracking(self, soc: float, timestamp: float) -> None:
        """Update SOC tracking variables."""
        # Update SOC history
        self.soc_history.append(soc)
        
        # Calculate new median when we have enough data
        if len(self.soc_history) >= 3:
            self.soc_median = self.get_median(list(self.soc_history))
        else:
            self.soc_median = soc
        
        # Update SOC trend
        if self.last_valid_soc is not None:
            if soc > self.last_valid_soc + 0.5:
                self.soc_trend = 1  # Upward trend
            elif soc < self.last_valid_soc - 0.5:
                self.soc_trend = -1  # Downward trend
            else:
                self.soc_trend = 0  # Stable
    
    def is_soc_spike(self, current_soc: float, timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        Detect SOC spikes using multiple methods.
        
        Returns:
            (is_spike, reason_if_spike)
        """
        if self.last_valid_soc is None or self.last_valid_soc_timestamp == 0:
            # First data point, can't determine if it's a spike
            return False, None
        
        # Calculate time difference
        time_diff_seconds = timestamp - self.last_valid_soc_timestamp
        time_diff_minutes = time_diff_seconds / 60.0
        
        # Skip very old timestamps
        if time_diff_seconds <= 0 or time_diff_seconds > self.max_time_gap:
            return False, None
        
        # Calculate the change rate
        soc_change = current_soc - self.last_valid_soc
        soc_change_rate = abs(soc_change) / time_diff_minutes
        
        # 1. Hard ceiling on SOC jumps regardless of time
        if abs(soc_change) > self.max_allowed_soc_jump:
            return True, f"Extreme SOC jump: {abs(soc_change):.1f}% (max allowed: {self.max_allowed_soc_jump:.1f}%)"
        
        # 2. Check against rate of change limit
        adaptive_rate = self.calculate_adaptive_soc_change_rate(time_diff_minutes, current_soc)
        if soc_change_rate > adaptive_rate:
            return True, f"SOC change rate: {soc_change_rate:.1f}%/min (max: {adaptive_rate:.1f}%/min)"
        
        # 3. Check for changes contradicting battery power direction
        if len(self.battery_power_history) > 0:
            avg_power = sum(self.battery_power_history) / len(self.battery_power_history)
            
            # If battery is discharging (negative) but SOC increasing significantly
            if avg_power < -100 and soc_change > 2:
                return True, f"SOC increased by {soc_change:.1f}% while battery discharging ({avg_power:.1f}W)"
                
            # If battery is charging (positive) but SOC decreasing significantly
            if avg_power > 100 and soc_change < -2:
                return True, f"SOC decreased by {abs(soc_change):.1f}% while battery charging ({avg_power:.1f}W)"
        
        # 4. Check against median-based thresholds
        if self.soc_median is not None:
            median_diff = abs(current_soc - self.soc_median)
            
            # If greater than 10% from median, investigate
            if median_diff > 10:
                # Stricter checks for sudden large jumps from median
                if time_diff_minutes < 5 and median_diff > 15:
                    return True, f"Large deviation from median: {current_soc:.1f}% vs {self.soc_median:.1f}%"
        
        # 5. Check for rapid direction reversal
        if self.soc_trend != 0:
            current_trend = 1 if soc_change > 0 else (-1 if soc_change < 0 else 0)
            
            # If trend reversed with a large jump
            if current_trend != 0 and current_trend != self.soc_trend and abs(soc_change) > 5:
                return True, f"Suspicious trend reversal: {soc_change:.1f}% change"
        
        return False, None
    
    def calculate_adaptive_soc_change_rate(self, time_diff_minutes: float, soc: float) -> float:
        """Calculate an adaptive SOC change rate based on time gap and current SOC."""
        base_rate = self.max_soc_change_rate
        
        # For larger time gaps, be more lenient
        if time_diff_minutes > 5:
            base_rate *= 1.5
        
        # Adapt based on SOC level
        if soc < 20 or soc > 80:
            # Battery charges/discharges more slowly at extremes
            base_rate *= 0.8
            
        return base_rate
    
    def validate_with_hysteresis(self, is_valid: bool, reason: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Apply hysteresis to validation results to prevent oscillation."""
        # Increment success/failure counters
        if is_valid:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
        
        # Apply hysteresis
        if self.last_validation_result and not is_valid:
            # Was valid, now invalid - require 2 consecutive failures to flip
            if self.consecutive_failures >= 2:
                self.last_validation_result = False
                return False, reason
            else:
                return True, None
        elif not self.last_validation_result and is_valid:
            # Was invalid, now valid - require 2 consecutive successes to flip
            if self.consecutive_successes >= 2:
                self.last_validation_result = True
                return True, None
            else:
                return False, "Hysteresis - waiting for more consistent valid data"
        else:
            # No change in state
            self.last_validation_result = is_valid
            return is_valid, reason
    
    def is_valid_response(self, data: Dict[str, Any], timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        Enhanced validation of API response data with robust spike detection.
        
        Args:
            data: The API response data
            timestamp: Unix timestamp of the response
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        if not data:
            return False, "No data in response"
        
        # Extract key power values
        current_soc = data.get('soc', 0)
        load_power = data.get('preal_l1', 0)
        solar_power = (
            data.get('ppv1', 0) + 
            data.get('ppv2', 0) + 
            data.get('ppv3', 0) + 
            data.get('ppv4', 0)
        )
        battery_power = data.get('pbat', 0)
        grid_power = (
            data.get('pmeter_l1', 0) + 
            data.get('pmeter_l2', 0) + 
            data.get('pmeter_l3', 0) + 
            data.get('pmeter_dc', 0)
        )
        
        # Update power state for context-aware validation
        self.determine_power_state(data)
        
        # Step 1: Check for SOC spikes first - most important validation
        if self.last_valid_soc is not None:
            is_spike, spike_reason = self.is_soc_spike(current_soc, timestamp)
            if is_spike:
                _LOGGER.warning(f"SOC spike detected: {current_soc}% vs last valid {self.last_valid_soc}%. Reason: {spike_reason}")
                self.suspected_spike = True
                return self.validate_with_hysteresis(False, spike_reason)
        
        # Step 2: Update SOC tracking (EMA, median, etc.)
        self.update_soc_tracking(current_soc, timestamp)
        
        # Update SOC EMA (used for smoothing)
        if self.soc_ema is None:
            self.soc_ema = current_soc
        else:
            self.soc_ema = self.update_exponential_moving_average(current_soc, self.soc_ema)
        
        # Step 3: Statistical validation against historical data
        if len(self.soc_history) >= 5:
            # Calculate z-score relative to median (more robust than mean)
            soc_median = self.get_median(list(self.soc_history))
            abs_deviations = [abs(x - soc_median) for x in self.soc_history]
            mad = self.get_median(abs_deviations)
            
            # Use MAD for robust outlier detection, with minimum threshold
            effective_std = max(mad * 1.4826, 1.0)  # 1.4826 converts MAD to std-dev equivalent
            
            # Calculate z-score
            z_score = abs(current_soc - soc_median) / effective_std
            
            # If z-score is extremely high, reject the value
            if z_score > self.anomaly_std_dev_threshold:
                _LOGGER.warning(f"Statistical anomaly: SOC {current_soc:.1f}% vs median {soc_median:.1f}% (z-score: {z_score:.2f})")
                return self.validate_with_hysteresis(
                    False,
                    f"Statistical anomaly: z-score {z_score:.2f} > threshold {self.anomaly_std_dev_threshold}"
                )
        
        # Step 4: Power balance check (could indicate faulty readings)
        power_sum = solar_power + grid_power + battery_power
        power_balance = abs(power_sum - load_power)
        max_power = max(abs(solar_power), abs(grid_power), abs(battery_power), abs(load_power))
        
        # Skip balance checks for small power values
        if max_power > self.min_power_threshold:
            # Calculate adaptive tolerance based on power magnitude
            adaptive_tolerance = self.power_balance_tolerance
            if max_power > 3000:
                # For high power levels, be more lenient
                adaptive_tolerance *= 1.2
            
            # Reject only extreme imbalances now that we have better SOC validation
            if power_balance > 2 * adaptive_tolerance * max_power:
                return self.validate_with_hysteresis(
                    False, 
                    f"Severe power imbalance: {power_balance:.1f}W (ratio: {power_balance/max_power:.2f})"
                )
        
        # Step 5: Battery power limit check
        adjusted_max_power = self.max_power_rating * self.power_contingency
        
        # If we're in a known operating state, be more lenient
        if self.is_charging or self.is_discharging:
            adjusted_max_power *= 1.2
            
        if abs(battery_power) > adjusted_max_power:
            return self.validate_with_hysteresis(
                False, 
                f"Battery power ({abs(battery_power):.1f}W) exceeds limit ({adjusted_max_power:.1f}W)"
            )
        
        # All checks passed - store as valid data point
        self.valid_data_points.append({
            'timestamp': timestamp,
            'data': data
        })
        
        # Keep window size limited
        if len(self.valid_data_points) > self.window_size * 3:
            self.valid_data_points.pop(0)
        
        # Update tracking variables for next validation
        self.last_valid_soc = current_soc
        self.last_valid_soc_timestamp = timestamp
        self.last_checked_timestamp = timestamp
        self.suspected_spike = False
        
        # Return valid result with hysteresis
        return self.validate_with_hysteresis(True, None)