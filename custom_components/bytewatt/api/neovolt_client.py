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
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.session.get(
                    url=url,
                    params=params,
                    headers=headers
                )
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to get battery data with status %s: %s", 
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
                        "Failed to get battery data with code %s: %s", 
                        result.get("code"), 
                        result.get("msg")
                    )
                    return None
                
                _LOGGER.debug("Received battery data: %s", result.get("data"))
                return result.get("data")
                
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Error fetching battery data: %s", error)
            return None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get the authentication headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }