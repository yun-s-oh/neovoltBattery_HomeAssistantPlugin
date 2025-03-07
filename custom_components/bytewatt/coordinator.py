"""Data update coordinator for Byte-Watt integration."""
import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval

from .bytewatt_client import ByteWattClient

_LOGGER = logging.getLogger(__name__)

# Constants for heartbeat monitoring
HEARTBEAT_INTERVAL = 120  # Check every 2 minutes
MAX_DATA_AGE = 300  # Consider data stale after 5 minutes
STALE_DATA_THRESHOLD = 3  # Number of consecutive stale data checks before forced recovery


class ByteWattDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Byte-Watt data with improved error handling and recovery."""

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
        self._scan_interval = scan_interval
        self._last_successful_update: Optional[datetime] = None
        self._consecutive_stale_checks = 0
        self._recovery_in_progress = False
        self._heartbeat_unsub = None
        self._recovery_attempts = 0

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
            
            # If we got SOC data, update our cached version and last successful time
            if soc_data:
                self._last_soc_data = soc_data
                self._last_successful_update = datetime.now()
                self._consecutive_stale_checks = 0
                self._recovery_attempts = 0  # Reset recovery attempts on successful update
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
    
    async def start_heartbeat(self) -> None:
        """Start the heartbeat service to monitor and recover the integration."""
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
        
        self._heartbeat_unsub = async_track_time_interval(
            self.hass,
            self._async_heartbeat_check,
            timedelta(seconds=HEARTBEAT_INTERVAL)
        )
        _LOGGER.debug("ByteWatt heartbeat monitoring started")
    
    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat service."""
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
            self._heartbeat_unsub = None
            _LOGGER.debug("ByteWatt heartbeat monitoring stopped")
    
    @callback
    async def _async_heartbeat_check(self, _now: Optional[datetime] = None) -> None:
        """Check if the integration is still alive and recover if needed."""
        # Convert callback to a normal async function
        await self._check_and_recover(_now)
    
    async def _check_and_recover(self, _now: Optional[datetime] = None) -> None:
        """Internal method to check data freshness and recover if needed."""
        # Skip check if recovery is already in progress
        if self._recovery_in_progress:
            return
        
        now = datetime.now()
        
        # No successful update recorded yet
        if self._last_successful_update is None:
            _LOGGER.debug("No successful update recorded yet")
            # Try to trigger an update if we have no data yet
            if self._last_soc_data is None:
                await self._perform_recovery()
            return
        
        # Calculate age of data
        data_age = now - self._last_successful_update
        
        # Check if data is stale
        if data_age.total_seconds() > MAX_DATA_AGE:
            self._consecutive_stale_checks += 1
            _LOGGER.warning(
                f"ByteWatt data is stale (age: {data_age.total_seconds():.1f}s). "
                f"Stale checks: {self._consecutive_stale_checks}/{STALE_DATA_THRESHOLD}"
            )
            
            # If we've reached the threshold, attempt recovery
            if self._consecutive_stale_checks >= STALE_DATA_THRESHOLD:
                await self._perform_recovery()
        else:
            # Data is fresh, reset counter
            self._consecutive_stale_checks = 0
    
    async def _perform_recovery(self) -> None:
        """Perform recovery actions when data updates have stopped."""
        self._recovery_in_progress = True
        self._recovery_attempts += 1
        _LOGGER.warning(f"Performing ByteWatt integration recovery (attempt {self._recovery_attempts})")
        
        try:
            # Step 1: Reset client state
            await self.hass.async_add_executor_job(self._reset_client)
            
            # Step 2: Force immediate data refresh
            await self.async_refresh()
            
            _LOGGER.info("ByteWatt integration recovery completed successfully")
        except Exception as err:
            _LOGGER.error(f"ByteWatt recovery failed: {err}")
            
            # Apply exponential backoff for retry frequency based on attempt count
            backoff_factor = min(5, self._recovery_attempts)  # Cap at 5x
            next_check_seconds = HEARTBEAT_INTERVAL // backoff_factor
            
            _LOGGER.info(f"Will attempt recovery again in {next_check_seconds} seconds")
            
            # Schedule a sooner check if needed
            if backoff_factor > 1:
                async_call_later = getattr(self.hass, "async_call_later", None)
                if async_call_later:
                    async_call_later(
                        next_check_seconds, 
                        lambda _: asyncio.create_task(self._check_and_recover(None))
                    )
        finally:
            self._recovery_in_progress = False
    
    def _reset_client(self) -> None:
        """Reset client state to force reauthentication and session cleanup."""
        try:
            # Reset auth tokens
            if hasattr(self.client, 'auth') and hasattr(self.client.auth, 'access_token'):
                self.client.auth.access_token = None
            
            # Reset session if available
            if hasattr(self.client, 'session'):
                try:
                    self.client.session.close()
                except:
                    pass
                self.client.session = None
            
            # Try to recreate session and get new token if needed
            if hasattr(self.client, 'initialize'):
                self.client.initialize()
            
            # Force authentication attempt
            self.client.ensure_authenticated()
            
            _LOGGER.info("ByteWatt client state has been reset")
        except Exception as err:
            _LOGGER.error(f"Error resetting ByteWatt client: {err}")
            raise