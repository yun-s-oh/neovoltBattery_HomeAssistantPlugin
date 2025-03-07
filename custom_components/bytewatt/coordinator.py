"""Data update coordinator for Byte-Watt integration."""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bytewatt_client import ByteWattClient

_LOGGER = logging.getLogger(__name__)


class ByteWattDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Byte-Watt data with improved error handling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ByteWattClient,
        scan_interval: int,
    ):
        """Initialize."""
        self.client = client
        self.hass = hass
        self._last_soc_data = None
        self._last_grid_data = None

        super().__init__(
            hass,
            _LOGGER,
            name="bytewatt",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Update data via library with improved error handling."""
        try:
            # First, get SOC data with retries
            soc_data = await self.hass.async_add_executor_job(self.client.get_soc_data)
            
            # If we got SOC data, update our cached version
            if soc_data:
                self._last_soc_data = soc_data
            elif self._last_soc_data is None:
                # Only raise error if we never got data
                raise UpdateFailed("Failed to get SOC data and no cached data available")
            else:
                _LOGGER.warning("Using cached SOC data due to API error")
            
            # Try to get grid data
            grid_data = await self.hass.async_add_executor_job(self.client.get_grid_data)
            
            # If we got grid data, update our cached version
            if grid_data:
                self._last_grid_data = grid_data
            elif self._last_grid_data is None:
                # Log warning but don't fail if we never got grid data
                _LOGGER.warning("Failed to get grid data and no cached data available")
                grid_data = {}
            else:
                _LOGGER.warning("Using cached grid data due to API error")
                grid_data = self._last_grid_data
            
            # Return the best data we have
            return {
                "soc": self._last_soc_data or {},
                "grid": self._last_grid_data or {}
            }
        except Exception as err:
            # If we have cached data, use it rather than failing
            if self._last_soc_data:
                _LOGGER.error(f"Error communicating with API: {err}")
                _LOGGER.warning("Using cached data due to communication error")
                return {
                    "soc": self._last_soc_data,
                    "grid": self._last_grid_data or {}
                }
            else:
                raise UpdateFailed(f"Error communicating with API: {err}")