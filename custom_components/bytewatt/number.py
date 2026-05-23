"""Number entities for the Byte-Watt integration."""

import logging
from typing import Optional

from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SERIAL_NUMBER,
    SENSOR_FEED_IN_POWER_1,
    SENSOR_FEED_IN_POWER_2,
    SENSOR_FEED_IN_CUTOFF_SOC,
)
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
        ByteWattChargeCapNumber(coordinator, config_entry),
        ByteWattMinimumSOCNumber(coordinator, config_entry),
    ]

    sys_sn = config_entry.data.get(CONF_SERIAL_NUMBER, "All")
    if sys_sn != "All":
        entities.extend([
            ByteWattFeedInPower1(coordinator, config_entry),
            ByteWattFeedInPower2(coordinator, config_entry),
            ByteWattDischargingCutoffSOCNumber(coordinator, config_entry),
        ])

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
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")
        self._friendly_name = name
        if sys_sn != "All":
            self._attr_name = f"{name} {sys_sn}"
            self._attr_unique_id = (
                f"{config_entry.entry_id}_{unique_id}_{sys_sn.lower()}"
            )
        else:
            self._attr_name = name
            self._attr_unique_id = f"{config_entry.entry_id}_{unique_id}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_class = device_class
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def name(self) -> str:
        """Return the friendly name of the number entity."""
        return self._friendly_name

    @property
    def device_info(self):
        """Return device info."""
        username = self._config_entry.data.get("username", "Unknown")
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")

        device_name = f"Byte-Watt Battery ({username}) - {sys_sn}"

        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": device_name,
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
            if (
                hasattr(client.api_client, "_settings_cache")
                and client.api_client._settings_cache
            ):
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
            if (
                hasattr(client.api_client, "_settings_cache")
                and client.api_client._settings_cache
            ):
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


class ByteWattFeedInPowerNumber(NumberEntity, CoordinatorEntity):
    """Base class for Byte-Watt feed-in power number entities."""

    def __init__(
        self,
        coordinator: ByteWattDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        unique_id: str,
        sort_order: int,
    ) -> None:
        """Initialize the feed-in power number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")
        self._friendly_name = name
        self._attr_name = f"{name} {sys_sn}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{unique_id}_{sys_sn.lower()}"
        )
        self._attr_icon = "mdi:home-export-outline"
        self._attr_native_step = 100.0
        self._attr_native_unit_of_measurement = "W"
        self._attr_entity_category = EntityCategory.CONFIG
        self._sort_order = sort_order

    @property
    def name(self) -> str:
        """Return the friendly name of the number entity."""
        return self._friendly_name

    @property
    def device_info(self):
        """Return device info."""
        username = self._config_entry.data.get("username", "Unknown")
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")
        device_name = f"Byte-Watt Battery ({username}) - {sys_sn}"
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": device_name,
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return 0.0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value, based on poinv."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if (
                hasattr(client.api_client, "_feed_strategy_cache")
                and client.api_client._feed_strategy_cache
            ):
                return float(client.api_client._feed_strategy_cache.poinv)
        except Exception:
            pass
        return 5000.0

    @property
    def native_value(self) -> Optional[float]:
        """Return the current feed-in power value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if (
                hasattr(client.api_client, "_feed_strategy_cache")
                and client.api_client._feed_strategy_cache
            ):
                settings = client.api_client._feed_strategy_cache
                sched = settings.get_schedule_by_sort(self._sort_order)
                return float(sched.feed_power)
        except Exception as ex:
            _LOGGER.debug(f"Error getting feed-in power: {ex}")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            return (
                hasattr(client.api_client, "_feed_strategy_cache")
                and client.api_client._feed_strategy_cache is not None
            )
        except Exception:
            return False

    async def async_set_native_value(self, value: float) -> None:
        """Set the feed-in power value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER)
            success = await client.update_feed_strategy(
                sys_sn=sys_sn, schedule_sort=self._sort_order, feed_power=int(value)
            )
            if success:
                _LOGGER.info(f"Successfully updated {self._friendly_name} to {value}W")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update {self._friendly_name} to {value}W")
        except Exception as ex:
            _LOGGER.error(f"Error setting {self._friendly_name} to {value}W: {ex}")


class ByteWattFeedInPower1(ByteWattFeedInPowerNumber):
    """Number entity for feed-in power 1."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the feed-in power 1."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Feed-in Power 1",
            unique_id=SENSOR_FEED_IN_POWER_1,
            sort_order=1,
        )


class ByteWattFeedInPower2(ByteWattFeedInPowerNumber):
    """Number entity for feed-in power 2."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the feed-in power 2."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            name="Feed-in Power 2",
            unique_id=SENSOR_FEED_IN_POWER_2,
            sort_order=2,
        )


class ByteWattDischargingCutoffSOCNumber(NumberEntity, CoordinatorEntity):
    """Number entity for discharging cutoff state of charge (feed strategy)."""

    def __init__(
        self, coordinator: ByteWattDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the discharging cutoff SOC number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")
        self._friendly_name = "Discharging Cutoff SOC"
        self._attr_name = f"{self._friendly_name} {sys_sn}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{SENSOR_FEED_IN_CUTOFF_SOC}_{sys_sn.lower()}"
        )
        self._attr_icon = "mdi:battery-alert"
        self._attr_native_step = 1.0
        self._attr_native_unit_of_measurement = "%"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def name(self) -> str:
        """Return the friendly name of the number entity."""
        return self._friendly_name

    @property
    def device_info(self):
        """Return device info."""
        username = self._config_entry.data.get("username", "Unknown")
        sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER, "All")
        device_name = f"Byte-Watt Battery ({username}) - {sys_sn}"
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": device_name,
            "manufacturer": "ByteWatt",
            "model": "Battery Management System",
            "sw_version": "1.0.0",
        }

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return 5.0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return 100.0

    @property
    def native_value(self) -> Optional[float]:
        """Return the current discharging cutoff SOC value.

        Defaults to 100 if the value is empty or not present in feed strategy settings.
        """
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            if (
                hasattr(client.api_client, "_feed_strategy_cache")
                and client.api_client._feed_strategy_cache
            ):
                val = client.api_client._feed_strategy_cache.battery_feed_cutoff_soc
                if val is None:
                    return 100.0
                return float(val)
        except Exception as ex:
            _LOGGER.debug(f"Error getting discharging cutoff SOC: {ex}")
        return 100.0

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            return (
                hasattr(client.api_client, "_feed_strategy_cache")
                and client.api_client._feed_strategy_cache is not None
            )
        except Exception:
            return False

    async def async_set_native_value(self, value: float) -> None:
        """Set the discharging cutoff SOC value."""
        try:
            client = self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
            sys_sn = self._config_entry.data.get(CONF_SERIAL_NUMBER)
            success = await client.update_feed_strategy(
                sys_sn=sys_sn, cutoff_soc=float(value)
            )
            if success:
                _LOGGER.info(f"Successfully updated discharging cutoff SOC to {value}%")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to update discharging cutoff SOC to {value}%")
        except Exception as ex:
            _LOGGER.error(f"Error setting discharging cutoff SOC to {value}%: {ex}")
