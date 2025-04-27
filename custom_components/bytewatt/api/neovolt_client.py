"""API client for Neovolt battery systems."""
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .neovolt_auth import encrypt_password

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_BASE_URL = "https://monitor.byte-watt.com"

class NeovoltClient:
    """API Client for Neovolt battery systems."""
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        username: str, 
        password: str, 
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.username = username
        self.password = password
        self.base_url = base_url
        self.session = async_get_clientsession(hass)
        self.token: Optional[str] = None
        self._settings_cache = {}
    
    async def async_login(self) -> bool:
        """Login to the Neovolt API using encrypted password."""
        _LOGGER.debug("Logging in to Neovolt API as %s", self.username)
        
        login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
        
        # Encrypt password using the correct method
        encrypted_password = encrypt_password(self.password, self.username)
        
        # JSON payload with encrypted password
        payload = {
            "username": self.username,
            "password": encrypted_password
        }
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.post(
                    url=login_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Login failed with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    return await self._async_login_fallback()
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Login failed with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return await self._async_login_fallback()
                
                # Extract token - handle different response formats
                if "token" in result:
                    self.token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    self.token = result["data"]["token"]
                else:
                    _LOGGER.error("No token found in login response")
                    return False
                
                _LOGGER.debug("Successfully logged in to Neovolt API")
                return True
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error connecting to Neovolt API: %s", error)
            return await self._async_login_fallback()
    
    async def _async_login_fallback(self) -> bool:
        """Fallback login method using form data with unencrypted password."""
        _LOGGER.debug("Trying fallback login with unencrypted password")
        
        login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
        
        # Form data with original password
        form_data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.post(
                    url=login_url,
                    data=form_data
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Fallback login failed with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    return False
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Fallback login failed with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return False
                
                # Extract token - handle different response formats
                if "token" in result:
                    self.token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    self.token = result["data"]["token"]
                else:
                    _LOGGER.error("No token found in fallback login response")
                    return False
                
                _LOGGER.debug("Successfully logged in with fallback method")
                return True
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error connecting to Neovolt API with fallback method: %s", error)
            return False
    
    async def async_get_device_list(self) -> Optional[Dict[str, Any]]:
        """Get the list of devices."""
        if not self.token:
            if not await self.async_login():
                return None
        
        url = f"{self.base_url}/api/devices/list"
        
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    headers=self._get_auth_headers()
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to get device list with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    
                    # Try refreshing token and retrying the request
                    if response.status == 401:
                        if await self.async_login():
                            return await self.async_get_device_list()
                    
                    return None
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Failed to get device list with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return None
                
                return result.get("data")
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error fetching device list: %s", error)
            return None
    
    async def async_get_battery_data(self, station_id: str = None) -> Optional[Dict[str, Any]]:
        """Get data for a specific battery using the new API endpoint."""
        if not self.token:
            if not await self.async_login():
                return None
        
        # First get the real-time power data
        url = f"{self.base_url}/api/report/energyStorage/getLastPowerData"
        
        params = {
            "sysSn": "All",
            "stationId": station_id or ""
        }
        
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        headers = self._get_auth_headers()
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "language": "en-US",
            "operationDate": current_date,
            "platform": "AK9D8H",
            "System": "alphacloud"
        })
        
        try:
            battery_data = {}
            
            # Get real-time power data
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    params=params,
                    headers=headers
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to get battery power data with status %s: %s", 
                        response.status, 
                        await response.text()
                    )
                    
                    # Try refreshing token and retrying the request
                    if response.status == 401:
                        if await self.async_login():
                            return await self.async_get_battery_data(station_id)
                    
                    return None
                
                result = await response.json()
                
                if result.get("code") != 0 and result.get("code") != 200:
                    _LOGGER.error(
                        "Failed to get battery power data with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return None
                
                # Store power data
                power_data = result.get("data", {})
                _LOGGER.debug("Received battery power data: %s", power_data)
                _LOGGER.debug("Available power data attributes: %s", list(power_data.keys()) if power_data else None)
                
                # Merge power data into our result
                battery_data.update(power_data)
            
            # Now get the energy statistics
            stats_url = f"{self.base_url}/api/report/energy/getEnergyStatistics"
            from datetime import datetime, timedelta
            
            # Get date range from 2020-01-01 to today
            end_date = datetime.now().strftime("%Y-%m-%d")
            begin_date = "2020-01-01"
            
            stats_params = {
                "sysSn": "All", 
                "stationId": station_id or "",
                "beginDate": begin_date,
                "endDate": end_date
            }
            
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                stats_response = await self.session.get(
                    url=stats_url,
                    params=stats_params,
                    headers=headers
                )
                
                if stats_response.status == 200:
                    stats_result = await stats_response.json()
                    
                    if stats_result.get("code") == 200 or stats_result.get("code") == 0:
                        stats_data = stats_result.get("data", {})
                        _LOGGER.debug("Received energy statistics data: %s", stats_data)
                        _LOGGER.debug("Available statistics attributes: %s", list(stats_data.keys()) if stats_data else None)
                        
                        # Map the statistics data to the grid sensor names
                        if stats_data:
                            # Total solar generation
                            battery_data["Total_Solar_Generation"] = stats_data.get("epvT")
                            # Total feed in (grid export)
                            battery_data["Total_Feed_In"] = stats_data.get("eout")
                            # Total battery charge
                            battery_data["Total_Battery_Charge"] = stats_data.get("echarge")
                            # PV to house
                            battery_data["PV_Power_House"] = stats_data.get("epv2load")
                            # PV charging battery
                            battery_data["PV_Charging_Battery"] = stats_data.get("epvcharge")
                            # Total house consumption
                            battery_data["Total_House_Consumption"] = stats_data.get("eload")
                            # Grid charging battery
                            battery_data["Grid_Based_Battery_Charge"] = stats_data.get("egridCharge")
                            # Grid power consumption
                            battery_data["Grid_Power_Consumption"] = stats_data.get("einput")
                    else:
                        _LOGGER.warning(
                            "Failed to get energy statistics with code %s: %s", 
                            stats_result.get("code"), 
                            stats_result.get("msg")
                        )
                else:
                    _LOGGER.warning(
                        "Failed to get energy statistics with status %s", 
                        stats_response.status
                    )
            
            _LOGGER.debug("Combined battery data: %s", battery_data)
            return battery_data
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error fetching battery data: %s", error)
            return None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get the authentication headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }