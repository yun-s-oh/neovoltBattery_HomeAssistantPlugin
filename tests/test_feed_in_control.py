"""Unit tests for the Grid Feed-in Control entities and data models."""

import sys
import os
from datetime import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add parent directory to path to import local modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.bytewatt.models import FeedStrategySettings, FeedStrategySchedule
from custom_components.bytewatt.switch import ByteWattGridFeedInControlSwitch
from custom_components.bytewatt.time import (
    ByteWattFeedInStartTime1,
    ByteWattFeedInEndTime1,
    ByteWattFeedInStartTime2,
    ByteWattFeedInEndTime2,
)
from custom_components.bytewatt.number import (
    ByteWattFeedInPower1,
    ByteWattFeedInPower2,
    ByteWattDischargingCutoffSOCNumber,
)


def test_feed_strategy_settings_parsing():
    """Test successful parsing of feed strategy API response."""
    raw_data = {
        "batteryEn": 1,
        "batteryFeedCutoffSoc": 10.0,
        "id": "sys_12345",
        "prechargeEn": 0,
        "poinv": 4600.0,
        "feedStrategyVOList": [
            {
                "id": 101,
                "sysSn": "SN123",
                "start": "09:00",
                "end": "11:00",
                "feedPower": 2000.0,
                "sort": 1,
            },
            {
                "id": 102,
                "sysSn": "SN123",
                "start": "13:30",
                "end": "15:00",
                "feedPower": 3000.0,
                "sort": 2,
            },
        ],
    }

    settings = FeedStrategySettings.from_api_response(raw_data)

    assert settings.battery_en == 1
    assert settings.battery_feed_cutoff_soc == 10.0
    assert settings.id == "sys_12345"
    assert settings.precharge_en == 0
    assert settings.poinv == 4600.0
    assert len(settings.feed_strategy_list) == 2

    # Verify Schedule 1
    sched1 = settings.get_schedule_by_sort(1)
    assert sched1.id == 101
    assert sched1.sys_sn == "SN123"
    assert sched1.start == "09:00"
    assert sched1.end == "11:00"
    assert sched1.feed_power == 2000.0
    assert sched1.sort == 1

    # Verify Schedule 2
    sched2 = settings.get_schedule_by_sort(2)
    assert sched2.id == 102
    assert sched2.sys_sn == "SN123"
    assert sched2.start == "13:30"
    assert sched2.end == "15:00"
    assert sched2.feed_power == 3000.0
    assert sched2.sort == 2


def test_feed_strategy_settings_defaults():
    """Test defaults when feedStrategyVOList is empty or missing specific sorts."""
    # Test completely empty response data
    settings = FeedStrategySettings.from_api_response({})
    assert settings.battery_en == 0
    assert settings.poinv == 5000.0  # fallback poinv

    # Check that sorting defaults are applied as requested
    sched1 = settings.get_schedule_by_sort(1)
    assert sched1.start == "00:00"
    assert sched1.end == "00:00"
    assert sched1.feed_power == 0.0
    assert sched1.sort == 1

    sched2 = settings.get_schedule_by_sort(2)
    assert sched2.start == "00:00"
    assert sched2.end == "00:00"
    assert sched2.feed_power == 0.0
    assert sched2.sort == 2


@pytest.mark.asyncio
async def test_grid_feed_in_control_switch():
    """Test the grid feed-in control switch entity."""
    coordinator = MagicMock()
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"serial_number": "SN12345", "username": "test_user"}

    # Mock Hass and Client
    hass = MagicMock()
    client = MagicMock()
    client.api_client = MagicMock()
    client.update_feed_strategy = AsyncMock(return_value=True)
    
    hass.data = {"bytewatt": {"test_entry": {"client": client}}}

    switch = ByteWattGridFeedInControlSwitch(coordinator, config_entry)
    switch.hass = hass

    # Test state when cache is missing
    client.api_client._feed_strategy_cache = None
    assert switch.is_on is False
    assert switch.available is False

    # Test state when cache is active
    cache = FeedStrategySettings(battery_en=1, poinv=4000.0)
    client.api_client._feed_strategy_cache = cache
    assert switch.is_on is True
    assert switch.available is True

    # Test turn off
    await switch.async_turn_off()
    client.update_feed_strategy.assert_called_once_with(sys_sn="SN12345", battery_en=False)
    coordinator.async_request_refresh.assert_called_once()

    # Test turn on
    client.update_feed_strategy.reset_mock()
    coordinator.async_request_refresh.reset_mock()
    await switch.async_turn_on()
    client.update_feed_strategy.assert_called_once_with(sys_sn="SN12345", battery_en=True)
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_feed_in_time_entities():
    """Test feed-in start and end time entities."""
    coordinator = MagicMock()
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"serial_number": "SN12345", "username": "test_user"}

    hass = MagicMock()
    client = MagicMock()
    client.api_client = MagicMock()
    client.update_feed_strategy = AsyncMock(return_value=True)
    hass.data = {"bytewatt": {"test_entry": {"client": client}}}

    # Setup cached settings with sort 1 schedule
    cache = FeedStrategySettings(
        battery_en=1,
        feed_strategy_list=[
            FeedStrategySchedule(start="08:30", end="10:15", feed_power=1500.0, sort=1)
        ],
    )
    client.api_client._feed_strategy_cache = cache

    # 1. Test Start Time 1 (exist in cache)
    time_start_1 = ByteWattFeedInStartTime1(coordinator, config_entry)
    time_start_1.hass = hass
    assert time_start_1.native_value == time(8, 30)

    # 2. Test End Time 1 (exist in cache)
    time_end_1 = ByteWattFeedInEndTime1(coordinator, config_entry)
    time_end_1.hass = hass
    assert time_end_1.native_value == time(10, 15)

    # 3. Test Start Time 2 (does NOT exist in cache -> defaults to 00:00)
    time_start_2 = ByteWattFeedInStartTime2(coordinator, config_entry)
    time_start_2.hass = hass
    assert time_start_2.native_value == time(0, 0)

    # Test set start time value
    await time_start_1.async_set_value(time(9, 45))
    client.update_feed_strategy.assert_called_once_with(
        sys_sn="SN12345", schedule_sort=1, start="09:45"
    )

    # Test set end time value
    client.update_feed_strategy.reset_mock()
    await time_end_1.async_set_value(time(11, 30))
    client.update_feed_strategy.assert_called_once_with(
        sys_sn="SN12345", schedule_sort=1, end="11:30"
    )


@pytest.mark.asyncio
async def test_feed_in_power_number_entities():
    """Test feed-in power number entities."""
    coordinator = MagicMock()
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"serial_number": "SN12345", "username": "test_user"}

    hass = MagicMock()
    client = MagicMock()
    client.api_client = MagicMock()
    client.update_feed_strategy = AsyncMock(return_value=True)
    hass.data = {"bytewatt": {"test_entry": {"client": client}}}

    # Setup cached settings with sort 2 schedule, poinv = 4600W
    cache = FeedStrategySettings(
        battery_en=1,
        poinv=4600.0,
        feed_strategy_list=[
            FeedStrategySchedule(start="13:00", end="14:00", feed_power=2500.0, sort=2)
        ],
    )
    client.api_client._feed_strategy_cache = cache

    # 1. Test Power 1 (does NOT exist -> defaults to 0)
    power_1 = ByteWattFeedInPower1(coordinator, config_entry)
    power_1.hass = hass
    assert power_1.native_value == 0.0
    assert power_1.native_max_value == 4600.0

    # 2. Test Power 2 (exists -> 2500.0)
    power_2 = ByteWattFeedInPower2(coordinator, config_entry)
    power_2.hass = hass
    assert power_2.native_value == 2500.0
    assert power_2.native_max_value == 4600.0

    # Test setting value
    await power_2.async_set_native_value(3000.0)
    client.update_feed_strategy.assert_called_once_with(
        sys_sn="SN12345", schedule_sort=2, feed_power=3000
    )


@pytest.mark.asyncio
async def test_discharging_cutoff_soc_number_entity():
    """Test the discharging cutoff SOC number entity."""
    coordinator = MagicMock()
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"serial_number": "SN12345", "username": "test_user"}

    hass = MagicMock()
    client = MagicMock()
    client.api_client = MagicMock()
    client.update_feed_strategy = AsyncMock(return_value=True)
    hass.data = {"bytewatt": {"test_entry": {"client": client}}}

    # Setup cached settings with cutoff SOC = 15%
    cache = FeedStrategySettings(
        battery_en=1,
        battery_feed_cutoff_soc=15.0,
    )
    client.api_client._feed_strategy_cache = cache

    cutoff_entity = ByteWattDischargingCutoffSOCNumber(coordinator, config_entry)
    cutoff_entity.hass = hass

    # Test state when cache has value
    assert cutoff_entity.native_value == 15.0
    assert cutoff_entity.native_min_value == 5.0
    assert cutoff_entity.native_max_value == 100.0
    assert cutoff_entity.available is True

    # Test state when cache is missing cutoff SOC
    cache.battery_feed_cutoff_soc = None
    assert cutoff_entity.native_value == 100.0  # Defaults to 100

    # Test setting value
    await cutoff_entity.async_set_native_value(20.0)
    client.update_feed_strategy.assert_called_once_with(
        sys_sn="SN12345", cutoff_soc=20.0
    )


@pytest.mark.asyncio
async def test_neovolt_client_update_feed_strategy_normalization():
    """Test that async_update_feed_strategy normalizes sys_sn in all cached schedules."""
    from custom_components.bytewatt.api.neovolt_client import NeovoltClient

    # Mock hass, session and API
    hass = MagicMock()
    client = NeovoltClient(hass, "test_user", "test_pass", system_id="sys_123")

    # Pre-populate client cache with schedules having empty sys_sn
    cache = FeedStrategySettings(
        battery_en=0,
        battery_feed_cutoff_soc=10.0,
        feed_strategy_list=[
            FeedStrategySchedule(
                id=None, sys_sn="", start="00:00", end="00:00", feed_power=0.0, sort=1
            ),
            FeedStrategySchedule(
                id=None, sys_sn="", start="00:00", end="00:00", feed_power=0.0, sort=2
            ),
        ]
    )
    client._feed_strategy_cache = cache

    # Mock BatterySettingsAPI to assert save_feed_strategy receives normalized settings
    with patch(
        "custom_components.bytewatt.api.settings.BatterySettingsAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.save_feed_strategy = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        # Disable auto-fetch task
        with patch.object(client, "_auto_fetch_updated_feed_strategy", return_value=None):
            success = await client.async_update_feed_strategy(
                sys_sn="SN_REAL_123",
                schedule_sort=1,
                start="12:00"
            )

            assert success is True
            # Verify BatterySettingsAPI.save_feed_strategy was called with normalized settings
            mock_api.save_feed_strategy.assert_called_once()
            saved_settings = mock_api.save_feed_strategy.call_args[0][0]

            # Both schedules should have been normalized to "SN_REAL_123"
            for sched in saved_settings.feed_strategy_list:
                assert sched.sys_sn == "SN_REAL_123"
