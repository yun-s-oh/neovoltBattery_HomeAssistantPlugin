"""Validation logic for Byte-Watt data."""
import math
import logging
from typing import Dict, Any, Tuple, Optional, List

_LOGGER = logging.getLogger(__name__)


class EnergyDataValidator:
    """Class for validating energy data from the Byte-Watt API."""
    
    def __init__(self, 
                 max_soc_change_rate: float = 1.6,  # % per minute (doubled from theoretical ~0.8%)
                 power_balance_tolerance: float = 0.25,  # 25% tolerance for power imbalance
                 anomaly_std_dev_threshold: float = 3.0,  # Flag if > 3 standard deviations from mean
                 window_size: int = 5,  # Number of data points to use for statistical analysis
                 max_power_rating: float = 5000,  # Maximum inverter power (W)
                 battery_capacity: float = 10000,  # Battery capacity (Wh)
                 power_contingency: float = 1.5):  # Contingency factor for power limits
        
        self.max_soc_change_rate = max_soc_change_rate
        self.power_balance_tolerance = power_balance_tolerance
        self.anomaly_std_dev_threshold = anomaly_std_dev_threshold
        self.window_size = window_size
        self.max_power_rating = max_power_rating
        self.battery_capacity = battery_capacity
        self.power_contingency = power_contingency
        self.valid_data_points = []
        
    def is_valid_response(self, data: Dict[str, Any], timestamp: float) -> Tuple[bool, Optional[str]]:
        """
        Check if an API response is valid based on multiple criteria.
        
        Args:
            data: The API response data
            timestamp: Unix timestamp of the response
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        if not data:
            return False, "No data in response"
            
        # 1. Check for sudden SOC jumps
        if self.valid_data_points:
            last_valid_data = self.valid_data_points[-1]
            last_valid_timestamp = last_valid_data.get('timestamp', 0)
            time_diff_minutes = (timestamp - last_valid_timestamp) / 60.0
            
            if time_diff_minutes > 0 and time_diff_minutes < 10:  # Only check if readings are < 10 minutes apart
                last_soc = last_valid_data.get('data', {}).get('soc', 0)
                current_soc = data.get('soc', 0)
                
                theoretical_max_change = (self.max_power_rating / self.battery_capacity) * 100 * time_diff_minutes
                
                # Apply our contingency factor to account for real-world variations
                adjusted_max_change = theoretical_max_change * self.power_contingency
                
                # Use the more conservative of our fixed rate or the calculated rate
                effective_max_change = min(self.max_soc_change_rate * time_diff_minutes, adjusted_max_change)
                
                if abs(current_soc - last_soc) > effective_max_change:
                    return False, f"Impossible SOC change: {abs(current_soc - last_soc):.1f}% in {time_diff_minutes:.1f} min (max allowed: {effective_max_change:.1f}%)"
        
        # 2. Check for power balance violations
        load_power = data.get('preal_l1', 0)
        solar_power = data.get('ppv1', 0) + data.get('ppv2', 0) + data.get('ppv3', 0) + data.get('ppv4', 0)
        battery_power = data.get('pbat', 0)
        grid_power = data.get('pmeter_l1', 0) + data.get('pmeter_l2', 0) + data.get('pmeter_l3', 0) + data.get('pmeter_dc', 0)
        
        # Skip small power values to avoid false positives
        if max(abs(load_power), abs(solar_power), abs(battery_power), abs(grid_power)) > 1000:
            power_balance = abs((solar_power + grid_power + battery_power) - load_power)
            max_power = max(abs(solar_power), abs(grid_power), abs(battery_power), abs(load_power))
            
            if power_balance > self.power_balance_tolerance * max_power:
                return False, f"Power balance violation: {power_balance:.1f}W imbalance"
                
        # Also check for battery power exceeding inverter rating
        if abs(battery_power) > self.max_power_rating * self.power_contingency:
            return False, f"Battery power ({abs(battery_power):.1f}W) exceeds adjusted inverter capability ({self.max_power_rating * self.power_contingency:.1f}W)"
        
        # 3. Apply statistical anomaly detection if we have enough data points
        if len(self.valid_data_points) >= self.window_size:
            window = self.valid_data_points[-self.window_size:]
            
            # Check SOC anomalies
            soc_values = [entry.get('data', {}).get('soc', 0) for entry in window]
            soc_mean = sum(soc_values) / len(soc_values)
            soc_std = math.sqrt(sum((x - soc_mean) ** 2 for x in soc_values) / len(soc_values))
            
            # Avoid division by zero and tiny standard deviations
            if soc_std > 1.0:
                soc_z_score = abs(data.get('soc', 0) - soc_mean) / soc_std
                if soc_z_score > self.anomaly_std_dev_threshold:
                    return False, f"SOC statistical anomaly: z-score={soc_z_score:.1f}"
        
        # If all checks pass, add to valid data points and consider the response valid
        self.valid_data_points.append({
            'timestamp': timestamp,
            'data': data
        })
        
        # Keep window size limited
        if len(self.valid_data_points) > self.window_size * 2:
            self.valid_data_points.pop(0)
            
        return True, None