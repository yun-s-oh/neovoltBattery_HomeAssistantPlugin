"""Sensor platform for Byte-Watt integration."""
import logging
from typing import Callable, Dict, Optional
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_SOC,
    SENSOR_GRID_CONSUMPTION,
    SENSOR_HOUSE_CONSUMPTION,
    SENSOR_BATTERY_POWER,
    SENSOR_PV,
    SENSOR_LAST_UPDATE,
    SENSOR_TOTAL_SOLAR,
    SENSOR_TOTAL_FEED_IN,
    SENSOR_TOTAL_BATTERY_CHARGE,
    SENSOR_PV_POWER_HOUSE,
    SENSOR_PV_CHARGING_BATTERY,
    SENSOR_TOTAL_HOUSE_CONSUMPTION,
    SENSOR_GRID_BATTERY_CHARGE,
    SENSOR_GRID_POWER_CONSUMPTION,
    SENSOR_DISCHARGE_START,
    SENSOR_DISCHARGE_END,
    SENSOR_CHARGE_START,
    SENSOR_CHARGE_END,
    SENSOR_MIN_SOC,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Byte-Watt sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    # Define SOC sensors
    soc_sensors = [
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_SOC, 
            "Battery Percentage", 
            "battery", 
            "soc", 
            "%", 
            "mdi:battery"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_CONSUMPTION, 
            "Grid Consumption", 
            "power", 
            "gridConsumption", 
            "W", 
            "mdi:transmission-tower"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_HOUSE_CONSUMPTION, 
            "House Consumption", 
            "power", 
            "houseConsumption", 
            "W", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_BATTERY_POWER, 
            "Battery Power", 
            "power", 
            "battery", 
            "W", 
            "mdi:battery-charging"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_PV, 
            "PV Power", 
            "power", 
            "pv", 
            "W", 
            "mdi:solar-power"
        ),
        ByteWattSensor(
            coordinator, 
            entry, 
            SENSOR_LAST_UPDATE, 
            "Last Update", 
            "timestamp", 
            "createTime", 
            "", 
            "mdi:clock-outline",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
    ]
    
    # Define grid stats sensors - modified to use "energy" device_class for kWh sensors
    grid_sensors = [
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_SOLAR, 
            "Total Solar Generation", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Solar_Generation", 
            "kWh", 
            "mdi:solar-power"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_FEED_IN, 
            "Total Feed In", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Feed_In", 
            "kWh", 
            "mdi:transmission-tower-export"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_BATTERY_CHARGE, 
            "Total Battery Charge", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_Battery_Charge", 
            "kWh", 
            "mdi:battery-charging"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_POWER_HOUSE, 
            "PV Power to House", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "PV_Power_House", 
            "kWh", 
            "mdi:solar-power-variant"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_PV_CHARGING_BATTERY, 
            "PV Charging Battery", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "PV_Charging_Battery", 
            "kWh", 
            "mdi:solar-power-variant-outline"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_TOTAL_HOUSE_CONSUMPTION, 
            "Total House Consumption", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Total_House_Consumption", 
            "kWh", 
            "mdi:home-lightning-bolt"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_BATTERY_CHARGE, 
            "Grid Based Battery Charge", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Grid_Based_Battery_Charge", 
            "kWh", 
            "mdi:transmission-tower-import"
        ),
        ByteWattGridSensor(
            coordinator, 
            entry, 
            SENSOR_GRID_POWER_CONSUMPTION, 
            "Grid Power Consumption", 
            "energy",  # Changed to "energy" for Energy Dashboard
            "Grid_Power_Consumption", 
            "kWh", 
            "mdi:transmission-tower"
        ),
    ]
    
    # Define battery settings sensors
    battery_settings_sensors = [
        ByteWattBatterySettingsSensor(
            coordinator, 
            entry, 
            SENSOR_DISCHARGE_START, 
            "Discharge Start Time", 
            "timestamp", 
            "time_disf1a", 
            "", 
            "mdi:battery-minus"
        ),
        ByteWattBatterySettingsSensor(
            coordinator, 
            entry, 
            SENSOR_DISCHARGE_END, 
            "Discharge End Time", 
            "timestamp", 
            "time_dise1a", 
            "", 
            "mdi:battery-minus-outline"
        ),
        ByteWattBatterySettingsSensor(
            coordinator, 
            entry, 
            SENSOR_CHARGE_START, 
            "Charge Start Time", 
            "timestamp", 
            "time_chaf1a", 
            "", 
            "mdi:battery-plus"
        ),
        ByteWattBatterySettingsSensor(
            coordinator, 
            entry, 
            SENSOR_CHARGE_END, 
            "Charge End Time", 
            "timestamp", 
            "time_chae1a", 
            "", 
            "mdi:battery-plus-outline"
        ),
        ByteWattBatterySettingsSensor(
            coordinator, 
            entry, 
            SENSOR_MIN_SOC, 
            "Minimum SOC", 
            "battery", 
            "bat_use_cap", 
            "%", 
            "mdi:battery-low"
        ),
    ]
    
    async_add_entities(soc_sensors + grid_sensors + battery_settings_sensors)


class ByteWattSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Byte-Watt Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
        name: str,
        device_class: str,
        attribute: str,
        unit: str,
        icon: str,
        entity_category: Optional[EntityCategory] = None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = entity_category

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": f"Byte-Watt Battery ({self._config_entry.data.get('username')})",
            "manufacturer": "Byte-Watt",
            "model": "Battery Monitor",
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "soc" not in self.coordinator.data:
                return None
            
            soc_data = self.coordinator.data["soc"]
            return soc_data.get(self._attribute)
        except Exception as ex:
            _LOGGER.error(f"Error getting sensor state: {ex}")
            return None


class ByteWattGridSensor(ByteWattSensor):
    """Representation of a Byte-Watt Grid Sensor."""

    def __init__(
        self,
        coordinator,
        config_entry,
        sensor_type,
        name,
        device_class,
        attribute,
        unit,
        icon,
        entity_category=None,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator, 
            config_entry, 
            sensor_type, 
            name, 
            device_class, 
            attribute, 
            unit, 
            icon,
            entity_category
        )
        # Add state_class for energy sensors (kWh)
        if unit == "kWh":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data or "grid" not in self.coordinator.data:
                return None
            
            grid_data = self.coordinator.data["grid"]
            return grid_data.get(self._attribute)
        except Exception as ex:
            _LOGGER.error(f"Error getting grid sensor state: {ex}")
            return None


class ByteWattBatterySettingsSensor(ByteWattSensor):
    """Representation of a Byte-Watt Battery Settings Sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            settings = client._settings_cache
            
            if settings:
                return settings.get(self._attribute)
            return None
        except Exception as ex:
            _LOGGER.error(f"Error getting battery settings sensor state: {ex}")
            return None
