"""Data update coordinator for Byte-Watt integration."""
import logging
import time
import json
import asyncio
import socket
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set
from enum import Enum
import statistics
from contextlib import contextmanager

from homeassistant.core import HomeAssistant, callback, Context
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MAX_DATA_AGE,
    CONF_STALE_CHECKS_THRESHOLD,
    CONF_NOTIFY_ON_RECOVERY,
    CONF_DIAGNOSTICS_MODE,
    CONF_AUTO_RECONNECT_TIME,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_MAX_DATA_AGE,
    DEFAULT_STALE_CHECKS_THRESHOLD,
    DEFAULT_NOTIFY_ON_RECOVERY,
    DEFAULT_DIAGNOSTICS_MODE,
    DEFAULT_AUTO_RECONNECT_TIME,
)

_LOGGER = logging.getLogger(__name__)

# Notification IDs
NOTIFICATION_RECOVERY = "bytewatt_recovery"
NOTIFICATION_ERROR = "bytewatt_error"

# Circuit breaker states
class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"      # Error threshold reached, no requests allowed
    HALF_OPEN = "half_open"  # Testing if service is back online


class ConnectionStatistics:
    """Track connection health statistics for circuit breaker pattern."""
    
    def __init__(self, window_size: int = 10):
        """Initialize connection statistics."""
        self.window_size = window_size
        self.success_history: List[bool] = []
        self.response_times: List[float] = []
        self.error_types: Dict[str, int] = {}
        self.last_success_time: Optional[datetime] = None
        self.last_error_time: Optional[datetime] = None
        self.last_error_message: Optional[str] = None
    
    def record_success(self, response_time: float):
        """Record a successful API call."""
        self.success_history.append(True)
        self.response_times.append(response_time)
        self.last_success_time = datetime.now()
        
        # Trim history to window size
        if len(self.success_history) > self.window_size:
            self.success_history = self.success_history[-self.window_size:]
            self.response_times = self.response_times[-self.window_size:]
    
    def record_failure(self, error_type: str, error_message: str):
        """Record a failed API call."""
        self.success_history.append(False)
        self.last_error_time = datetime.now()
        self.last_error_message = error_message
        
        # Record error type
        if error_type in self.error_types:
            self.error_types[error_type] += 1
        else:
            self.error_types[error_type] = 1
        
        # Trim history to window size
        if len(self.success_history) > self.window_size:
            self.success_history = self.success_history[-self.window_size:]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate over the window."""
        if not self.success_history:
            return 1.0  # Default to 100% if no history
        
        return sum(1 for x in self.success_history if x) / len(self.success_history)
    
    @property
    def avg_response_time(self) -> Optional[float]:
        """Calculate average response time over the window."""
        if not self.response_times:
            return None
        
        return sum(self.response_times) / len(self.response_times)
    
    @property
    def most_common_error(self) -> Optional[Tuple[str, int]]:
        """Get the most common error type."""
        if not self.error_types:
            return None
        
        return max(self.error_types.items(), key=lambda x: x[1])
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate a status report of connection health."""
        return {
            "success_rate": f"{self.success_rate:.2%}",
            "avg_response_time": f"{self.avg_response_time:.2f}s" if self.avg_response_time else "N/A",
            "most_common_error": self.most_common_error[0] if self.most_common_error else "None",
            "error_count": sum(self.error_types.values()),
            "last_success": self.last_success_time.isoformat() if self.last_success_time else "Never",
            "last_error": self.last_error_time.isoformat() if self.last_error_time else "Never",
            "last_error_message": self.last_error_message or "None"
        }


class CircuitBreaker:
    """Implements circuit breaker pattern for API calls."""
    
    def __init__(
        self, 
        failure_threshold: float = 0.5,
        recovery_timeout: int = 300,
        half_open_timeout: int = 60
    ):
        """Initialize circuit breaker with configurable thresholds."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_threshold = failure_threshold  # 50% failure rate by default
        self.recovery_timeout = recovery_timeout  # 5 minutes by default
        self.half_open_timeout = half_open_timeout  # 1 minute by default
        self.last_state_change = datetime.now()
        self.stats = ConnectionStatistics()
    
    def record_success(self, response_time: float):
        """Record a successful API call."""
        self.stats.record_success(response_time)
        
        # If we're in half-open state and got a success, close the circuit
        if self.state == CircuitBreakerState.HALF_OPEN:
            _LOGGER.info("Circuit breaker transitioning from HALF_OPEN to CLOSED after successful response")
            self.state = CircuitBreakerState.CLOSED
            self.last_state_change = datetime.now()
    
    def record_failure(self, error_type: str, error_message: str):
        """Record a failed API call."""
        self.stats.record_failure(error_type, error_message)
        
        # If success rate drops below threshold, open the circuit
        if (self.state == CircuitBreakerState.CLOSED and 
            len(self.stats.success_history) >= 3 and  # Need at least 3 data points
            self.stats.success_rate < self.failure_threshold):
            
            _LOGGER.warning(
                "Circuit breaker transitioning from CLOSED to OPEN: "
                f"success rate ({self.stats.success_rate:.2%}) below threshold ({self.failure_threshold:.2%})"
            )
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.now()
        
        # If we're in half-open state and got a failure, back to open
        elif self.state == CircuitBreakerState.HALF_OPEN:
            _LOGGER.warning("Circuit breaker transitioning from HALF_OPEN to OPEN after failed response")
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.now()
    
    def check_state_transition(self):
        """Check if circuit breaker state should transition based on timeouts."""
        now = datetime.now()
        
        # If circuit is open and recovery timeout has passed, try half-open
        if (self.state == CircuitBreakerState.OPEN and 
            (now - self.last_state_change).total_seconds() > self.recovery_timeout):
            
            _LOGGER.info(
                f"Circuit breaker transitioning from OPEN to HALF_OPEN after {self.recovery_timeout}s timeout"
            )
            self.state = CircuitBreakerState.HALF_OPEN
            self.last_state_change = now
    
    def can_execute(self) -> bool:
        """Check if the API call should be allowed based on circuit state."""
        self.check_state_transition()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # In half-open state, allow one request to test the service
            return True
        else:  # OPEN
            return False
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate a status report of circuit breaker health."""
        state_duration = (datetime.now() - self.last_state_change).total_seconds()
        
        report = {
            "state": self.state.value,
            "state_duration": f"{state_duration:.0f}s",
            "failure_threshold": f"{self.failure_threshold:.2%}",
            "recovery_timeout": f"{self.recovery_timeout}s",
        }
        
        # Add connection statistics
        report.update(self.stats.get_status_report())
        
        return report


class ByteWattDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Byte-Watt data with improved error handling and recovery."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ByteWattClient,
        scan_interval: int,
        entry_id: str,
        options: Dict[str, Any] = None,
    ):
        """Initialize."""
        self.client = client
        self.hass = hass
        self.entry_id = entry_id
        self._last_battery_data = None
        self._scan_interval = scan_interval
        self._last_successful_update: Optional[datetime] = None
        self._consecutive_stale_checks = 0
        self._recovery_in_progress = False
        self._heartbeat_unsub = None
        self._recovery_attempts = 0
        self._auto_reconnect_unsub = None
        self._diagnostics_enabled = False
        self._webhook_id = None
        self._webhook_unsub = None
        self._diagnostic_logs: List[Dict[str, Any]] = []
        self._max_diagnostic_logs = 100
        
        # Connection health tracking
        self.circuit_breaker = CircuitBreaker()
        
        # Load options
        options = options or {}
        self._heartbeat_interval = options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL)
        self._max_data_age = options.get(CONF_MAX_DATA_AGE, DEFAULT_MAX_DATA_AGE)
        self._stale_checks_threshold = options.get(CONF_STALE_CHECKS_THRESHOLD, DEFAULT_STALE_CHECKS_THRESHOLD)
        self._notify_on_recovery = options.get(CONF_NOTIFY_ON_RECOVERY, DEFAULT_NOTIFY_ON_RECOVERY)
        self._diagnostics_mode = options.get(CONF_DIAGNOSTICS_MODE, DEFAULT_DIAGNOSTICS_MODE)
        self._auto_reconnect_time = options.get(CONF_AUTO_RECONNECT_TIME, DEFAULT_AUTO_RECONNECT_TIME)
        
        if self._diagnostics_mode:
            self._enable_diagnostics()

        super().__init__(
            hass,
            _LOGGER,
            name="bytewatt",
            update_interval=timedelta(seconds=scan_interval),
        )

    def _enable_diagnostics(self):
        """Enable diagnostic logging mode."""
        self._diagnostics_enabled = True
        _LOGGER.info("ByteWatt diagnostic logging mode enabled")
    
    def _disable_diagnostics(self):
        """Disable diagnostic logging mode."""
        self._diagnostics_enabled = False
        self._diagnostic_logs.clear()
        _LOGGER.info("ByteWatt diagnostic logging mode disabled")
    
    def _log_diagnostic(self, event_type: str, details: Dict[str, Any]):
        """Log a diagnostic event."""
        if not self._diagnostics_enabled:
            return
            
        # Add timestamp and event type
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **details
        }
        
        self._diagnostic_logs.append(event)
        
        # Trim log if needed
        if len(self._diagnostic_logs) > self._max_diagnostic_logs:
            self._diagnostic_logs = self._diagnostic_logs[-self._max_diagnostic_logs:]
    
    @contextmanager
    def _timed_operation(self, operation_name: str):
        """Context manager for timing operations and recording diagnostics."""
        start_time = time.time()
        error = None
        
        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            if self._diagnostics_enabled:
                details = {
                    "operation": operation_name,
                    "duration": f"{duration:.3f}s",
                    "success": error is None
                }
                
                if error:
                    details["error"] = str(error)
                    details["error_type"] = type(error).__name__
                
                self._log_diagnostic("operation", details)
                
                # Record in circuit breaker stats
                if error:
                    self.circuit_breaker.record_failure(
                        type(error).__name__, 
                        str(error)
                    )
                else:
                    self.circuit_breaker.record_success(duration)
    
    async def _async_update_data(self):
        """Update data via library with improved error handling."""
        try:
            # Check if circuit breaker allows execution
            if not self.circuit_breaker.can_execute():
                _LOGGER.warning(
                    f"Circuit breaker is {self.circuit_breaker.state.value}, using cached data"
                )
                self._log_diagnostic("circuit_breaker_blocked", {
                    "state": self.circuit_breaker.state.value,
                    "stats": self.circuit_breaker.get_status_report()
                })
                
                # Use cached data if available
                if self._last_battery_data:
                    return {
                        "battery": self._last_battery_data,
                        "connection_status": "limited",
                        "circuit_breaker": self.circuit_breaker.state.value
                    }
                else:
                    raise UpdateFailed(
                        f"Circuit breaker is {self.circuit_breaker.state.value} and no cached data available"
                    )
            
            # Get battery data
            with self._timed_operation("get_battery_data"):
                battery_data = await self.client.get_battery_data()
            
            # If we got battery data, update our cached version and last successful time
            if battery_data:
                self._last_battery_data = battery_data
                self._last_successful_update = datetime.now()
                self._consecutive_stale_checks = 0
                self._recovery_attempts = 0  # Reset recovery attempts on successful update
                
                self._log_diagnostic("data_update", {
                    "type": "battery_data",
                    "result": "success"
                })
            elif self._last_battery_data is None:
                # Only raise error if we never got data
                error_msg = "Failed to get battery data and no cached data available"
                self._log_diagnostic("data_update", {
                    "type": "battery_data",
                    "result": "failure",
                    "error": error_msg
                })
                raise UpdateFailed(error_msg)
            else:
                _LOGGER.warning("Using cached battery data due to API error")
                self._log_diagnostic("data_update", {
                    "type": "battery_data",
                    "result": "fallback_to_cache"
                })
            
            # If we got here successfully, ensure any error notifications are dismissed
            if self._notify_on_recovery:
                try:
                    await self.hass.components.persistent_notification.async_dismiss(NOTIFICATION_ERROR)
                except (AttributeError, TypeError):
                    _LOGGER.debug("Could not dismiss notification - may not exist yet")
            
            # Return the data along with connection status
            data = {
                "battery": self._last_battery_data or {},
                "connection_status": "connected" if battery_data else "partial",
                "circuit_breaker": self.circuit_breaker.state.value,
                "last_updated": datetime.now().isoformat()
            }
            
            _LOGGER.debug(f"Coordinator data refreshed with keys: {list(data.keys())}")
            return data
        except Exception as err:
            # Record the error in diagnostics
            self._log_diagnostic("update_error", {
                "error_type": type(err).__name__,
                "error_message": str(err)
            })
            
            # If we have cached data, use it rather than failing
            if self._last_battery_data:
                _LOGGER.error(f"Error communicating with API: {err}")
                _LOGGER.warning("Using cached data due to communication error")
                
                # Update cache freshness status
                cache_age = "unknown"
                if self._last_successful_update:
                    age_seconds = (datetime.now() - self._last_successful_update).total_seconds()
                    if age_seconds < 300:  # 5 minutes
                        cache_age = "fresh"
                    elif age_seconds < 3600:  # 1 hour
                        cache_age = "recent"
                    else:
                        cache_age = "stale"
                
                return {
                    "battery": self._last_battery_data,
                    "connection_status": "cached",
                    "cache_age": cache_age,
                    "circuit_breaker": self.circuit_breaker.state.value,
                    "last_updated": self._last_successful_update.isoformat() if self._last_successful_update else "unknown"
                }
            else:
                # Create error notification if enabled
                if self._notify_on_recovery:
                    try:
                        await self.hass.components.persistent_notification.async_create(
                            f"ByteWatt integration error: {err}",
                            title="ByteWatt Connection Error",
                            notification_id=NOTIFICATION_ERROR
                        )
                    except (AttributeError, TypeError):
                        _LOGGER.error(f"Could not create error notification: {err}")
                    
                raise UpdateFailed(f"Error communicating with API: {err}")
    
    async def start_heartbeat(self) -> None:
        """Start the heartbeat service to monitor and recover the integration."""
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
        
        self._heartbeat_unsub = async_track_time_interval(
            self.hass,
            self._async_heartbeat_check,
            timedelta(seconds=self._heartbeat_interval)
        )
        _LOGGER.debug("ByteWatt heartbeat monitoring started")
        
        # Also start auto-reconnect if configured
        await self.start_auto_reconnect()
        
        # Log this in diagnostics
        self._log_diagnostic("service_started", {
            "heartbeat_interval": self._heartbeat_interval,
            "auto_reconnect_time": self._auto_reconnect_time
        })
    
    async def start_auto_reconnect(self) -> None:
        """Start scheduled daily reconnection."""
        if self._auto_reconnect_unsub is not None:
            self._auto_reconnect_unsub()
        
        # Schedule reconnect every 24 hours
        self._auto_reconnect_unsub = async_track_time_interval(
            self.hass,
            self._handle_auto_reconnect,
            timedelta(hours=24)
        )
        _LOGGER.info("Automatic reconnect scheduled every 24 hours")
        
        # Immediately run a check if a time is configured
        if hasattr(self, '_auto_reconnect_time') and self._auto_reconnect_time:
            try:
                current_time = datetime.now().time()
                reconnect_time = dt_util.parse_time(self._auto_reconnect_time)
                
                if reconnect_time:
                    # The _handle_auto_reconnect will be called by the interval
                    # eventually, but we log the configured time for reference
                    _LOGGER.info(f"Auto reconnect time configured for {self._auto_reconnect_time}")
            except Exception as err:
                _LOGGER.error(f"Error parsing auto reconnect time: {err}")
    
    @callback
    async def _handle_auto_reconnect(self, _now: Optional[datetime] = None) -> None:
        """Handle scheduled automatic reconnection."""
        _LOGGER.info(f"Executing scheduled auto reconnect at {datetime.now().strftime('%H:%M:%S')}")
        self._log_diagnostic("auto_reconnect", {
            "trigger": "scheduled",
            "time": datetime.now().isoformat()
        })
        
        await self._perform_recovery(is_scheduled=True)
    
    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat service."""
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
            self._heartbeat_unsub = None
            _LOGGER.debug("ByteWatt heartbeat monitoring stopped")
        
        # Also stop auto reconnect
        if self._auto_reconnect_unsub is not None:
            self._auto_reconnect_unsub()
            self._auto_reconnect_unsub = None
        
        # And webhook if registered
        if self._webhook_unsub is not None:
            self._webhook_unsub()
            self._webhook_unsub = None
    
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
        
        # Log heartbeat check in diagnostics
        self._log_diagnostic("heartbeat_check", {
            "timestamp": now.isoformat(),
            "last_update": self._last_successful_update.isoformat() if self._last_successful_update else "never"
        })
        
        # No successful update recorded yet
        if self._last_successful_update is None:
            _LOGGER.debug("No successful update recorded yet")
            # Try to trigger an update if we have no data yet
            if self._last_battery_data is None:
                await self._perform_recovery()
            return
        
        # Calculate age of data
        data_age = now - self._last_successful_update
        data_age_seconds = data_age.total_seconds()
        
        # Check if data is stale
        if data_age_seconds > self._max_data_age:
            self._consecutive_stale_checks += 1
            _LOGGER.warning(
                f"ByteWatt data is stale (age: {data_age_seconds:.1f}s). "
                f"Stale checks: {self._consecutive_stale_checks}/{self._stale_checks_threshold}"
            )
            
            self._log_diagnostic("stale_data", {
                "age_seconds": data_age_seconds,
                "consecutive_checks": self._consecutive_stale_checks,
                "threshold": self._stale_checks_threshold
            })
            
            # If we've reached the threshold, attempt recovery
            if self._consecutive_stale_checks >= self._stale_checks_threshold:
                await self._perform_recovery()
        else:
            # Data is fresh, reset counter
            if self._consecutive_stale_checks > 0:
                _LOGGER.debug("Data is fresh, resetting stale check counter")
                self._log_diagnostic("fresh_data", {
                    "age_seconds": data_age_seconds,
                    "reset_counter_from": self._consecutive_stale_checks
                })
                
            self._consecutive_stale_checks = 0
    
    async def _perform_recovery(self, is_scheduled: bool = False) -> None:
        """Perform recovery actions when data updates have stopped."""
        self._recovery_in_progress = True
        self._recovery_attempts += 1
        
        recovery_type = "scheduled" if is_scheduled else "automatic"
        _LOGGER.warning(f"Performing ByteWatt integration {recovery_type} recovery (attempt {self._recovery_attempts})")
        
        # Record recovery attempt in diagnostics
        self._log_diagnostic("recovery_attempt", {
            "attempt": self._recovery_attempts,
            "type": recovery_type,
            "timestamp": datetime.now().isoformat()
        })
        
        # Create notification about recovery attempt if enabled
        if self._notify_on_recovery:
            try:
                message = f"ByteWatt integration is attempting to reconnect ({recovery_type} recovery)"
                await self.hass.components.persistent_notification.async_create(
                    message,
                    title="ByteWatt Recovery",
                    notification_id=NOTIFICATION_RECOVERY
                )
            except (AttributeError, TypeError) as e:
                _LOGGER.error(f"Could not create recovery notification: {e}")
        
        try:
            # Step 1: Network diagnostics (if diagnostics enabled)
            if self._diagnostics_enabled:
                network_status = await self.hass.async_add_executor_job(self._check_network)
                self._log_diagnostic("network_check", network_status)
            
            # Step 2: Reset client state
            with self._timed_operation("reset_client"):
                await self._reset_client()
            
            # Step 3: Force immediate data refresh
            with self._timed_operation("refresh_data"):
                await self.async_refresh()
            
            # Recovery succeeded
            _LOGGER.info("ByteWatt integration recovery completed successfully")
            
            # Record success in diagnostics
            self._log_diagnostic("recovery_result", {
                "success": True,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update notification if enabled
            if self._notify_on_recovery:
                try:
                    await self.hass.components.persistent_notification.async_dismiss(NOTIFICATION_RECOVERY)
                    await self.hass.components.persistent_notification.async_create(
                        "ByteWatt integration successfully reconnected to the API",
                        title="ByteWatt Recovery Success",
                        notification_id=NOTIFICATION_RECOVERY
                    )
                except (AttributeError, TypeError) as e:
                    _LOGGER.error(f"Could not update recovery notification: {e}")
        except Exception as err:
            _LOGGER.error(f"ByteWatt recovery failed: {err}")
            
            # Record failure in diagnostics
            self._log_diagnostic("recovery_result", {
                "success": False,
                "error": str(err),
                "error_type": type(err).__name__,
                "timestamp": datetime.now().isoformat()
            })
            
            # Apply exponential backoff for retry frequency based on attempt count
            backoff_factor = min(5, self._recovery_attempts)  # Cap at 5x
            next_check_seconds = self._heartbeat_interval // backoff_factor
            
            _LOGGER.info(f"Will attempt recovery again in {next_check_seconds} seconds")
            
            # Update notification if enabled
            if self._notify_on_recovery:
                try:
                    await self.hass.components.persistent_notification.async_create(
                        f"ByteWatt recovery attempt failed: {err}. Will retry in {next_check_seconds} seconds.",
                        title="ByteWatt Recovery Failed",
                        notification_id=NOTIFICATION_RECOVERY
                    )
                except (AttributeError, TypeError) as e:
                    _LOGGER.error(f"Could not update failure notification: {e}")
            
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
    
    def _check_network(self) -> Dict[str, Any]:
        """Check network connectivity to ByteWatt API."""
        result = {
            "dns_check": {},
            "ping_check": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Extract domain from base_url
        domain = "monitor.byte-watt.com"
        if hasattr(self.client, 'api_client') and hasattr(self.client.api_client, 'base_url'):
            base_url = self.client.api_client.base_url
            domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]
        
        # Check DNS resolution
        try:
            ip_address = socket.gethostbyname(domain)
            result["dns_check"] = {
                "success": True,
                "domain": domain,
                "ip_address": ip_address
            }
        except Exception as e:
            result["dns_check"] = {
                "success": False,
                "domain": domain,
                "error": str(e)
            }
        
        # Simple TCP connection test on port 443 (HTTPS)
        try:
            start_time = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((domain, 443))
            s.close()
            end_time = time.time()
            result["ping_check"] = {
                "success": True,
                "domain": domain,
                "port": 443,
                "response_time": f"{(end_time - start_time) * 1000:.2f}ms"
            }
        except Exception as e:
            result["ping_check"] = {
                "success": False,
                "domain": domain,
                "port": 443,
                "error": str(e)
            }
        
        return result
    
    async def _reset_client(self) -> None:
        """Reset client state to force reauthentication and session cleanup."""
        try:
            # Reinitialize client to get a new session and authentication
            if hasattr(self.client, 'initialize'):
                await self.client.initialize()
            
            _LOGGER.info("ByteWatt client state has been reset")
            
            # Record diagnostics
            self._log_diagnostic("client_reset", {
                "success": True,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as err:
            _LOGGER.error(f"Error resetting ByteWatt client: {err}")
            
            # Record diagnostics
            self._log_diagnostic("client_reset", {
                "success": False,
                "error": str(err),
                "error_type": type(err).__name__,
                "timestamp": datetime.now().isoformat()
            })
            
            raise
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run a comprehensive health check on the ByteWatt integration."""
        health_result = {
            "timestamp": datetime.now().isoformat(),
            "integration_id": self.entry_id,
            "connection_status": "unknown",
            "network_checks": {},
            "authentication": {},
            "api_checks": {},
            "configuration": {},
            "metrics": {}
        }
        
        # Record in diagnostics
        self._log_diagnostic("health_check", {"timestamp": datetime.now().isoformat()})
        
        # Check network connectivity
        try:
            health_result["network_checks"] = await self.hass.async_add_executor_job(self._check_network)
        except Exception as err:
            health_result["network_checks"] = {
                "success": False,
                "error": str(err)
            }
        
        # Check authentication
        try:
            auth_start = time.time()
            auth_result = await self.client.initialize()
            auth_duration = time.time() - auth_start
            
            health_result["authentication"] = {
                "success": auth_result,
                "duration": f"{auth_duration:.3f}s"
            }
        except Exception as err:
            health_result["authentication"] = {
                "success": False,
                "error": str(err)
            }
        
        # Check API endpoints
        api_checks = {}
        
        # Check battery data endpoint
        try:
            data_start = time.time()
            battery_data = await self.client.get_battery_data()
            data_duration = time.time() - data_start
            
            api_checks["battery_endpoint"] = {
                "success": battery_data is not None,
                "duration": f"{data_duration:.3f}s",
                "data_available": bool(battery_data)
            }
        except Exception as err:
            api_checks["battery_endpoint"] = {
                "success": False,
                "error": str(err)
            }
        
        # Add API checks to result
        health_result["api_checks"] = api_checks
        
        # Add configuration details
        health_result["configuration"] = {
            "heartbeat_interval": f"{self._heartbeat_interval}s",
            "max_data_age": f"{self._max_data_age}s",
            "stale_checks_threshold": self._stale_checks_threshold,
            "notifications_enabled": self._notify_on_recovery,
            "diagnostics_enabled": self._diagnostics_enabled,
            "auto_reconnect_time": self._auto_reconnect_time
        }
        
        # Add metrics
        health_result["metrics"] = {
            "recovery_attempts": self._recovery_attempts,
            "consecutive_stale_checks": self._consecutive_stale_checks,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "last_successful_update": self._last_successful_update.isoformat() if self._last_successful_update else "never"
        }
        
        # Add overall status
        if (health_result["network_checks"].get("ping_check", {}).get("success", False) and
            health_result["authentication"].get("success", False) and
            api_checks.get("battery_endpoint", {}).get("success", False)):
            health_result["connection_status"] = "healthy"
        elif health_result["authentication"].get("success", False):
            health_result["connection_status"] = "limited"
        else:
            health_result["connection_status"] = "disconnected"
        
        # Log result to diagnostics
        self._log_diagnostic("health_check_result", health_result)
        
        return health_result
    
    def toggle_diagnostics_mode(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle or set diagnostics mode."""
        if enable is None:
            # Toggle current state
            enable = not self._diagnostics_enabled
        
        if enable:
            self._enable_diagnostics()
        else:
            self._disable_diagnostics()
        
        return {
            "diagnostics_mode": self._diagnostics_enabled,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_diagnostic_logs(self) -> List[Dict[str, Any]]:
        """Get all diagnostic logs."""
        return self._diagnostic_logs