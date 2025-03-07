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
                 max_soc_change_rate: float = 5.0,  # % per minute - increased based on data analysis
                 power_balance_tolerance: float = 1.0,  # Increased tolerance for power imbalance
                 anomaly_std_dev_threshold: float = 3.5,  # Flag if > 3.5 standard deviations from mean
                 window_size: int = 5,  # Number of data points to use for statistical analysis
                 max_power_rating: float = 8000,  # Maximum inverter power (W) - increased based on data
                 battery_capacity: float = 10000,  # Battery capacity (Wh)
                 power_contingency: float = 1.5,  # Contingency factor for power limits
                 min_power_threshold: float = 500,  # Minimum power threshold for balance checks
                 max_time_gap: float = 600,  # Maximum time gap in seconds to consider for validation
                 ema_alpha: float = 0.3):  # Exponential moving average weight factor
        
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
        
        # Power state tracking
        self.is_charging = False
        self.is_discharging = False
        
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
        Enhanced validation of API response data with adaptive thresholds and filtering.
        
        Args:
            data: The API response data
            timestamp: Unix timestamp of the response
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        if not data:
            return False, "No data in response"
        
        # Update power state for context-aware validation
        self.determine_power_state(data)
        
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
        
        # Update SOC EMA
        if self.soc_ema is None:
            self.soc_ema = current_soc
        else:
            self.soc_ema = self.update_exponential_moving_average(current_soc, self.soc_ema)
        
        # 1. Check for sudden SOC jumps with adaptive thresholds
        if self.valid_data_points:
            last_valid_data = self.valid_data_points[-1]
            last_valid_timestamp = last_valid_data.get('timestamp', 0)
            time_diff_seconds = timestamp - last_valid_timestamp
            time_diff_minutes = time_diff_seconds / 60.0
            
            # Only validate if time difference is within reasonable bounds
            if 0 < time_diff_seconds < self.max_time_gap:
                last_soc = last_valid_data.get('data', {}).get('soc', 0)
                
                # Calculate theoretical and adaptive change limits
                theoretical_max_change = (self.max_power_rating / self.battery_capacity) * 100 * time_diff_minutes
                adaptive_rate = self.calculate_adaptive_soc_change_rate(time_diff_minutes, current_soc)
                
                # Apply contingency factor to theoretical limit
                adjusted_max_change = theoretical_max_change * self.power_contingency
                
                # Use the more conservative of the adaptive rate or theoretical limit
                effective_max_change = min(adaptive_rate * time_diff_minutes, adjusted_max_change)
                
                # Add a minimum threshold to avoid rejecting small changes
                effective_max_change = max(effective_max_change, 1.0)
                
                # Check against SOC EMA for larger time gaps
                comparison_soc = self.soc_ema if time_diff_minutes > 5 else last_soc
                
                if abs(current_soc - comparison_soc) > effective_max_change:
                    return self.validate_with_hysteresis(
                        False, 
                        f"SOC change: {abs(current_soc - comparison_soc):.1f}% in {time_diff_minutes:.1f}min (max: {effective_max_change:.1f}%)"
                    )
        
        # 2. Improved power balance check with adaptive tolerance
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
            
            if power_balance > adaptive_tolerance * max_power:
                # For extreme imbalances, always reject
                if power_balance > 2 * adaptive_tolerance * max_power:
                    return self.validate_with_hysteresis(
                        False, 
                        f"Severe power imbalance: {power_balance:.1f}W (ratio: {power_balance/max_power:.2f})"
                    )
                
                # Check if we have previous power values for median filtering
                if len(self.valid_data_points) >= 3:
                    # Get recent power values
                    recent_entries = self.valid_data_points[-3:]
                    recent_balances = []
                    
                    for entry in recent_entries:
                        entry_data = entry.get('data', {})
                        entry_load = entry_data.get('preal_l1', 0)
                        entry_solar = (
                            entry_data.get('ppv1', 0) + 
                            entry_data.get('ppv2', 0) + 
                            entry_data.get('ppv3', 0) + 
                            entry_data.get('ppv4', 0)
                        )
                        entry_battery = entry_data.get('pbat', 0)
                        entry_grid = (
                            entry_data.get('pmeter_l1', 0) + 
                            entry_data.get('pmeter_l2', 0) + 
                            entry_data.get('pmeter_l3', 0) + 
                            entry_data.get('pmeter_dc', 0)
                        )
                        
                        entry_sum = entry_solar + entry_grid + entry_battery
                        entry_balance = abs(entry_sum - entry_load)
                        entry_max_power = max(abs(entry_solar), abs(entry_grid), abs(entry_battery), abs(entry_load))
                        
                        if entry_max_power > 0:
                            recent_balances.append(entry_balance / entry_max_power)
                    
                    # If median of recent imbalances is also high, reject
                    if recent_balances and self.get_median(recent_balances) > adaptive_tolerance:
                        return self.validate_with_hysteresis(
                            False, 
                            f"Consistent power imbalance: {power_balance:.1f}W (ratio: {power_balance/max_power:.2f})"
                        )
        
        # 3. Improved battery power limit check with context awareness
        adjusted_max_power = self.max_power_rating * self.power_contingency
        
        # If we're in a known operating state, be more lenient
        if self.is_charging or self.is_discharging:
            adjusted_max_power *= 1.2
            
        if abs(battery_power) > adjusted_max_power:
            return self.validate_with_hysteresis(
                False, 
                f"Battery power ({abs(battery_power):.1f}W) exceeds limit ({adjusted_max_power:.1f}W)"
            )
        
        # 4. Statistical anomaly detection with improved robustness
        if len(self.valid_data_points) >= self.window_size:
            # Use adaptive window size based on data quality
            window_size = min(self.window_size, len(self.valid_data_points))
            window = self.valid_data_points[-window_size:]
            
            # Extract SOC values and filter out None values
            soc_values = [entry.get('data', {}).get('soc', 0) for entry in window]
            soc_values = [v for v in soc_values if v is not None]
            
            if soc_values:
                # Calculate mean, median, and std dev
                soc_mean = sum(soc_values) / len(soc_values)
                soc_median = self.get_median(soc_values)
                
                # Use median for more robust anomaly detection
                soc_diff = abs(current_soc - soc_median)
                
                # Calculate MAD (Median Absolute Deviation) for robust std dev equivalent
                abs_deviations = [abs(x - soc_median) for x in soc_values]
                mad = self.get_median(abs_deviations)
                
                # Standard deviation fallback if MAD is too small
                soc_std = math.sqrt(sum((x - soc_mean) ** 2 for x in soc_values) / len(soc_values))
                
                # Use MAD for robust outlier detection, with minimum threshold
                effective_std = max(mad * 1.4826, 1.0)  # 1.4826 converts MAD to std-dev equivalent
                
                # Only apply statistical check for larger windows to avoid false positives
                if len(soc_values) >= 4 and effective_std > 0.5:
                    z_score = soc_diff / effective_std
                    
                    # Use higher threshold for anomalies
                    if z_score > self.anomaly_std_dev_threshold:
                        return self.validate_with_hysteresis(
                            False, 
                            f"SOC statistical anomaly: {current_soc:.1f}% vs median {soc_median:.1f}% (z: {z_score:.1f})"
                        )
        
        # If all checks pass, add to valid data points and consider the response valid
        self.valid_data_points.append({
            'timestamp': timestamp,
            'data': data
        })
        
        # Keep window size limited
        if len(self.valid_data_points) > self.window_size * 3:
            self.valid_data_points.pop(0)
        
        # Update last check time
        self.last_checked_timestamp = timestamp
        
        # Return valid result with hysteresis
        return self.validate_with_hysteresis(True, None)