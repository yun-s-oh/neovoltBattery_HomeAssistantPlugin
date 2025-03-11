"""Validation logic for Byte-Watt data."""
import math
import logging
import time
import statistics
from typing import Dict, Any, Tuple, Optional, List, Deque
from collections import deque

_LOGGER = logging.getLogger(__name__)


class NeuralPhysicsValidator:
    """
    Neural Physics validator combining adaptive physics constraints with 
    pattern recognition for robust battery data validation.
    """
    
    def __init__(self):
        # Physics constraints (universal)
        self.max_soc_change_rate = 5.0  # % per minute (physical limit)
        self.extreme_soc_jump = 15.0    # % absolute (hard physical limit)
        self.min_power_threshold = 300  # Watts - ignore balance for low values
        self.max_battery_power = 8000   # Maximum inverter capacity
        self.max_time_gap = 600         # Maximum time gap in seconds
        
        # Pattern recognition components
        self.soc_history = deque(maxlen=30)  # SOC values
        self.timestamps = deque(maxlen=30)   # Corresponding timestamps
        self.power_history = {
            'battery': deque(maxlen=30),  # Battery power
            'solar': deque(maxlen=30),    # Solar power
            'grid': deque(maxlen=30),     # Grid power
            'load': deque(maxlen=30)      # Load power
        }
        
        # Pattern weighting
        self.weights = {
            'soc_physics': 1.0,         # SOC change rate (most reliable)
            'energy_conservation': 0.7,  # Power balance
            'bms_constraints': 0.9,      # BMS prevents charging at 100%, etc.
            'power_limits': 0.6,         # Power within system limits
            'pattern_consistency': 0.4   # Consistent patterns over time
        }
        
        # Tracking
        self.last_known_good = None  # Last valid entry
        self.last_known_good_timestamp = 0
        self.last_soc_direction = 0  # -1=decreasing, 0=stable, 1=increasing
        self.confidence_scores = []  # Track validation confidence
        
        # Debug information
        self.validation_details = {}
    
    def extract_data(self, data: Dict[str, Any], timestamp: float) -> Dict[str, Any]:
        """Extract relevant data from entry for validation."""
        if not data:
            return {}
        
        # Extract key metrics
        extracted_data = {
            'timestamp': timestamp,
            'soc': data.get('soc'),
            'battery_power': data.get('pbat', 0),
            'solar_power': sum(data.get(f'ppv{i}', 0) for i in range(1, 5)),
            'grid_power': sum(data.get(f'pmeter_l{i}', 0) for i in range(1, 4)) + data.get('pmeter_dc', 0),
            'load_power': sum(data.get(f'preal_l{i}', 0) for i in range(1, 4)),
            'raw': data  # Keep full raw data for reference
        }
        
        return extracted_data
    
    def update_history(self, data: Dict[str, Any]) -> None:
        """Update historical data used for pattern recognition."""
        if not data or 'soc' not in data:
            return
            
        # Update histories
        self.soc_history.append(data['soc'])
        self.timestamps.append(data['timestamp'])
        self.power_history['battery'].append(data['battery_power'])
        self.power_history['solar'].append(data['solar_power'])
        self.power_history['grid'].append(data['grid_power'])
        self.power_history['load'].append(data['load_power'])
        
        # Update SOC direction
        if len(self.soc_history) >= 2:
            diff = self.soc_history[-1] - self.soc_history[-2]
            if diff > 0.5:
                self.last_soc_direction = 1  # Increasing
            elif diff < -0.5:
                self.last_soc_direction = -1  # Decreasing
            else:
                self.last_soc_direction = 0  # Stable
    
    def validate_physics_soc(self, data: Dict[str, Any], prev_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate SOC changes based on physical constraints of battery chemistry.
        Returns a score (0-1) and reason if invalid.
        """
        if not data or not prev_data or 'soc' not in data or 'soc' not in prev_data:
            return 1.0, ""
        
        # Calculate time difference and SOC change
        time_diff_seconds = data['timestamp'] - prev_data['timestamp']
        
        # Skip validation for large time gaps or invalid timestamps
        if time_diff_seconds <= 0 or time_diff_seconds > self.max_time_gap:
            return 1.0, ""
        
        time_diff_minutes = time_diff_seconds / 60.0
        soc_change = abs(data['soc'] - prev_data['soc'])
        
        # Hard physical limit - extreme jumps are impossible regardless of time
        if soc_change > self.extreme_soc_jump:
            return 0.0, f"Extreme SOC jump: {soc_change:.1f}% (max allowed: {self.extreme_soc_jump:.1f}%)"
        
        # Calculate SOC change rate
        soc_rate = soc_change / time_diff_minutes
        
        # Calculate adaptive threshold based on SOC level
        # Batteries charge/discharge more slowly at extremes (0% or 100%)
        avg_soc = (data['soc'] + prev_data['soc']) / 2
        adaptive_max_rate = self.max_soc_change_rate
        
        if avg_soc < 10 or avg_soc > 90:
            # 40% reduction in extreme SOC ranges
            adaptive_max_rate *= 0.6
        elif avg_soc < 20 or avg_soc > 80:
            # 20% reduction in near-extreme ranges
            adaptive_max_rate *= 0.8
        
        # Compute a score based on how close to the limit we are
        if soc_rate <= adaptive_max_rate * 0.4:  # Well within limits
            return 1.0, ""
        elif soc_rate <= adaptive_max_rate * 0.7:  # Getting closer to limits
            return 0.8, ""
        elif soc_rate <= adaptive_max_rate:  # Near the limit but acceptable
            return 0.6, ""
        elif soc_rate <= adaptive_max_rate * 1.2:  # Slightly above limit
            return 0.2, f"High SOC change rate: {soc_rate:.1f}%/min (limit: {adaptive_max_rate:.1f}%/min)"
        else:  # Well above limit
            return 0.0, f"Extreme SOC change rate: {soc_rate:.1f}%/min (limit: {adaptive_max_rate:.1f}%/min)"
    
    def validate_energy_conservation(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate power measurements using energy conservation principles.
        Power in = Power out (within tolerance).
        """
        if not data:
            return 1.0, ""
        
        # Calculate total power flow
        power_in = data['solar_power'] + data['grid_power'] + data['battery_power']
        power_out = data['load_power']
        max_power = max(abs(data['solar_power']), abs(data['grid_power']), 
                       abs(data['battery_power']), abs(data['load_power']))
        
        # Skip validation for very low power (measurement noise dominates)
        if max_power < self.min_power_threshold:
            return 1.0, ""
        
        # Calculate imbalance
        power_imbalance = abs(power_in - power_out)
        imbalance_ratio = power_imbalance / max_power
        
        # Adaptive tolerance based on power levels
        # Higher power levels have more measurement error
        adaptive_tolerance = 0.3  # Base tolerance (30%)
        if max_power > 5000:
            adaptive_tolerance = 0.35  # 35% for high power
        elif max_power < 1000:
            adaptive_tolerance = 0.25  # 25% for low power
        
        # Score based on imbalance ratio
        if imbalance_ratio <= adaptive_tolerance * 0.5:  # Very good balance
            return 1.0, ""
        elif imbalance_ratio <= adaptive_tolerance * 0.8:  # Good balance
            return 0.9, ""
        elif imbalance_ratio <= adaptive_tolerance:  # Acceptable balance
            return 0.7, ""
        elif imbalance_ratio <= adaptive_tolerance * 1.5:  # Poor balance
            return 0.3, f"Energy imbalance: {imbalance_ratio:.2f} (limit: {adaptive_tolerance:.2f})"
        else:  # Severe imbalance
            return 0.0, f"Severe energy imbalance: {imbalance_ratio:.2f} (limit: {adaptive_tolerance:.2f})"
    
    def validate_bms_constraints(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate that data follows Battery Management System constraints.
        - Cannot charge at 100% SOC
        - Cannot discharge at 0% SOC
        """
        if not data or 'soc' not in data:
            return 1.0, ""
        
        soc = data['soc']
        battery_power = data['battery_power']
        
        # 100% SOC with charging - physically impossible due to BMS
        if soc >= 99.5 and battery_power > 100:
            return 0.0, f"BMS violation: Charging ({battery_power:.1f}W) at {soc:.1f}% SOC"
        
        # 0% SOC with discharging - physically impossible due to BMS
        if soc <= 0.5 and battery_power < -100:
            return 0.0, f"BMS violation: Discharging ({battery_power:.1f}W) at {soc:.1f}% SOC"
        
        # SOC direction vs battery power direction check (only apply with significant power)
        if len(self.soc_history) >= 3 and abs(battery_power) > 500:
            # Calculate SOC trend over last few readings
            recent_soc_changes = [self.soc_history[i] - self.soc_history[i-1] 
                                 for i in range(1, min(5, len(self.soc_history)))]
            avg_soc_change = sum(recent_soc_changes) / len(recent_soc_changes)
            
            # Charging but SOC decreasing significantly
            if battery_power > 500 and avg_soc_change < -0.5:
                return 0.2, f"BMS violation: SOC decreasing while charging ({battery_power:.1f}W)"
                
            # Discharging but SOC increasing significantly
            if battery_power < -500 and avg_soc_change > 0.5:
                return 0.2, f"BMS violation: SOC increasing while discharging ({battery_power:.1f}W)"
        
        return 1.0, ""
    
    def validate_power_limits(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate that power values stay within physical system limits.
        """
        if not data:
            return 1.0, ""
        
        # Battery power check
        if abs(data['battery_power']) > self.max_battery_power * 1.1:  # 10% margin
            return 0.0, f"Power violation: Battery power {abs(data['battery_power']):.1f}W exceeds limit {self.max_battery_power:.1f}W"
        
        # Solar power should never be negative
        if data['solar_power'] < -50:  # Small tolerance for measurement noise
            return 0.0, f"Power violation: Negative solar power {data['solar_power']:.1f}W"
        
        # Check for unrealistically high solar power
        if data['solar_power'] > self.max_battery_power * 1.5:  # 50% higher than inverter
            return 0.2, f"Power violation: Unrealistic solar power {data['solar_power']:.1f}W"
        
        return 1.0, ""
    
    def validate_pattern_consistency(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate that the entry follows expected patterns based on history.
        This uses a neural-like approach to detect anomalies by comparing
        to established patterns.
        """
        if not data or len(self.soc_history) < 5:
            return 1.0, ""
        
        # 1. Statistical anomaly detection for SOC
        soc_values = list(self.soc_history)
        try:
            mean_soc = statistics.mean(soc_values)
            stdev_soc = statistics.stdev(soc_values) if len(soc_values) > 1 else 0
            
            # If standard deviation is very small, use a minimum value
            stdev_soc = max(stdev_soc, 0.5)
            
            # Calculate z-score for current SOC
            z_score = abs(data['soc'] - mean_soc) / stdev_soc
            
            # Extremely high z-score indicates statistical anomaly
            if z_score > 3.0:
                return 0.2, f"Pattern anomaly: SOC {data['soc']:.1f}% (z-score: {z_score:.1f})"
        except:
            # In case of statistical errors, skip this check
            pass
        
        # 2. Pattern recognition for operation mode consistency
        # Analyze recent power distribution patterns
        if len(self.power_history['battery']) >= 5:
            # Calculate current power distribution
            total_power = (abs(data['solar_power']) + abs(data['grid_power']) + 
                          abs(data['battery_power']) + abs(data['load_power']))
            
            if total_power > 1000:  # Only check with significant power
                # Detect solar mode
                if data['solar_power'] > 2000 and data['solar_power'] / total_power > 0.4:
                    solar_mode = True
                    
                    # Check if battery behavior is consistent with solar mode
                    if data['battery_power'] < -1000 and data['solar_power'] > 3000:
                        return 0.4, f"Pattern anomaly: Battery discharging with high solar production"
                
                # Detect grid-dominant mode
                if abs(data['grid_power']) > 2000 and abs(data['grid_power']) / total_power > 0.5:
                    grid_mode = True
                    
                    # Check battery behavior in grid mode
                    recent_grid = list(self.power_history['grid'])[-3:]
                    avg_recent_grid = sum(recent_grid) / len(recent_grid)
                    
                    # Sudden battery power reversal in grid mode
                    if avg_recent_grid > 2000 and data['battery_power'] < -2000:
                        return 0.5, f"Pattern anomaly: Battery discharge with grid import"
        
        return 1.0, ""
    
    def calculate_combined_score(self, scores: Dict[str, Tuple[float, str]]) -> Tuple[float, str]:
        """
        Calculate a weighted score from individual validation components.
        Returns the final score and the primary reason if validation failed.
        """
        total_weight = 0
        weighted_score = 0
        failure_reasons = []
        
        for key, (score, reason) in scores.items():
            weight = self.weights.get(key, 0.5)
            weighted_score += score * weight
            total_weight += weight
            
            # Collect failure reasons (scores below 0.5)
            if score < 0.5 and reason:
                failure_reasons.append(reason)
        
        # Calculate final normalized score
        final_score = weighted_score / total_weight if total_weight > 0 else 0.5
        
        # Return the most important reason if validation failed
        if failure_reasons and final_score < 0.5:
            return final_score, failure_reasons[0]
        
        return final_score, ""
    
    def validate(self, data: Dict[str, Any], timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        Validate data using the neural physics approach.
        
        Args:
            data: The data to validate
            timestamp: Unix timestamp of the data
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        # Extract relevant data
        extracted_data = self.extract_data(data, timestamp)
        if not extracted_data:
            return False, "Invalid data or missing required fields"
        
        # First entry is always valid (no prior reference)
        prev_data = None
        if self.last_known_good_timestamp > 0:
            prev_data = self.extract_data(self.last_known_good, self.last_known_good_timestamp)
        else:
            self.last_known_good = data
            self.last_known_good_timestamp = timestamp
            self.update_history(extracted_data)
            return True, None
        
        # Run all validation components
        validation_scores = {
            'soc_physics': self.validate_physics_soc(extracted_data, prev_data),
            'energy_conservation': self.validate_energy_conservation(extracted_data),
            'bms_constraints': self.validate_bms_constraints(extracted_data),
            'power_limits': self.validate_power_limits(extracted_data),
            'pattern_consistency': self.validate_pattern_consistency(extracted_data)
        }
        
        # Store validation details for debugging
        self.validation_details = {k: v[0] for k, v in validation_scores.items()}
        
        # Calculate final score
        final_score, reason = self.calculate_combined_score(validation_scores)
        
        # Apply neural-inspired confidence tracking
        self.confidence_scores.append(final_score)
        if len(self.confidence_scores) > 10:
            self.confidence_scores.pop(0)
        
        # Adaptive threshold with hysteresis
        # Higher threshold for first transition to valid after invalid
        validation_threshold = 0.5
        
        # If recent history was mostly invalid, require higher confidence to switch to valid
        if len(self.confidence_scores) >= 3 and sum(1 for s in self.confidence_scores if s < 0.5) >= 2:
            validation_threshold = 0.65
        
        # Final decision
        is_valid = final_score >= validation_threshold
        
        # Update tracking for valid entries
        if is_valid:
            self.last_known_good = data
            self.last_known_good_timestamp = timestamp
            self.update_history(extracted_data)
        
        return is_valid, reason if not is_valid else None


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
                 soc_history_size: int = 20,  # Size of SOC history deque for median filtering
                 use_neural_validator: bool = True):  # Whether to use the neural validator
        
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
        
        # Neural validator integration
        self.use_neural_validator = use_neural_validator
        self.neural_validator = NeuralPhysicsValidator() if use_neural_validator else None
        
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
        Enhanced validation of API response data with robust neural physics validation.
        
        Args:
            data: The API response data
            timestamp: Unix timestamp of the response
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        if not data:
            return False, "No data in response"
        
        # If neural validator is enabled, use it as the primary validation method
        if self.use_neural_validator and self.neural_validator:
            neural_valid, neural_reason = self.neural_validator.validate(data, timestamp)
            
            # Apply hysteresis to neural validation results
            final_valid, final_reason = self.validate_with_hysteresis(neural_valid, neural_reason)
            
            # If neural validator rejects data, log the reason
            if not final_valid and final_reason:
                _LOGGER.warning(f"Neural validator rejected data: {final_reason}")
            
            # For valid data, still update our traditional tracking variables for backup
            if neural_valid:
                # Update our own state tracking for legacy compatibility
                current_soc = data.get('soc', 0)
                self.update_soc_tracking(current_soc, timestamp)
                self.determine_power_state(data)
                
                # Store the data point for window-based validations
                self.valid_data_points.append({
                    'timestamp': timestamp,
                    'data': data
                })
                
                # Keep window size limited
                if len(self.valid_data_points) > self.window_size * 3:
                    self.valid_data_points.pop(0)
                
                # Update tracking variables
                self.last_valid_soc = current_soc
                self.last_valid_soc_timestamp = timestamp
                self.last_checked_timestamp = timestamp
                self.suspected_spike = False
            
            return final_valid, final_reason
        
        # If neural validator is disabled, fall back to traditional validation
        
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