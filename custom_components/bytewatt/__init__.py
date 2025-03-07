"""The Byte-Watt integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

from .bytewatt_client import ByteWattClient
from .coordinator import ByteWattDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_SET_DISCHARGE_TIME,
    SERVICE_SET_DISCHARGE_START_TIME,
    SERVICE_SET_CHARGE_START_TIME,
    SERVICE_SET_CHARGE_END_TIME,
    SERVICE_SET_MINIMUM_SOC,
    SERVICE_UPDATE_BATTERY_SETTINGS,
    ATTR_END_DISCHARGE,
    ATTR_START_DISCHARGE,
    ATTR_START_CHARGE,
    ATTR_END_CHARGE,
    ATTR_MINIMUM_SOC,
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

    # Register all battery control services
    await register_battery_services(hass, client)

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


async def register_battery_services(hass: HomeAssistant, client: ByteWattClient):
    """Register all battery control services."""
    
    # Legacy service - set discharge end time only
    async def handle_set_discharge_time(call: ServiceCall):
        """Handle the service call to set discharge end time."""
        end_discharge = call.data.get(ATTR_END_DISCHARGE)
        if not end_discharge:
            _LOGGER.error("No end_discharge time provided")
            return

        success = await hass.async_add_executor_job(
            client.set_battery_settings, end_discharge
        )
        if success:
            _LOGGER.info(f"Successfully set discharge end time to {end_discharge}")
        else:
            _LOGGER.error(f"Failed to set discharge end time to {end_discharge}")
    
    # New service - set discharge start time
    async def handle_set_discharge_start_time(call: ServiceCall):
        """Handle the service call to set discharge start time."""
        start_discharge = call.data.get(ATTR_START_DISCHARGE)
        if not start_discharge:
            _LOGGER.error("No start_discharge time provided")
            return

        success = await hass.async_add_executor_job(
            client.update_battery_settings,
            start_discharge,  # discharge_start_time
            None,  # discharge_end_time
            None,  # charge_start_time
            None,  # charge_end_time
            None,  # minimum_soc
        )
        if success:
            _LOGGER.info(f"Successfully set discharge start time to {start_discharge}")
        else:
            _LOGGER.error(f"Failed to set discharge start time to {start_discharge}")
    
    # New service - set charge start time
    async def handle_set_charge_start_time(call: ServiceCall):
        """Handle the service call to set charge start time."""
        start_charge = call.data.get(ATTR_START_CHARGE)
        if not start_charge:
            _LOGGER.error("No start_charge time provided")
            return

        success = await hass.async_add_executor_job(
            client.update_battery_settings,
            None,  # discharge_start_time
            None,  # discharge_end_time
            start_charge,  # charge_start_time
            None,  # charge_end_time
            None,  # minimum_soc
        )
        if success:
            _LOGGER.info(f"Successfully set charge start time to {start_charge}")
        else:
            _LOGGER.error(f"Failed to set charge start time to {start_charge}")
    
    # New service - set charge end time
    async def handle_set_charge_end_time(call: ServiceCall):
        """Handle the service call to set charge end time."""
        end_charge = call.data.get(ATTR_END_CHARGE)
        if not end_charge:
            _LOGGER.error("No end_charge time provided")
            return

        success = await hass.async_add_executor_job(
            client.update_battery_settings,
            None,  # discharge_start_time
            None,  # discharge_end_time
            None,  # charge_start_time
            end_charge,  # charge_end_time
            None,  # minimum_soc
        )
        if success:
            _LOGGER.info(f"Successfully set charge end time to {end_charge}")
        else:
            _LOGGER.error(f"Failed to set charge end time to {end_charge}")
    
    # New service - set minimum SOC
    async def handle_set_minimum_soc(call: ServiceCall):
        """Handle the service call to set minimum state of charge."""
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        if minimum_soc is None:
            _LOGGER.error("No minimum_soc provided")
            return

        success = await hass.async_add_executor_job(
            client.update_battery_settings,
            None,  # discharge_start_time
            None,  # discharge_end_time
            None,  # charge_start_time
            None,  # charge_end_time
            minimum_soc,  # minimum_soc
        )
        if success:
            _LOGGER.info(f"Successfully set minimum SOC to {minimum_soc}%")
        else:
            _LOGGER.error(f"Failed to set minimum SOC to {minimum_soc}%")
    
    # New service - update multiple battery settings at once
    async def handle_update_battery_settings(call: ServiceCall):
        """Handle the service call to update multiple battery settings at once."""
        discharge_start_time = call.data.get(ATTR_START_DISCHARGE)
        discharge_end_time = call.data.get(ATTR_END_DISCHARGE)
        charge_start_time = call.data.get(ATTR_START_CHARGE)
        charge_end_time = call.data.get(ATTR_END_CHARGE)
        minimum_soc = call.data.get(ATTR_MINIMUM_SOC)
        
        # Check if at least one parameter is provided
        if (discharge_start_time is None and discharge_end_time is None and
                charge_start_time is None and charge_end_time is None and
                minimum_soc is None):
            _LOGGER.error("No battery settings provided to update")
            return

        success = await hass.async_add_executor_job(
            client.update_battery_settings,
            discharge_start_time,
            discharge_end_time,
            charge_start_time,
            charge_end_time,
            minimum_soc,
        )
        if success:
            _LOGGER.info(f"Successfully updated battery settings")
        else:
            _LOGGER.error(f"Failed to update battery settings")

    # Register all services
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
        SERVICE_SET_CHARGE_START_TIME,
        handle_set_charge_start_time,
        schema=vol.Schema({
            vol.Required(ATTR_START_CHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_CHARGE_END_TIME,
        handle_set_charge_end_time,
        schema=vol.Schema({
            vol.Required(ATTR_END_CHARGE): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_SET_MINIMUM_SOC,
        handle_set_minimum_soc,
        schema=vol.Schema({
            vol.Required(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_UPDATE_BATTERY_SETTINGS,
        handle_update_battery_settings,
        schema=vol.Schema({
            vol.Optional(ATTR_START_DISCHARGE): cv.string,
            vol.Optional(ATTR_END_DISCHARGE): cv.string,
            vol.Optional(ATTR_START_CHARGE): cv.string,
            vol.Optional(ATTR_END_CHARGE): cv.string,
            vol.Optional(ATTR_MINIMUM_SOC): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
    )
