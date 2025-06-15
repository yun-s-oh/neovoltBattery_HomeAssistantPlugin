"""Diagnostic and health check services for ByteWatt integration."""
import json
import logging
import socket
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..const import HTTPS_PORT, MAX_DIAGNOSTIC_LOGS

_LOGGER = logging.getLogger(__name__)


class DiagnosticService:
    """Service for handling diagnostics and health checks."""
    
    def __init__(self):
        """Initialize the diagnostic service."""
        self._diagnostics_enabled = False
        self._diagnostic_logs: List[Dict[str, Any]] = []
        self._max_diagnostic_logs = MAX_DIAGNOSTIC_LOGS
    
    def enable_diagnostics(self):
        """Enable diagnostic logging."""
        self._diagnostics_enabled = True
        _LOGGER.info("Diagnostic logging enabled")
        self.log_diagnostic("diagnostics_enabled", {"timestamp": datetime.now().isoformat()})
    
    def disable_diagnostics(self):
        """Disable diagnostic logging."""
        self._diagnostics_enabled = False
        _LOGGER.info("Diagnostic logging disabled")
        self.log_diagnostic("diagnostics_disabled", {"timestamp": datetime.now().isoformat()})
    
    def log_diagnostic(self, event_type: str, details: Dict[str, Any]):
        """Log a diagnostic event."""
        if not self._diagnostics_enabled:
            return
        
        diagnostic_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        
        self._diagnostic_logs.append(diagnostic_entry)
        
        # Trim logs to prevent memory issues
        if len(self._diagnostic_logs) > self._max_diagnostic_logs:
            self._diagnostic_logs = self._diagnostic_logs[-self._max_diagnostic_logs:]
        
        _LOGGER.debug(f"Diagnostic logged: {event_type}")
    
    async def check_connectivity(self, base_url: str) -> Dict[str, Any]:
        """Check connectivity to the API server."""
        domain = base_url.replace("https://", "").replace("http://", "")
        start_time = time.time()
        
        try:
            # Simple TCP connection test on HTTPS port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect((domain, HTTPS_PORT))
            
            end_time = time.time()
            return {
                "status": "success",
                "domain": domain,
                "port": HTTPS_PORT,
                "response_time": f"{(end_time - start_time) * 1000:.2f}ms"
            }
        except Exception as e:
            end_time = time.time()
            return {
                "status": "failed",
                "domain": domain,
                "port": HTTPS_PORT,
                "error": str(e),
                "response_time": f"{(end_time - start_time) * 1000:.2f}ms"
            }
    
    def toggle_diagnostics_mode(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle diagnostics mode on or off."""
        if enable is None:
            # Toggle current state
            enable = not self._diagnostics_enabled
        
        old_state = self._diagnostics_enabled
        
        if enable:
            self.enable_diagnostics()
        else:
            self.disable_diagnostics()
        
        return {
            "previous_state": old_state,
            "new_state": self._diagnostics_enabled,
            "action": "enabled" if self._diagnostics_enabled else "disabled",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_diagnostic_logs(self) -> List[Dict[str, Any]]:
        """Get all diagnostic logs."""
        return self._diagnostic_logs.copy()
    
    @property
    def diagnostics_enabled(self) -> bool:
        """Check if diagnostics are enabled."""
        return self._diagnostics_enabled
    
    async def run_health_check(self, coordinator) -> Dict[str, Any]:
        """Run a comprehensive health check on the ByteWatt integration."""
        health_timestamp = datetime.now()
        health_result = {
            "timestamp": health_timestamp.isoformat(),
            "integration_id": coordinator.entry_id,
            "connection_status": "unknown",
            "network_checks": {},
            "authentication": {},
            "api_checks": {},
            "configuration": {},
            "metrics": {}
        }
        
        # Record in diagnostics
        self.log_diagnostic("health_check", {"timestamp": health_timestamp.isoformat()})
        
        # Check network connectivity
        try:
            health_result["network_checks"] = await self.check_connectivity(
                coordinator.client.api_client.base_url
            )
        except Exception as err:
            health_result["network_checks"] = {
                "success": False,
                "error": str(err)
            }
        
        # Check authentication
        try:
            auth_start = time.time()
            auth_result = await coordinator.client.initialize()
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
            battery_data = await coordinator.client.get_battery_data()
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
            "heartbeat_interval": f"{coordinator._heartbeat_interval}s",
            "max_data_age": f"{coordinator._max_data_age}s",
            "stale_checks_threshold": coordinator._stale_checks_threshold,
            "notifications_enabled": coordinator._notify_on_recovery,
            "diagnostics_enabled": self._diagnostics_enabled,
            "auto_reconnect_time": coordinator._auto_reconnect_time
        }
        
        # Add metrics
        health_result["metrics"] = {
            "recovery_attempts": coordinator._recovery_attempts,
            "consecutive_stale_checks": coordinator._consecutive_stale_checks,
            "circuit_breaker_state": coordinator.circuit_breaker.state.value,
            "last_successful_update": coordinator._last_successful_update.isoformat() if coordinator._last_successful_update else "never"
        }
        
        # Add overall status
        if (health_result["network_checks"].get("status") == "success" and
            health_result["authentication"].get("success", False) and
            api_checks.get("battery_endpoint", {}).get("success", False)):
            health_result["connection_status"] = "healthy"
        elif health_result["authentication"].get("success", False):
            health_result["connection_status"] = "limited"
        else:
            health_result["connection_status"] = "disconnected"
        
        # Log result to diagnostics
        self.log_diagnostic("health_check_result", health_result)
        
        return health_result