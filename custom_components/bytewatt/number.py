"""Number entities for the Byte-Watt integration."""
import logging
from typing import Optional

from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ByteWattDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Byte-Watt number entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = [
        ByteWattMinimumSOCNumber(coordinator, config_entry),
        ByteWattChargeCapNumber(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ByteWattNumberEntity(CoordinatorEntity, NumberEntity):
    """Base class for Byte-Watt number entities."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_id: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        device_class: Optional[NumberDeviceClass] = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_class = device_class
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "ByteWatt Battery System",
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }


class ByteWattMinimumSOCNumber(ByteWattNumberEntity):
    """Number entity for minimum state of charge."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the minimum SOC number entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Minimum SOC",
            unique_id="minimum_soc",
            icon="mdi:battery-low",
            min_value=5,
            max_value=95,
            step=1,
            device_class=NumberDeviceClass.BATTERY,
        )
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> Optional[float]:
        """Return the current minimum SOC value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                return float(getattr(settings, "bat_use_cap", 6))
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting minimum SOC value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the minimum SOC value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            success = await client.update_battery_settings(minimum_soc=int(value))
            if success:
                _LOGGER.info(f"Successfully updated minimum SOC to {value}%")
                # Trigger coordinator refresh to update other entities
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update minimum SOC to {value}%")
        except Exception as ex:
            _LOGGER.error(f"Error setting minimum SOC to {value}%: {ex}")


class ByteWattChargeCapNumber(ByteWattNumberEntity):
    """Number entity for battery charge cap."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the charge cap number entity."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Battery Charge Cap",
            unique_id="charge_cap",
            icon="mdi:battery-high",
            min_value=50,
            max_value=100,
            step=1,
            device_class=NumberDeviceClass.BATTERY,
        )
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> Optional[float]:
        """Return the current charge cap value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if hasattr(client.api_client, "_settings_cache") and client.api_client._settings_cache:
                settings = client.api_client._settings_cache
                value = getattr(settings, "bat_high_cap", "100")
                return float(value) if isinstance(value, (str, int, float)) else 100.0
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(f"Error getting charge cap value: {ex}")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the charge cap value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            success = await client.update_battery_settings(charge_cap=int(value))
            if success:
                _LOGGER.info(f"Successfully updated charge cap to {value}%")
                # Trigger coordinator refresh to update other entities
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update charge cap to {value}%")
        except Exception as ex:
            _LOGGER.error(f"Error setting charge cap to {value}%: {ex}")