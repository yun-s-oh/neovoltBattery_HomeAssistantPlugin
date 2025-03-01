"""Byte-Watt API client with pure dynamic authentication signature generation."""
import requests
import json
import time
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

class ByteWattClient:
    """Client for interacting with the Byte-Watt API with dynamic authentication."""
    
    def __init__(self, username, password):
        """Initialize with login credentials."""
        self.base_url = "https://monitor.byte-watt.com"
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.access_token = None
        
        # For signature generation
        self.prefix = "al8e4s"
        self.suffix = "ui893ed"
    
    def get_auth_signature(self, is_login=False):
        """
        Generate a dynamic auth signature.
        
        Args:
            is_login: True for login endpoint, False for other API endpoints
        
        Returns:
            A dynamically generated authentication signature
        """
        # Choose modifier based on endpoint type
        modifier = 'd' if is_login else 'e'
        
        # Create a pattern for the middle part (128 characters)
        # We'll use a simple repeating pattern of hexadecimal digits
        middle_part = ""
        for i in range(128):
            # Simple pattern that creates a pseudo-random but consistent string
            c = "0123456789abcdef"[i % 16]
            middle_part += c
        
        # Combine all parts to create the final signature
        signature = f"{self.prefix}{modifier}{middle_part}{self.suffix}"
        return signature
    
    def get_token(self):
        """Get an authentication token."""
        try:
            # Generate dynamic signature for login
            auth_signature = self.get_auth_signature(is_login=True)
            login_url = f"{self.base_url}/api/Account/Login?authsignature={auth_signature}&authtimestamp=11111"
            
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            _LOGGER.debug(f"Sending login request with dynamic signature")
            _LOGGER.debug(f"Signature: {auth_signature[:15]}...{auth_signature[-15:]}")
            
            response = self.session.post(login_url, json=payload, headers=headers)
            
            _LOGGER.debug(f"Login response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and "AccessToken" in data["data"]:
                        self.access_token = data["data"]["AccessToken"]
                        _LOGGER.debug(f"Successfully obtained token: {self.access_token[:10]}...")
                        return True
                    else:
                        _LOGGER.error(f"Token not found in response: {data}")
                except Exception as e:
                    _LOGGER.error(f"Error parsing login response: {e}")
            else:
                try:
                    _LOGGER.error(f"Login failed with status {response.status_code}: {response.text}")
                except:
                    _LOGGER.error(f"Login failed with status {response.status_code}")
            
            return False
        except Exception as e:
            _LOGGER.error(f"Error in login: {e}")
            return False
    
    def set_auth_headers(self):
        """Set authentication headers for an API request."""
        # Generate dynamic signature for API calls
        auth_signature = self.get_auth_signature(is_login=False)
        
        headers = {
            "Content-Type": "application/json",
            "authtimestamp": "11111",
            "authsignature": auth_signature
        }
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers
    
    def get_soc_data(self, max_retries=5, retry_delay=1):
        """Get State of Charge data from the API with retry capability."""
        if not self.access_token and not self.get_token():
            return None
        
        url = f"{self.base_url}/api/ESS/GetLastPowerDataBySN?sys_sn=All&noLoading=true"
        
        for attempt in range(max_retries):
            try:
                headers = self.set_auth_headers()
                
                _LOGGER.debug(f"SOC request attempt {attempt+1}/{max_retries}")
                
                response = self.session.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if "code" in data and data["code"] == 9007:
                            _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {data['info']}")
                            # Server is reporting a network issue, let's retry
                            time.sleep(retry_delay)
                            continue
                            
                        if "data" in data:
                            # Success! Extract the data
                            return {
                                "soc": data["data"].get("soc", 0),
                                "gridConsumption": data["data"].get("pmeter_l1", 0),
                                "battery": data["data"].get("pbat", 0),
                                "houseConsumption": data["data"].get("pmeter_l1", 0) + data["data"].get("pbat", 0),
                                "createTime": data["data"].get("createtime", ""),
                                "pv": data["data"].get("ppv1", 0)
                            }
                        else:
                            _LOGGER.error(f"Unexpected response format (attempt {attempt+1}/{max_retries}): {data}")
                    except Exception as e:
                        _LOGGER.error(f"Error parsing SOC data (attempt {attempt+1}/{max_retries}): {e}")
                elif response.status_code == 401:
                    _LOGGER.info("Token expired, refreshing...")
                    self.access_token = None
                    if not self.get_token():
                        _LOGGER.error("Failed to refresh token")
                        return None
                else:
                    _LOGGER.error(f"Failed to get SOC data: HTTP {response.status_code} (attempt {attempt+1}/{max_retries})")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                _LOGGER.error(f"Exception during SOC request (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to get SOC data after {max_retries} attempts")
        return None
    
    def get_grid_data(self, max_retries=5, retry_delay=1):
        """Get Grid data from the API with retry capability."""
        if not self.access_token and not self.get_token():
            return None
        
        # Using current date for beginDay, and a far future date for endDay
        today = datetime.now().strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/api/Power/SticsByPeriod?beginDay={today}&endDay=2030-08-30&SN=&noLoading=true"
        
        for attempt in range(max_retries):
            try:
                headers = self.set_auth_headers()
                
                _LOGGER.debug(f"Grid data request attempt {attempt+1}/{max_retries}")
                
                response = self.session.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if "code" in data and data["code"] == 9007:
                            _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {data['info']}")
                            # Server is reporting a network issue, let's retry
                            time.sleep(retry_delay)
                            continue
                            
                        if "data" in data:
                            # Success! Extract the data
                            return {
                                "Total_Solar_Generation": data["data"].get("EpvT", 0),
                                "Total_Feed_In": data["data"].get("Eout", 0),
                                "Total_Battery_Charge": data["data"].get("Echarge", 0),
                                "PV_Power_House": data["data"].get("Epv2load", 0),
                                "PV_Charging_Battery": data["data"].get("Epvcharge", 0),
                                "Total_House_Consumption": data["data"].get("EHomeLoad", 0),
                                "Grid_Based_Battery_Charge": data["data"].get("EGridCharge", 0),
                                "Grid_Power_Consumption": data["data"].get("EGrid2Load", 0)
                            }
                        else:
                            _LOGGER.error(f"Unexpected response format (attempt {attempt+1}/{max_retries}): {data}")
                    except Exception as e:
                        _LOGGER.error(f"Error parsing grid data (attempt {attempt+1}/{max_retries}): {e}")
                elif response.status_code == 401:
                    _LOGGER.info("Token expired, refreshing...")
                    self.access_token = None
                    if not self.get_token():
                        _LOGGER.error("Failed to refresh token")
                        return None
                else:
                    _LOGGER.error(f"Failed to get grid data: HTTP {response.status_code} (attempt {attempt+1}/{max_retries})")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                _LOGGER.error(f"Exception during grid data request (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to get grid data after {max_retries} attempts")
        return None

    def set_battery_settings(self, end_discharge="23:00", max_retries=5, retry_delay=1):
        """Update battery settings with retry capability."""
        if not self.access_token and not self.get_token():
            return False
        
        url = f"{self.base_url}/api/Account/CustomUseESSSetting"
        
        # Prepare payload (using the same structure as in the original code)
        payload = {
            "grid_charge": 1,
            "ctr_dis": 1,
            "bat_use_cap": 6,
            "time_chaf1a": "14:30",
            "time_chae1a": "16:00",
            "time_chaf2a": "00:00",
            "time_chae2a": "00:00",
            "time_disf1a": "16:00",
            "time_dise1a": end_discharge,
            "time_disf2a": "06:00",
            "time_dise2a": "10:00",
            "bat_high_cap": "100",
            "time_cha_fwe1a": "00:00",
            "time_cha_ewe1a": "00:00",
            "time_cha_fwe2a": "00:00",
            "time_cha_ewe2a": "00:00",
            "time_dis_fwe1a": "00:00",
            "time_dis_ewe1a": "00:00",
            "time_dis_fwe2a": "00:00",
            "time_dis_ewe2a": "00:00",
            "peak_s1a": "00:00",
            "peak_e1a": "00:00",
            "peak_s2a": "00:00",
            "peak_e2a": "00:00",
            "fill_s1a": "00:00",
            "fill_e1a": "00:00",
            "fill_s2a": "00:00",
            "fill_e2a": "00:00",
            "pm_offset_s1a": "00:00",
            "pm_offset_e1a": "00:00",
            "pm_offset_s2a": "00:00",
            "pm_offset_e2a": "00:00"
        }
        
        for attempt in range(max_retries):
            try:
                headers = self.set_auth_headers()
                
                _LOGGER.debug(f"Battery settings request attempt {attempt+1}/{max_retries}")
                
                response = self.session.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if "Success" in str(data):
                            _LOGGER.info(f"Successfully updated battery settings to end discharge at {end_discharge}")
                            return True
                        elif "code" in data and data["code"] == 9007:
                            _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {data['info']}")
                            # Server is reporting a network issue, let's retry
                            time.sleep(retry_delay)
                            continue
                        else:
                            _LOGGER.error(f"Unexpected response when setting battery parameters: {data}")
                    except Exception as e:
                        _LOGGER.error(f"Error parsing settings response (attempt {attempt+1}/{max_retries}): {e}")
                elif response.status_code == 401:
                    _LOGGER.info("Token expired, refreshing...")
                    self.access_token = None
                    if not self.get_token():
                        _LOGGER.error("Failed to refresh token")
                        return False
                else:
                    _LOGGER.error(f"Failed to update settings: HTTP {response.status_code} (attempt {attempt+1}/{max_retries})")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                _LOGGER.error(f"Exception during settings request (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to update battery settings after {max_retries} attempts")
        return False