"""Battery data API interface for Byte-Watt integration."""
import logging
import time
from typing import Optional, Dict, Any

from ..models import SoCData, GridData
from ..validation import EnergyDataValidator
from .client import ByteWattAPIClient

_LOGGER = logging.getLogger(__name__)


class BatteryDataAPI:
    """API client for battery data."""
    
    def __init__(self, api_client: ByteWattAPIClient):
        """Initialize the battery data API client."""
        self.api_client = api_client
        
        # Initialize data validators
        self.soc_validator = EnergyDataValidator()
        self.grid_validator = EnergyDataValidator()
        
        # For tracking last valid grid data
        self._last_valid_grid_data = None
    
    def get_soc_data(self, max_retries: int = 5, retry_delay: int = 1) -> Optional[SoCData]:
        """
        Get State of Charge data from the API with validation.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            SoCData if successful, None otherwise
        """
        endpoint = "api/ESS/GetLastPowerDataBySN?sys_sn=All&noLoading=true"
        
        for attempt in range(max_retries):
            response = self.api_client.get(endpoint, max_retries=1, retry_delay=0)
            current_timestamp = time.time()
            
            if not response:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
            
            if "data" not in response:
                _LOGGER.error(f"No data in response (attempt {attempt+1}/{max_retries}): {response}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
            
            # Use our validator to check for data issues
            is_valid, reason = self.soc_validator.is_valid_response(response["data"], current_timestamp)
            
            if not is_valid:
                _LOGGER.warning(f"Invalid SOC data detected ({reason}), retrying (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
                
            # Success! Extract the valid data
            raw_data = {
                "soc": response["data"].get("soc", 0),
                "gridConsumption": response["data"].get("pmeter_l1", 0),
                "battery": response["data"].get("pbat", 0),
                "houseConsumption": response["data"].get("pmeter_l1", 0) + response["data"].get("pbat", 0),
                "createTime": response["data"].get("createtime", ""),
                "pv": response["data"].get("ppv1", 0)
            }
            
            return SoCData.from_api_response(raw_data)
        
        _LOGGER.error(f"Failed to get SOC data after {max_retries} attempts")
        return None
    
    def get_grid_data(self, max_retries: int = 5, retry_delay: int = 1) -> Optional[GridData]:
        """
        Get Grid data from the API with validation.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            GridData if successful, None otherwise
        """
        endpoint = "api/Power/SticsByPeriod?beginDay=2020-01-01&endDay=2035-08-30&SN=&noLoading=true"
        
        for attempt in range(max_retries):
            response = self.api_client.get(endpoint, max_retries=1, retry_delay=0)
            
            if not response:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
            
            if "data" not in response:
                _LOGGER.error(f"No data in response (attempt {attempt+1}/{max_retries}): {response}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
            
            # Extract the data we need
            grid_data = {
                "Total_Solar_Generation": response["data"].get("EpvT", 0),
                "Total_Feed_In": response["data"].get("Eout", 0),
                "Total_Battery_Charge": response["data"].get("Echarge", 0),
                "PV_Power_House": response["data"].get("Epv2load", 0),
                "PV_Charging_Battery": response["data"].get("Epvcharge", 0),
                "Total_House_Consumption": response["data"].get("EHomeLoad", 0),
                "Grid_Based_Battery_Charge": response["data"].get("EGridCharge", 0),
                "Grid_Power_Consumption": response["data"].get("EGrid2Load", 0)
            }
            
            # For grid data, we check if cumulative values are increasing
            if self._last_valid_grid_data:
                # Check each cumulative value
                decreasing_values = []
                for key, value in grid_data.items():
                    last_value = self._last_valid_grid_data.get(key, 0)
                    if value < last_value:
                        decreasing_values.append(f"{key}: {last_value} -> {value}")
                
                if decreasing_values:
                    _LOGGER.warning(f"Decreasing cumulative values detected: {', '.join(decreasing_values)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    continue
            
            # Store for next comparison and return the data
            self._last_valid_grid_data = grid_data
            return GridData.from_api_response(grid_data)
        
        _LOGGER.error(f"Failed to get grid data after {max_retries} attempts")
        return None