"""Validation logic for Byte-Watt data."""
import math
import logging
import time
import statistics
from typing import Dict, Any, Tuple, Optional, List, Deque, Set
from collections import deque

_LOGGER = logging.getLogger(__name__)


class BalancedAdvancedValidator:
    """
    Balanced Advanced validator for ByteWatt Battery Data.
    
    This validator provides highly accurate detection of anomalies while maintaining
    good data availability. It employs a multi-tier validation system with separate 
    trusted and accepted data classifications, and handles recovery points appropriately.
    """
    
    def __init__(self):
        # Core parameters - balanced thresholds
        self.max_soc_change_rate = 4.0  # % per minute (less restrictive)
        self.extreme_soc_jump = 10.0    # % absolute (moderate threshold)
        self.min_power_threshold = 200  # Watts - ignore balance for low values
        self.max_battery_power = 8000   # Maximum inverter capacity
        self.max_time_gap = 600         # Maximum time gap in seconds
        
        # History tracking
        self.window_size = 30           # Moderate window size
        self.soc_history = deque(maxlen=self.window_size)
        self.timestamps = deque(maxlen=self.window_size)
        self.power_history = {
            'battery': deque(maxlen=self.window_size),
            'solar': deque(maxlen=self.window_size),
            'grid': deque(maxlen=self.window_size),
            'load': deque(maxlen=self.window_size)
        }
        
        # Derived metrics
        self.soc_delta_history = deque(maxlen=self.window_size)
        self.soc_rate_history = deque(maxlen=self.window_size)
        
        # Multi-tier validation data storage
        self.trusted_data_points = []   # Strictly validated data (high confidence)
        self.accepted_data_points = []  # Accepted data (passes baseline validation)
        self.context_data_points = []   # All data points for contextual awareness (even invalid ones)
        self.recovery_points = []       # Track recovery points separately
        
        # Mode detection and tracking
        self.current_mode = "unknown"
        self.mode_history = deque(maxlen=8)
        self.mode_transition_time = 0
        
        # Context tracking for spike pattern detection
        self.all_soc_values = deque(maxlen=10)  # All SOC values seen, even invalid ones
        self.all_soc_deltas = deque(maxlen=10)  # All SOC deltas, even from invalid entries
        
        # Statistical tracking
        self.median_soc = None
        self.mad_soc = 0.5
        self.soc_ema = None
        
        # Validation state
        self.last_known_good = None
        self.last_known_good_timestamp = 0
        self.validation_details = {}
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Component weights - prioritize physics over statistics
        self.weights = {
            'physics_critical': 1.0,    # Critical physics violations
            'physics_standard': 0.8,    # Standard physics constraints
            'statistics': 0.6,          # Statistical outlier detection
            'mode_consistency': 0.5,    # Mode consistency checks
            'power_balance': 0.4,       # Power flow balance
        }
        
        # Internal tracking for current entry
        self._current_entry = None
        
        # Recovery point tracking
        self.is_recovery_point = False
        self.recovery_pattern = ""
        self.suspected_spike = False
    
    def extract_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant data from entry for validation."""
        if not entry:
            return {}
            
        raw_data = entry
        timestamp = int(time.time())
        
        # Extract key metrics
        data = {
            'timestamp': timestamp,
            'soc': raw_data.get('soc'),
            'battery_power': raw_data.get('pbat', 0),
            'solar_power': sum(raw_data.get(f'ppv{i}', 0) for i in range(1, 5)),
            'grid_power': sum(raw_data.get(f'pmeter_l{i}', 0) for i in range(1, 4)) + raw_data.get('pmeter_dc', 0),
            'load_power': sum(raw_data.get(f'preal_l{i}', 0) for i in range(1, 4)),
            'raw': raw_data  # Keep full raw data for reference
        }
        
        return data
    
    def update_statistics(self):
        """Update statistical measures based on history."""
        if len(self.soc_history) < 3:
            return
        
        # Update SOC median and MAD
        soc_values = list(self.soc_history)
        self.median_soc = statistics.median(soc_values)
        
        # Calculate Median Absolute Deviation (more robust than standard deviation)
        absolute_deviations = [abs(x - self.median_soc) for x in soc_values]
        self.mad_soc = max(statistics.median(absolute_deviations), 0.5)  # Ensure minimum MAD
    
    def update_history(self, data: Dict[str, Any]) -> None:
        """Update historical data for validation context."""
        if not data or 'soc' not in data:
            return
            
        # Update core histories
        self.soc_history.append(data['soc'])
        self.timestamps.append(data['timestamp'])
        self.power_history['battery'].append(data['battery_power'])
        self.power_history['solar'].append(data['solar_power'])
        self.power_history['grid'].append(data['grid_power'])
        self.power_history['load'].append(data['load_power'])
        
        # Calculate and store SOC delta and rate
        if len(self.soc_history) >= 2 and len(self.timestamps) >= 2:
            soc_delta = self.soc_history[-1] - self.soc_history[-2]
            self.soc_delta_history.append(soc_delta)
            
            time_diff = (self.timestamps[-1] - self.timestamps[-2]) / 60.0  # minutes
            if time_diff > 0:
                rate = soc_delta / time_diff
                self.soc_rate_history.append(rate)
        
        # Update EMA with adaptive alpha
        if self.soc_ema is None:
            self.soc_ema = data['soc']
        else:
            alpha = 0.2  # Standard alpha
            self.soc_ema = alpha * data['soc'] + (1 - alpha) * self.soc_ema
        
        # Update system mode
        self.detect_system_mode(data)
        
        # Update overall statistics
        self.update_statistics()
    
    def detect_system_mode(self, data: Dict[str, Any]) -> None:
        """Detect the current system operating mode based on power flows."""
        battery = data['battery_power']
        solar = data['solar_power']
        grid = data['grid_power']
        load = data['load_power']
        
        # Determine primary mode based on power flows
        if solar > 1000:  # Significant solar production
            if battery < -500:  # Charging (negative = charging)
                mode = "solar_charging"
            elif battery > 500:  # Discharging
                mode = "solar_discharge"
            elif grid < -500:  # Exporting to grid
                mode = "solar_export"
            else:
                mode = "solar_direct"
        elif battery < -500:  # Charging from grid
            mode = "grid_charging"
        elif battery > 500:  # Discharging to load
            mode = "battery_discharge"
        elif grid > 500:  # Grid import
            mode = "grid_import"
        elif grid < -500:  # Grid export
            mode = "grid_export"
        else:  # Low power state
            mode = "idle"
        
        # If mode changed, record transition time
        if mode != self.current_mode:
            self.mode_transition_time = data['timestamp']
            
        # Update mode
        self.current_mode = mode
        self.mode_history.append(mode)
    
    def validate_physics_critical(self, data: Dict[str, Any], prev_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate against critical physics violations that should never occur.
        Returns (score, reason_if_invalid).
        """
        if not data or not prev_data or 'soc' not in data or 'soc' not in prev_data:
            return 1.0, ""
        
        # Calculate time difference and SOC change
        time_diff_seconds = data['timestamp'] - prev_data['timestamp']
        if time_diff_seconds <= 0 or time_diff_seconds > self.max_time_gap:
            return 1.0, ""
            
        time_diff_minutes = time_diff_seconds / 60.0
        current_soc = data['soc']
        prev_soc = prev_data['soc']
        soc_change = abs(current_soc - prev_soc)
        soc_direction = 1 if current_soc > prev_soc else (-1 if current_soc < prev_soc else 0)
        
        # Check for extreme SOC jumps (physically impossible)
        extreme_limit = 20.0  # Very conservative - only flag extremely obvious problems
        if soc_change > extreme_limit:
            return 0.0, f"Extreme SOC jump: {soc_change:.1f}% (hard limit: {extreme_limit:.1f}%)"
        
        # Check if this entry is a recovery from a large jump
        # This catches the scenario where SOC jumps from A → B and then back to approximately A
        if len(self.soc_history) >= 2:
            # If we have at least 2 previous readings, check for recovery pattern
            if abs(current_soc - self.soc_history[-2]) < 5.0 and abs(self.soc_history[-1] - self.soc_history[-2]) > 15.0:
                # This is a recovery pattern: A → B → (back to ~A)
                # Instead of rejecting, flag it as a recovery point but allow validation to continue
                entry = getattr(self, '_current_entry', None)
                if entry is not None:
                    # Track internally but don't reject
                    self.is_recovery_point = True
                    self.recovery_pattern = f"{self.soc_history[-2]:.1f}% → {self.soc_history[-1]:.1f}% → {current_soc:.1f}%"
        
        # Check for severe physical contradictions with significant power
        # This catches cases with strong battery power and SOC moving the wrong way
        avg_battery_power = (data['battery_power'] + prev_data.get('battery_power', 0)) / 2
        if abs(avg_battery_power) > 2000:  # Only with very strong power
            expected_soc_direction = 1 if avg_battery_power < 0 else -1  # neg power = charging = SOC increase
            
            # Strong power and SOC is clearly moving the wrong way
            if soc_direction != 0 and soc_direction != expected_soc_direction and soc_change > 5.0:
                power_str = "charging" if avg_battery_power < 0 else "discharging"
                soc_str = "increasing" if soc_direction > 0 else "decreasing"
                return 0.0, f"Critical physics violation: SOC {soc_str} by {soc_change:.1f}% while {power_str} at {abs(avg_battery_power):.0f}W"
        
        # Check for physics violation with any power level
        if data['battery_power'] < -300 and prev_data.get('battery_power', 0) < -300:  # Both charging
            if soc_direction < 0 and soc_change > 10.0:  # Large decrease while charging
                return 0.0, f"Physics violation: SOC decreased by {soc_change:.1f}% while charging"
                
        if data['battery_power'] > 300 and prev_data.get('battery_power', 0) > 300:  # Both discharging
            if soc_direction > 0 and soc_change > 10.0:  # Large increase while discharging
                return 0.0, f"Physics violation: SOC increased by {soc_change:.1f}% while discharging"
        
        # BMS critical violations
        # 100% SOC with charging - impossible due to BMS
        if current_soc >= 99.9 and data['battery_power'] < -500:
            return 0.0, f"BMS violation: Charging at 100% SOC"
            
        # 0% SOC with discharging - impossible due to BMS
        if current_soc <= 0.1 and data['battery_power'] > 500:
            return 0.0, f"BMS violation: Discharging at 0% SOC"
            
        # All critical checks passed
        return 1.0, ""
    
    def validate_physics_standard(self, data: Dict[str, Any], prev_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate against standard physics constraints.
        Less restrictive than critical validation.
        """
        if not data or not prev_data or 'soc' not in data or 'soc' not in prev_data:
            return 1.0, ""
        
        # Calculate time difference and SOC change
        time_diff_seconds = data['timestamp'] - prev_data['timestamp']
        if time_diff_seconds <= 0 or time_diff_seconds > self.max_time_gap:
            return 1.0, ""
            
        time_diff_minutes = time_diff_seconds / 60.0
        current_soc = data['soc']
        prev_soc = prev_data['soc']
        soc_change = abs(current_soc - prev_soc)
        
        # Check SOC jumps against our normal threshold
        if soc_change > self.extreme_soc_jump:
            return 0.0, f"Large SOC jump: {soc_change:.1f}% (limit: {self.extreme_soc_jump:.1f}%)"

        # Detect the recovery from a large spike specifically
        # Looking for "recovery jumps" where large SOC changes occur in short time
        # Especially those that cancel a previous large change
        if len(self.soc_delta_history) > 0:
            prev_delta = self.soc_delta_history[-1]  # Last SOC delta
            current_delta = current_soc - prev_soc  # Current SOC delta
            
            # If we have a large change in the opposite direction of a previous large change
            if abs(prev_delta) > 15.0 and abs(current_delta) > 15.0 and (prev_delta * current_delta < 0):
                # This is a typical recovery pattern - flag but don't reject
                # Track internally but don't reject
                self.is_recovery_point = True
                self.recovery_pattern = f"Delta pattern: {prev_delta:+.1f}% followed by {current_delta:+.1f}%"
        
        # Common spike pattern: jumps to/from exact values like 0%, 100%
        exact_values = [0, 100]
        if (current_soc in exact_values or prev_soc in exact_values) and soc_change > 8.0:
            return 0.3, f"Suspicious SOC change to/from {current_soc:.0f}%"
            
        # Calculate SOC change rate
        soc_rate = soc_change / time_diff_minutes
        
        # Calculate adaptive threshold based on SOC level and power
        avg_soc = (current_soc + prev_soc) / 2
        adaptive_max_rate = self.max_soc_change_rate
        
        # Adjust threshold based on SOC range
        if avg_soc < 10 or avg_soc > 90:
            adaptive_max_rate *= 0.7  # 30% reduction in extreme ranges
        elif avg_soc < 20 or avg_soc > 80:
            adaptive_max_rate *= 0.85  # 15% reduction in near-extreme ranges
            
        # Adjust based on power level - higher power = higher allowed rate
        avg_power = abs((data['battery_power'] + prev_data.get('battery_power', 0)) / 2)
        if avg_power > 2000:  # High power allows higher rate
            adaptive_max_rate *= 1.3
            
        # During mode transitions, allow higher rate
        if data['timestamp'] - self.mode_transition_time < 180:  # Within 3 minutes of mode change
            adaptive_max_rate *= 1.3
            
        # Compute score based on how close to the limit we are
        if soc_rate <= adaptive_max_rate * 0.5:  # Well within limits
            return 1.0, ""
        elif soc_rate <= adaptive_max_rate * 0.8:  # Getting closer to limits
            return 0.9, ""
        elif soc_rate <= adaptive_max_rate:  # Near the limit but acceptable
            return 0.7, ""
        elif soc_rate <= adaptive_max_rate * 1.3:  # Slightly above limit, but could be valid
            return 0.4, f"High SOC change rate: {soc_rate:.1f}%/min (limit: {adaptive_max_rate:.1f}%/min)"
        else:  # Well above limit
            return 0.1, f"Very high SOC change rate: {soc_rate:.1f}%/min (limit: {adaptive_max_rate:.1f}%/min)"
    
    def validate_statistics(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate using statistical methods based on historical patterns.
        """
        if not data or self.median_soc is None or len(self.soc_history) < 5:
            return 1.0, ""
        
        # Calculate robust z-score using MAD
        # 0.6745 is a scaling factor for normal distribution equivalence
        z_score = 0.6745 * abs(data['soc'] - self.median_soc) / self.mad_soc
        
        # Use less restrictive threshold than before
        threshold = 6.0  # Much higher z-score threshold
        
        if z_score > threshold:
            return 0.0, f"Statistical outlier: SOC {data['soc']:.1f}% (z-score: {z_score:.1f})"
        elif z_score > threshold * 0.7:
            return 0.4, f"Potential outlier: SOC {data['soc']:.1f}% (z-score: {z_score:.1f})"
        
        # Also check for bipolar pattern (rapid up-down or down-up)
        if len(self.soc_delta_history) >= 2:
            last_deltas = list(self.soc_delta_history)[-2:]
            
            # Look for sign change with significant magnitude in both directions
            if (last_deltas[0] > 5.0 and last_deltas[1] < -5.0) or \
               (last_deltas[0] < -5.0 and last_deltas[1] > 5.0):
                swing = abs(last_deltas[0]) + abs(last_deltas[1])
                return 0.1, f"Bipolar SOC pattern detected: {swing:.1f}% total swing"
        
        return 1.0, ""
    
    def validate_mode_consistency(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate consistency with current operating mode.
        """
        if not data or len(self.mode_history) < 3:
            return 1.0, ""
        
        # Skip during mode transitions
        if data['timestamp'] - self.mode_transition_time < 180:  # Within 3 minutes of mode change
            return 1.0, ""
        
        # Get current dominant mode
        mode_counts = {}
        for mode in self.mode_history:
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        if not mode_counts:
            return 1.0, ""
            
        dominant_mode = max(mode_counts.items(), key=lambda x: x[1])[0]
        
        # Skip if mode is not stable
        if mode_counts[dominant_mode] < 0.6 * len(self.mode_history):
            return 1.0, ""
        
        # Only check obvious contradictions
        if dominant_mode == "solar_charging" and data['solar_power'] < 200:
            return 0.3, f"Mode inconsistency: solar_charging mode with no solar power"
            
        if dominant_mode == "battery_discharge" and data['battery_power'] < 0:
            return 0.3, f"Mode inconsistency: battery_discharge mode but battery is charging"
        
        return 1.0, ""
    
    def validate_power_balance(self, data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Validate power measurements using energy conservation principles.
        Less restrictive than before to allow more data through.
        """
        if not data:
            return 1.0, ""
        
        # Power flow validation
        solar_power = data['solar_power']
        battery_power = data['battery_power']
        grid_power = data['grid_power']
        load_power = data['load_power']
        
        # Skip validation for very low power
        max_power = max(abs(solar_power), abs(grid_power), abs(battery_power), abs(load_power))
        if max_power < self.min_power_threshold:
            return 1.0, ""
        
        # Calculate power flows with direction normalization
        # Power in = solar + grid import + battery discharge 
        power_in = solar_power
        if grid_power > 0:  # Grid import
            power_in += grid_power
        if battery_power > 0:  # Battery discharging
            power_in += battery_power
            
        # Power out = load + grid export + battery charge
        power_out = abs(load_power)  # Load is always consumption (positive)
        if grid_power < 0:  # Grid export
            power_out += abs(grid_power)
        if battery_power < 0:  # Battery charging
            power_out += abs(battery_power)
        
        # Calculate imbalance (should ideally be 0)
        power_imbalance = abs(power_in - power_out)
        imbalance_ratio = power_imbalance / max(max_power, 1)  # Avoid division by 0
        
        # Very generous tolerance - only flag extreme cases
        adaptive_tolerance = 0.6  # 60% tolerance
        if max_power > 5000:
            adaptive_tolerance = 0.7  # 70% for high power
        
        # More tolerant scoring
        if imbalance_ratio <= adaptive_tolerance * 0.5:
            return 1.0, ""
        elif imbalance_ratio <= adaptive_tolerance:
            return 0.8, ""
        elif imbalance_ratio <= adaptive_tolerance * 1.5:
            return 0.5, f"Power imbalance: {imbalance_ratio:.2f} (limit: {adaptive_tolerance:.2f})"
        else:
            return 0.1, f"Severe power imbalance: {imbalance_ratio:.2f} (limit: {adaptive_tolerance:.2f})"
    
    def calculate_combined_score(self, scores: Dict[str, Tuple[float, str]]) -> Tuple[float, bool, float, str]:
        """
        Calculate combined score with multi-tier classification.
        Returns:
            (overall_score, is_valid, trust_score, primary_reason)
            
        The validator uses two thresholds:
        - Validity threshold: Lower bar for accepted data
        - Trust threshold: Higher bar for trusted data
        """
        total_weight = 0
        weighted_score = 0
        reasons = []
        
        # Critical checks are non-negotiable - fail immediately on critical physics violations
        if 'physics_critical' in scores:
            critical_score, critical_reason = scores['physics_critical']
            if critical_score == 0.0:  # Critical failure
                return 0.0, False, 0.0, critical_reason
        
        # Calculate weighted score for other components
        for key, (score, reason) in scores.items():
            weight = self.weights.get(key, 0.5)
            weighted_score += score * weight
            total_weight += weight
            
            # Collect failure reasons
            if score < 0.5 and reason:
                reasons.append(reason)
        
        # Calculate final normalized score
        final_score = weighted_score / total_weight if total_weight > 0 else 0.5
        
        # Calculate trust score - must be high confidence to be trusted
        trust_score = final_score
        
        # Determine validity based on moderate threshold
        is_valid = final_score >= 0.4  # More permissive validity threshold
        
        # Return the primary reason if invalid
        primary_reason = reasons[0] if reasons and not is_valid else ""
        
        return final_score, is_valid, trust_score, primary_reason
    
    def apply_hysteresis(self, is_valid: bool, score: float) -> bool:
        """
        Apply hysteresis to validation results to prevent oscillation.
        """
        # Be more lenient after multiple failures to prevent getting stuck
        if not is_valid and self.consecutive_failures >= 3:
            threshold_reduction = min(0.05 * self.consecutive_failures, 0.15)  # Up to 0.15 reduction
            return score >= (0.4 - threshold_reduction)
        
        # Be slightly more strict after many successes
        if is_valid and self.consecutive_successes >= 5:
            return score >= 0.45
            
        return is_valid
    
    def update_context_tracking(self, data: Dict[str, Any]) -> None:
        """
        Update context tracking with all entries, even invalid ones.
        This helps detect spike patterns across both valid and invalid entries.
        """
        if not data or 'soc' not in data:
            return
            
        # Add to context data points
        self.context_data_points.append({
            'timestamp': data['timestamp'],
            'data': data
        })
        
        # Track all SOC values for pattern detection
        current_soc = data['soc']
        self.all_soc_values.append(current_soc)
        
        # Calculate SOC deltas across all entries
        if len(self.all_soc_values) >= 2:
            delta = current_soc - self.all_soc_values[-2]
            self.all_soc_deltas.append(delta)
            
        # Check for recovery pattern in context
        if len(self.all_soc_values) >= 3 and len(self.all_soc_deltas) >= 2:
            # Get last 3 SOC values
            soc_1, soc_2, soc_3 = list(self.all_soc_values)[-3:]
            
            # Check for A → B → A pattern (where A and B differ significantly)
            if abs(soc_1 - soc_3) < 5.0 and abs(soc_2 - soc_1) > 15.0:
                # This is a spike and recover pattern
                self.suspected_spike = True
    
    def is_valid_response(self, entry: Dict[str, Any], timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        Validate an API response data.
        
        Args:
            entry: The data to validate
            timestamp: Unix timestamp of the data
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        # Convert to interface compatible with validate_entry
        return self.validate_entry(entry)
    
    def validate_entry(self, entry: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a single entry using the balanced approach.
        
        Args:
            entry: The entry to validate
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        # Store current entry for reference in validation functions
        self._current_entry = entry
        
        # Reset recovery point tracking for this entry
        self.is_recovery_point = False
        self.recovery_pattern = ""
        
        # Extract relevant data
        data = self.extract_data(entry)
        if not data:
            return False, "Invalid API response or missing data"
        
        # First entry is always valid (no prior reference)
        if self.last_known_good is None:
            self.last_known_good = entry
            self.last_known_good_timestamp = data['timestamp']
            self.update_history(data)
            
            # Add to all tracking lists
            self.accepted_data_points.append({
                'timestamp': data['timestamp'],
                'data': data
            })
            self.trusted_data_points.append({
                'timestamp': data['timestamp'],
                'data': data
            })
            
            # Update context tracking
            self.update_context_tracking(data)
            
            return True, None
        
        # Always update context tracking before validation
        # This gives us awareness of previous entries even if they were invalid
        self.update_context_tracking(data)
        
        # Get previous valid data for comparison
        prev_data = self.extract_data(self.last_known_good)
        
        # Run validation components
        scores = {
            'physics_critical': self.validate_physics_critical(data, prev_data),
            'physics_standard': self.validate_physics_standard(data, prev_data),
            'statistics': self.validate_statistics(data),
            'mode_consistency': self.validate_mode_consistency(data),
            'power_balance': self.validate_power_balance(data)
        }
        
        # Store component scores for debugging
        self.validation_details = {k: v[0] for k, v in scores.items()}
        
        # Calculate final score with multi-tier classification
        score, is_valid, trust_score, reason = self.calculate_combined_score(scores)
        
        # Apply hysteresis for stability
        is_valid = self.apply_hysteresis(is_valid, score)
        
        # Update state tracking
        if is_valid:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            
            # Update tracking for valid entries
            self.last_known_good = entry
            self.last_known_good_timestamp = data['timestamp']
            self.update_history(data)
            
            # Add to accepted data points
            data_point = {
                'timestamp': data['timestamp'],
                'data': data
            }
            
            # Store recovery point information internally but still mark as valid
            if self.is_recovery_point:
                # Add to recovery points list for tracking
                recovery_data_point = data_point.copy()
                recovery_data_point['recovery_pattern'] = self.recovery_pattern
                self.recovery_points.append(recovery_data_point)
                
                # Log the recovery point (but don't reject it)
                _LOGGER.info(f"Detected SOC recovery pattern: {self.recovery_pattern}")
                
            self.accepted_data_points.append(data_point)
            
            # If high trust score, add to trusted data points
            # Recovery points aren't automatically trusted, even if they pass validation
            if trust_score >= 0.7 and not self.is_recovery_point:  
                self.trusted_data_points.append(data_point.copy())
        else:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # For data that almost makes the cut, still update some tracking
            if score >= 0.3:  # Near-miss data
                self.detect_system_mode(data)
        
        # Clear current entry reference to avoid memory leaks
        self._current_entry = None
        
        return is_valid, reason if not is_valid else None


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