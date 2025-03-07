"""Client for interacting with the Byte-Watt API."""
import logging
from typing import Dict, Any, Optional, List

from .api.client import ByteWattAPIClient
from .api.battery_data import BatteryDataAPI
from .api.settings import BatterySettingsAPI
from .models import SoCData, GridData, BatterySettings

_LOGGER = logging.getLogger(__name__)


class ByteWattClient:
    """Client for interacting with the Byte-Watt API with comprehensive validation."""
    
    def __init__(self, username: str, password: str):
        """Initialize with login credentials."""
        self.username = username
        self.password = password
        self.api_client = ByteWattAPIClient(username, password)
        self.battery_data_api = BatteryDataAPI(self.api_client)
        self.settings_api = BatterySettingsAPI(self.api_client)
        
        # Make the settings cache accessible for the sensor module
        self._settings_cache = self.settings_api._settings_cache
    
    def initialize(self):
        """Initialize or re-initialize the client."""
        # Re-create API client with fresh session
        self.api_client = ByteWattAPIClient(self.username, self.password)
        
        # Re-initialize API modules with the new client
        self.battery_data_api = BatteryDataAPI(self.api_client)
        self.settings_api = BatterySettingsAPI(self.api_client)
        
        # Re-link settings cache
        self._settings_cache = self.settings_api._settings_cache
    
    def ensure_authenticated(self) -> bool:
        """Ensure the client is authenticated with the API."""
        return self.api_client.ensure_authenticated()
    
    def get_token(self) -> bool:
        """Get an authentication token."""
        return self.api_client.ensure_authenticated()
    
    def get_soc_data(self, max_retries: int = 5, retry_delay: int = 1) -> Optional[Dict[str, Any]]:
        """Get State of Charge data from the API with validation."""
        soc_data = self.battery_data_api.get_soc_data(max_retries, retry_delay)
        if not soc_data:
            return None
        
        # Convert to the legacy format for backward compatibility
        return {
            "soc": soc_data.soc,
            "gridConsumption": soc_data.grid_consumption,
            "battery": soc_data.battery,
            "houseConsumption": soc_data.house_consumption,
            "createTime": soc_data.create_time,
            "pv": soc_data.pv
        }
    
    def get_grid_data(self, max_retries: int = 5, retry_delay: int = 1) -> Optional[Dict[str, Any]]:
        """Get Grid data from the API with validation."""
        grid_data = self.battery_data_api.get_grid_data(max_retries, retry_delay)
        if not grid_data:
            return None
        
        # Convert to the legacy format for backward compatibility
        return {
            "Total_Solar_Generation": grid_data.total_solar_generation,
            "Total_Feed_In": grid_data.total_feed_in,
            "Total_Battery_Charge": grid_data.total_battery_charge,
            "PV_Power_House": grid_data.pv_power_house,
            "PV_Charging_Battery": grid_data.pv_charging_battery,
            "Total_House_Consumption": grid_data.total_house_consumption,
            "Grid_Based_Battery_Charge": grid_data.grid_based_battery_charge,
            "Grid_Power_Consumption": grid_data.grid_power_consumption
        }
    
    def get_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> Dict[str, Any]:
        """Get current battery settings."""
        settings = self.settings_api.get_current_settings(max_retries, retry_delay)
        
        # Convert to the legacy format for backward compatibility
        return settings.to_dict()
    
    def update_battery_settings(self, 
                               discharge_start_time=None, 
                               discharge_end_time=None,
                               charge_start_time=None,
                               charge_end_time=None,
                               minimum_soc=None,
                               max_retries: int = 5, 
                               retry_delay: int = 1) -> bool:
        """
        Update battery settings with API fetch to preserve existing settings.
        
        Args:
            discharge_start_time: Time to start battery discharge (format HH:MM)
            discharge_end_time: Time to end battery discharge (format HH:MM)
            charge_start_time: Time to start battery charging (format HH:MM)
            charge_end_time: Time to end battery charging (format HH:MM)
            minimum_soc: Minimum state of charge percentage to maintain (1-100)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        return self.settings_api.update_battery_settings(
            discharge_start_time,
            discharge_end_time,
            charge_start_time,
            charge_end_time,
            minimum_soc,
            max_retries,
            retry_delay
        )
    
    # Legacy method for backward compatibility
    def set_battery_settings(self, end_discharge="23:00", max_retries=5, retry_delay=1) -> bool:
        """
        Legacy method for backward compatibility - updates only the discharge end time.
        """
        return self.settings_api.set_battery_settings(end_discharge, max_retries, retry_delay)
