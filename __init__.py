"""The Byte-Watt integration."""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_SET_DISCHARGE_TIME,
    SERVICE_SET_DISCHARGE_START_TIME,
    SERVICE_SET_DISCHARGE_END_TIME,
    SERVICE_SET_GRID_CHARGE_START_TIME,
    SERVICE_SET_GRID_CHARGE_END_TIME,
    ATTR_END_DISCHARGE,
    ATTR_START_DISCHARGE,
    ATTR_START_GRID_CHARGE,
    ATTR_END_GRID_CHARGE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Byte-Watt component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Byte-Watt from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    client = ByteWattClient(username, password)

    coordinator = ByteWattDataUpdateCoordinator(
        hass,
        client=client,
        scan_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # Register the service to set discharge time
    async def handle_set_discharge_time(call: ServiceCall):
        """Handle the service call to set discharge time."""
        end_discharge = call.data.get(ATTR_END_DISCHARGE)
        if not end_discharge:
            _LOGGER.error("No end_discharge time provided")
            return

        for entry_id, entry_data in hass.data[DOMAIN].items():
            client = entry_data["client"]
            success = await hass.async_add_executor_job(
                client.set_battery_settings, end_discharge
            )
            if success:
                _LOGGER.info(f"Successfully set discharge time to {end_discharge}")
            else:
                _LOGGER.error(f"Failed to set discharge time to {end_discharge}")

    # Register the service to set discharge start time
    async def handle_set_discharge_start_time(call: ServiceCall):
        """Handle the service call to set discharge start time."""
        start_discharge = call.data.get(ATTR_START_DISCHARGE)
        if not start_discharge:
            _LOGGER.error("No start_discharge time provided")
            return

        for entry_id, entry_data in hass.data[DOMAIN].items():
            client = entry_data["client"]
            success = await hass.async_add_executor_job(
                client.set_discharge_start_time, start_discharge
            )
            if success:
                _LOGGER.info(f"Successfully set discharge start time to {start_discharge}")
            else:
                _LOGGER.error(f"Failed to set discharge start time to {start_discharge}")

    # Register the service to set discharge end time
    async def handle_set_discharge_end_time(call: ServiceCall):
        """Handle the service call to set discharge end time."""
        end_discharge = call.data.get(ATTR_END_DISCHARGE)
        if not end_discharge:
            _LOGGER.error("No end_discharge time provided")
            return

        for entry_id, entry_data in hass.data[DOMAIN].items():
            client = entry_data["client"]
            success = await hass.async_add_executor_job(
                client.set_discharge_end_time, end_discharge
            )
            if success:
                _LOGGER.info(f"Successfully set discharge end time to {end_discharge}")
            else:
                _LOGGER.error(f"Failed to set discharge end time to {end_discharge}")

    # Register the service to set grid charge start time
    async def handle_set_grid_charge_start_time(call: ServiceCall):
        """Handle the service call to set grid charge start time."""
        start_grid_charge = call.data.get(ATTR_START_GRID_CHARGE)
        if not start_grid_charge:
            _LOGGER.error("No start_grid_charge time provided")
            return

        for entry_id, entry_data in hass.data[DOMAIN].items():
            client = entry_data["client"]
            success = await hass.async_add_executor_job(
                client.set_grid_charge_start_time, start_grid_charge
            )
            if success:
                _LOGGER.info(f"Successfully set grid charge start time to {start_grid_charge}")
            else:
                _LOGGER.error(f"Failed to set grid charge start time to {start_grid_charge}")

    # Register the service to set grid charge end time
    async def handle_set_grid_charge_end_time(call: ServiceCall):
        """Handle the service call to set grid charge end time."""
        end_grid_charge = call.data.get(ATTR_END_GRID_CHARGE)
        if not end_grid_charge:
            _LOGGER.error("No end_grid_charge time provided")
            return

        for entry_id, entry_data in hass.data[DOMAIN].items():
            client = entry_data["client"]
            success = await hass.async_add_executor_job(
                client.set_grid_charge_end_time, end_grid_charge
            )
            if success:
                _LOGGER.info(f"Successfully set grid charge end time to {end_grid_charge}")
            else:
                _LOGGER.error(f"Failed to set grid charge end time to {end_grid_charge}")

    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_DISCHARGE_TIME,
        handle_set_discharge_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_DISCHARGE): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_DISCHARGE_START_TIME,
        handle_set_discharge_start_time,
        schema=vol.Schema({
            vol.Required(ATTR_START_DISCHARGE): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_DISCHARGE_END_TIME,
        handle_set_discharge_end_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_DISCHARGE): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_GRID_CHARGE_START_TIME,
        handle_set_grid_charge_start_time,
        schema=vol.Schema({
            vol.Required(ATTR_START_GRID_CHARGE): cv.string,
        })
    )

    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_GRID_CHARGE_END_TIME,
        handle_set_grid_charge_end_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_GRID_CHARGE): cv.string,
        })
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
            name=DOMAIN,
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
