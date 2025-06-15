"""Battery settings API interface for Byte-Watt integration."""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, Tuple

from ..models import BatterySettings
from ..utilities.time_utils import sanitize_time_format
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .neovolt_client import NeovoltClient

_LOGGER = logging.getLogger(__name__)


class BatterySettingsAPI:
    """API client for battery settings."""
    
    def __init__(self, api_client: 'NeovoltClient'):
        """Initialize the battery settings API client."""
        self.api_client = api_client
        
        # Default settings cache (used only if API fetch fails)
        self._settings_cache = BatterySettings()
        self._settings_loaded = False
    
    def validate_settings_input(self, 
                              discharge_start_time, 
                              discharge_end_time, 
                              charge_start_time, 
                              charge_end_time, 
                              minimum_soc):
        """
        Validate input parameters for battery settings.
        
        Args:
            discharge_start_time: Time to start battery discharge
            discharge_end_time: Time to end battery discharge
            charge_start_time: Time to start battery charging
            charge_end_time: Time to end battery charging
            minimum_soc: Minimum state of charge percentage
            
        Returns:
            Tuple of validated values (discharge_start, discharge_end, charge_start, charge_end, min_soc)
            Invalid values will be None
        """
        # Sanitize time formats
        discharge_start = sanitize_time_format(discharge_start_time)
        discharge_end = sanitize_time_format(discharge_end_time)
        charge_start = sanitize_time_format(charge_start_time)
        charge_end = sanitize_time_format(charge_end_time)
        
        # Validate minimum SOC
        min_soc = None
        if minimum_soc is not None:
            try:
                min_soc_val = int(minimum_soc)
                if 1 <= min_soc_val <= 100:
                    min_soc = min_soc_val
                else:
                    _LOGGER.error(f"Minimum SOC must be between 1 and 100, got {minimum_soc}")
            except (ValueError, TypeError):
                _LOGGER.error(f"Invalid minimum SOC value: {minimum_soc}")
        
        return discharge_start, discharge_end, charge_start, charge_end, min_soc
    
    async def fetch_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> Optional[BatterySettings]:
        """
        Fetch current battery settings directly from the API using new endpoint.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            BatterySettings if successful, None if failed
        """
        # Use new API endpoint with empty id= to get settings for all devices
        endpoint = "api/iterate/sysSet/getChargeConfigInfo?id="
        
        for attempt in range(max_retries):
            response = await self.api_client._async_get(endpoint)
            
            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            if "data" not in response or "code" not in response or response["code"] != 200:
                _LOGGER.error(f"Unexpected response format (attempt {attempt+1}/{max_retries}): {response}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            # Success! Extract the settings
            settings = BatterySettings.from_api_response(response["data"])
            
            # Update our settings cache
            self._settings_cache = settings
            self._settings_loaded = True
            
            _LOGGER.info(f"Successfully fetched current settings from new API")
            _LOGGER.debug(f"Current settings: " +
                         f"Charge: {settings.time_chaf1a}-{settings.time_chae1a}, " +
                         f"Discharge: {settings.time_disf1a}-{settings.time_dise1a}, " +
                         f"Min SOC: {settings.bat_use_cap}%")
            
            return settings
        
        _LOGGER.error(f"Failed to fetch current settings after {max_retries} attempts")
        # If we failed to fetch from API, use the cached settings or defaults
        if self._settings_loaded:
            _LOGGER.warning("Using cached settings as fallback")
            return self._settings_cache
        else:
            _LOGGER.warning("Using default settings as fallback")
            return self._settings_cache
    
    async def get_current_settings(self, max_retries: int = 3, retry_delay: int = 1) -> BatterySettings:
        """
        Get current battery settings - first try API, then fallback to cache.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Current battery settings
        """
        # First try to fetch from API
        settings = await self.fetch_current_settings(max_retries, retry_delay)
        
        # If that failed but we have cached settings, use those
        if settings is None and self._settings_loaded:
            _LOGGER.warning("Using cached settings")
            return self._settings_cache
            
        # If we still don't have settings, use the defaults
        if settings is None:
            _LOGGER.warning("Using default settings")
            return self._settings_cache
            
        return settings
    
    async def update_battery_settings(self, 
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
        # Validate all inputs
        discharge_start, discharge_end, charge_start, charge_end, min_soc = self.validate_settings_input(
            discharge_start_time, discharge_end_time, charge_start_time, charge_end_time, minimum_soc
        )
        
        # Check if any changes were made
        if (discharge_start is None and discharge_end is None and 
            charge_start is None and charge_end is None and min_soc is None):
            _LOGGER.warning("No valid battery settings provided, nothing to update")
            return False
        
        # Get current settings from the API - this will fetch from API or use cache as fallback
        current_settings = await self.get_current_settings()
        
        # Create a copy of the current settings
        settings = current_settings
        
        # Update settings with provided values (only if they're valid)
        if discharge_start is not None:
            settings.time_disf1a = discharge_start
            _LOGGER.debug(f"Updating discharge start time to {discharge_start}")
        
        if discharge_end is not None:
            settings.time_dise1a = discharge_end
            _LOGGER.debug(f"Updating discharge end time to {discharge_end}")
        
        if charge_start is not None:
            settings.time_chaf1a = charge_start
            _LOGGER.debug(f"Updating charge start time to {charge_start}")
        
        if charge_end is not None:
            settings.time_chae1a = charge_end
            _LOGGER.debug(f"Updating charge end time to {charge_end}")
        
        if min_soc is not None:
            settings.bat_use_cap = min_soc
            _LOGGER.debug(f"Updating minimum SOC to {min_soc}%")
        
        # Send the updated settings to the server
        return await self._send_battery_settings(settings, max_retries, retry_delay)
    
    async def _send_battery_settings(self, 
                              settings: BatterySettings, 
                              max_retries: int = 5, 
                              retry_delay: int = 1) -> bool:
        """
        Internal method to send battery settings to the server.
        
        Args:
            settings: Battery settings to send
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        endpoint = "api/iterate/sysSet/updateChargeConfigInfo"
        
        for attempt in range(max_retries):
            response = await self.api_client._async_put(endpoint, settings.to_dict())
            
            if not response:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            # Check for successful response based on new API format
            if response.get("code") == 200 and response.get("msg") == "Success":
                _LOGGER.info(f"Successfully updated battery settings using new API")
                # Update settings cache with the successfully sent settings
                self._settings_cache = settings
                self._settings_loaded = True
                
                # Log the updated settings
                _LOGGER.info(f"Updated settings: " +
                            f"Charge: {settings.time_chaf1a}-{settings.time_chae1a}, " +
                            f"Discharge: {settings.time_disf1a}-{settings.time_dise1a}, " +
                            f"Min SOC: {settings.bat_use_cap}%")
                return True
            elif response.get("code") == 9007:
                _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {response.get('msg', 'Unknown error')}")
                # Server is reporting a network issue, let's retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            else:
                _LOGGER.error(f"Unexpected response when setting battery parameters: {response}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
        
        _LOGGER.error(f"Failed to update battery settings after {max_retries} attempts")
        return False
    
    async def set_battery_settings(self, end_discharge="23:00", max_retries: int = 5, retry_delay: int = 1) -> bool:
        """
        Legacy method for backward compatibility - updates only the discharge end time.
        
        Args:
            end_discharge: Time to end battery discharge (format HH:MM)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        # Sanitize the time format
        sanitized_end_discharge = sanitize_time_format(end_discharge)
        if not sanitized_end_discharge:
            _LOGGER.error(f"Invalid end discharge time format: {end_discharge}")
            return False
            
        return await self.update_battery_settings(
            discharge_end_time=sanitized_end_discharge,
            max_retries=max_retries,
            retry_delay=retry_delay
        )