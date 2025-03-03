"""Byte-Watt API client with API settings fetching."""
import requests
import json
import time
import re
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

class ByteWattClient:
    """Client for interacting with the Byte-Watt API with improved settings handling."""
    
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
        
        # Default settings cache (used only if API fetch fails)
        self._settings_cache = {
            "grid_charge": 1,
            "ctr_dis": 1,
            "bat_use_cap": 6,  # Minimum remaining SOC
            "time_chaf1a": "14:30",  # Charge start time
            "time_chae1a": "16:00",  # Charge end time
            "time_chaf2a": "00:00",
            "time_chae2a": "00:00",
            "time_disf1a": "16:00",  # Discharge start time
            "time_dise1a": "23:00",  # Discharge end time
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
        self._settings_loaded = False
    
    def sanitize_time_format(self, time_str):
        """
        Sanitize time format to ensure it's in HH:MM format.
        
        Args:
            time_str: Time string to sanitize
            
        Returns:
            Time string in HH:MM format, or None if invalid
        """
        if not time_str:
            return None
            
        # Try different formats
        time_formats = [
            # Standard time formats
            r'^(\d{1,2}):(\d{1,2})$',                # HH:MM
            r'^(\d{1,2}):(\d{1,2}):\d{1,2}$',        # HH:MM:SS
            r'^(\d{1,2}):(\d{1,2}):\d{1,2}\.\d+$',   # HH:MM:SS.ms
            
            # Home Assistant time picker formats
            r'^(\d{1,2}):(\d{1,2}) [APap][Mm]$',     # HH:MM AM/PM
        ]
        
        for pattern in time_formats:
            match = re.match(pattern, time_str)
            if match:
                hours, minutes = match.groups()
                hours = int(hours)
                minutes = int(minutes)
                
                # Validate hours and minutes
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    # Return in HH:MM format
                    return f"{hours:02d}:{minutes:02d}"
        
        # Check if it's just the entity_id of a time entity
        if time_str.startswith('input_datetime.') or time_str.startswith('sensor.'):
            _LOGGER.warning(f"Time value appears to be an entity ID: {time_str}. " 
                          f"Please use the actual time value instead.")
            return None
        
        _LOGGER.error(f"Invalid time format: {time_str}. Expected format: HH:MM")
        return None
    
    def validate_settings_input(self, discharge_start_time, discharge_end_time, 
                                charge_start_time, charge_end_time, minimum_soc):
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
        discharge_start = self.sanitize_time_format(discharge_start_time)
        discharge_end = self.sanitize_time_format(discharge_end_time)
        charge_start = self.sanitize_time_format(charge_start_time)
        charge_end = self.sanitize_time_format(charge_end_time)
        
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
    
    def is_valid_response(self, data):
        """
        Check if the API response is valid based on pmeter values.
        
        Args:
            data: The API response data
            
        Returns:
            bool: True if the response is valid, False otherwise
        """
        if not data or "data" not in data:
            return False
        
        # Check for non-zero pmeter values, which indicate a bad response
        pmeter_l1 = data["data"].get("pmeter_l1", 0)
        pmeter_l2 = data["data"].get("pmeter_l2", 0)
        pmeter_l3 = data["data"].get("pmeter_l3", 0)
        
        # If any pmeter value is non-zero, the response is invalid
        if pmeter_l1 != 0 or pmeter_l2 != 0 or pmeter_l3 != 0:
            _LOGGER.warning(
                f"Invalid API response detected: pmeter_l1={pmeter_l1}, " +
                f"pmeter_l2={pmeter_l2}, pmeter_l3={pmeter_l3}"
            )
            return False
        
        return True

    # Then modify the get_soc_data method to use this validation
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
                        
                        # Check if the response is valid
                        if not self.is_valid_response(data):
                            _LOGGER.warning(f"Invalid response data, retrying (attempt {attempt+1}/{max_retries})")
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

        
        url = f"{self.base_url}/api/Power/SticsByPeriod?beginDay=2020-01-01&endDay=2035-08-30&SN=&noLoading=true"
        
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

    def fetch_current_settings(self, max_retries=3, retry_delay=1):
        """
        Fetch current battery settings directly from the API.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Dictionary of current settings if successful, None if failed
        """
        if not self.access_token and not self.get_token():
            return None
            
        url = f"{self.base_url}/api/Account/GetCustomUseESSSetting"
        
        for attempt in range(max_retries):
            try:
                headers = self.set_auth_headers()
                
                _LOGGER.debug(f"Fetching current settings attempt {attempt+1}/{max_retries}")
                
                response = self.session.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if "code" in data and data["code"] == 9007:
                            _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {data['info']}")
                            # Server is reporting a network issue, let's retry
                            time.sleep(retry_delay)
                            continue
                            
                        if "data" in data and "code" in data and data["code"] == 200:
                            # Success! Extract all the settings we need
                            settings_data = data["data"]
                            
                            # Extract the key settings we need
                            settings = {
                                "grid_charge": settings_data.get("grid_charge", 1),
                                "ctr_dis": settings_data.get("ctr_dis", 1),
                                "bat_use_cap": settings_data.get("bat_use_cap", 6),
                                "time_chaf1a": settings_data.get("time_chaf1a", "14:30"),
                                "time_chae1a": settings_data.get("time_chae1a", "16:00"),
                                "time_chaf2a": settings_data.get("time_chaf2a", "00:00"),
                                "time_chae2a": settings_data.get("time_chae2a", "00:00"),
                                "time_disf1a": settings_data.get("time_disf1a", "16:00"),
                                "time_dise1a": settings_data.get("time_dise1a", "23:00"),
                                "time_disf2a": settings_data.get("time_disf2a", "06:00"),
                                "time_dise2a": settings_data.get("time_dise2a", "10:00"),
                                "bat_high_cap": settings_data.get("bat_high_cap", 100),
                                "time_cha_fwe1a": settings_data.get("time_cha_fwe1a", "00:00"),
                                "time_cha_ewe1a": settings_data.get("time_cha_ewe1a", "00:00"),
                                "time_cha_fwe2a": settings_data.get("time_cha_fwe2a", "00:00"),
                                "time_cha_ewe2a": settings_data.get("time_cha_ewe2a", "00:00"),
                                "time_dis_fwe1a": settings_data.get("time_dis_fwe1a", "00:00"),
                                "time_dis_ewe1a": settings_data.get("time_dis_ewe1a", "00:00"),
                                "time_dis_fwe2a": settings_data.get("time_dis_fwe2a", "00:00"),
                                "time_dis_ewe2a": settings_data.get("time_dis_ewe2a", "00:00"),
                                "peak_s1a": settings_data.get("peak_s1a", "00:00"),
                                "peak_e1a": settings_data.get("peak_e1a", "00:00"),
                                "peak_s2a": settings_data.get("peak_s2a", "00:00"),
                                "peak_e2a": settings_data.get("peak_e2a", "00:00"),
                                "fill_s1a": settings_data.get("fill_s1a", "00:00"),
                                "fill_e1a": settings_data.get("fill_e1a", "00:00"),
                                "fill_s2a": settings_data.get("fill_s2a", "00:00"),
                                "fill_e2a": settings_data.get("fill_e2a", "00:00"),
                                "pm_offset_s1a": settings_data.get("pm_offset_s1a", "00:00"),
                                "pm_offset_e1a": settings_data.get("pm_offset_e1a", "00:00"),
                                "pm_offset_s2a": settings_data.get("pm_offset_s2a", "00:00"),
                                "pm_offset_e2a": settings_data.get("pm_offset_e2a", "00:00")
                            }
                            
                            # Also include any other fields that might be required
                            for field in [
                                "sys_sn", "ems_version", "charge_workdays", "bakbox_ver",
                                "charge_weekend", "grid_Charge_we", "bat_highcap_we",
                                "ctr_dis_we", "bat_usecap_we", "basic_mode_jp", "peace_mode_jp",
                                "vpp_mode_jp", "channel1", "control_mode1", "start_time1a", 
                                "end_time1a", "start_time1b", "end_time1b", "date1", 
                                "charge_soc1", "ups1", "switch_on1", "switch_off1", 
                                "delay1", "duration1", "pause1", "channel2", "control_mode2", 
                                "start_time2a", "end_time2a", "start_time2b", "end_time2b", 
                                "date2", "charge_soc2", "ups2", "switch_on2", "switch_off2", 
                                "delay2", "duration2", "pause2", "l1_priority", "l2_priority", 
                                "l3_priority", "l1_soc_limit", "l2_soc_limit", "l3_soc_limit", 
                                "charge_mode2", "charge_mode1", "backupbox", "minv", "mbat", 
                                "generator", "gc_output_mode", "generator_mode", "gc_soc_start", 
                                "gc_soc_end", "gc_time_start", "gc_time_end", "gc_charge_power", 
                                "gc_rated_power", "dg_cap", "dg_frequency", "gc_rate_percent", 
                                "chargingpile", "currentsetting", "chargingmode", "charging_pile_list", 
                                "chargingpile_control_open", "peak_fill_en", "peakvalue", "fillvalue", 
                                "delta", "pm_offset", "pm_max", "pm_offset_en", "stoinv_type", 
                                "loadcut_soc", "loadtied_soc", "ac_tied", "soc_50_flag", 
                                "auto_soccalib_en", "three_unbalance_en", "enable_current_set", 
                                "enable_obc_set", "upsReserve", "columnIsSow", "nmi", "state", 
                                "agent", "country_code", "register_dynamic_export", "register_type"
                            ]:
                                if field in settings_data:
                                    settings[field] = settings_data[field]
                            
                            # Update our settings cache
                            self._settings_cache = settings
                            self._settings_loaded = True
                            
                            _LOGGER.info(f"Successfully fetched current settings")
                            _LOGGER.debug(f"Current settings: " +
                                         f"Charge: {settings['time_chaf1a']}-{settings['time_chae1a']}, " +
                                         f"Discharge: {settings['time_disf1a']}-{settings['time_dise1a']}, " +
                                         f"Min SOC: {settings['bat_use_cap']}%")
                            
                            return settings
                        else:
                            _LOGGER.error(f"Unexpected response format (attempt {attempt+1}/{max_retries}): {data}")
                    except Exception as e:
                        _LOGGER.error(f"Error parsing settings response (attempt {attempt+1}/{max_retries}): {e}")
                elif response.status_code == 401:
                    _LOGGER.info("Token expired, refreshing...")
                    self.access_token = None
                    if not self.get_token():
                        _LOGGER.error("Failed to refresh token")
                        return None
                else:
                    _LOGGER.error(f"Failed to fetch settings: HTTP {response.status_code} (attempt {attempt+1}/{max_retries})")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                _LOGGER.error(f"Exception during settings fetch (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to fetch current settings after {max_retries} attempts")
        # If we failed to fetch from API, use the cached settings or defaults
        if self._settings_loaded:
            _LOGGER.warning("Using cached settings as fallback")
            return self._settings_cache
        else:
            _LOGGER.warning("Using default settings as fallback")
            return self._settings_cache

    def get_current_settings(self, max_retries=3, retry_delay=1):
        """
        Get current battery settings - first try API, then fallback to cache.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Dictionary of current settings
        """
        # First try to fetch from API
        settings = self.fetch_current_settings(max_retries, retry_delay)
        
        # If that failed but we have cached settings, use those
        if settings is None and self._settings_loaded:
            _LOGGER.warning("Using cached settings")
            return self._settings_cache
            
        # If we still don't have settings, use the defaults
        if settings is None:
            _LOGGER.warning("Using default settings")
            return self._settings_cache
            
        return settings

    def update_battery_settings(self, 
                                discharge_start_time=None, 
                                discharge_end_time=None,
                                charge_start_time=None,
                                charge_end_time=None,
                                minimum_soc=None,
                                max_retries=5, 
                                retry_delay=1):
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
        if not self.access_token and not self.get_token():
            return False
        
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
        current_settings = self.get_current_settings()
        if not current_settings:
            _LOGGER.error("Failed to get current settings, cannot proceed with update")
            return False
            
        # Create a copy of the current settings
        settings = current_settings.copy()
        
        # Update settings with provided values (only if they're valid)
        if discharge_start is not None:
            settings["time_disf1a"] = discharge_start
            _LOGGER.debug(f"Updating discharge start time to {discharge_start}")
        
        if discharge_end is not None:
            settings["time_dise1a"] = discharge_end
            _LOGGER.debug(f"Updating discharge end time to {discharge_end}")
        
        if charge_start is not None:
            settings["time_chaf1a"] = charge_start
            _LOGGER.debug(f"Updating charge start time to {charge_start}")
        
        if charge_end is not None:
            settings["time_chae1a"] = charge_end
            _LOGGER.debug(f"Updating charge end time to {charge_end}")
        
        if min_soc is not None:
            settings["bat_use_cap"] = min_soc
            _LOGGER.debug(f"Updating minimum SOC to {min_soc}%")
        
        # Send the updated settings to the server
        return self._send_battery_settings(settings, max_retries, retry_delay)
    
    def _send_battery_settings(self, settings, max_retries=5, retry_delay=1):
        """
        Internal method to send battery settings to the server.
        
        Args:
            settings: Dictionary of battery settings
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.access_token and not self.get_token():
            return False
            
        url = f"{self.base_url}/api/Account/CustomUseESSSetting"
        
        for attempt in range(max_retries):
            try:
                headers = self.set_auth_headers()
                
                _LOGGER.debug(f"Battery settings request attempt {attempt+1}/{max_retries}")
                
                response = self.session.post(url, json=settings, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if "Success" in str(data):
                            _LOGGER.info(f"Successfully updated battery settings")
                            # Update settings cache with the successfully sent settings
                            self._settings_cache = settings.copy()
                            self._settings_loaded = True
                            
                            # Log the updated settings
                            _LOGGER.info(f"Updated settings: " +
                                         f"Charge: {settings['time_chaf1a']}-{settings['time_chae1a']}, " +
                                         f"Discharge: {settings['time_disf1a']}-{settings['time_dise1a']}, " +
                                         f"Min SOC: {settings['bat_use_cap']}%")
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
    
    # Legacy method for backward compatibility
    def set_battery_settings(self, end_discharge="23:00", max_retries=5, retry_delay=1):
        """
        Legacy method for backward compatibility - updates only the discharge end time.
        """
        # Sanitize the time format
        sanitized_end_discharge = self.sanitize_time_format(end_discharge)
        if not sanitized_end_discharge:
            _LOGGER.error(f"Invalid end discharge time format: {end_discharge}")
            return False
            
        return self.update_battery_settings(
            discharge_end_time=sanitized_end_discharge,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
