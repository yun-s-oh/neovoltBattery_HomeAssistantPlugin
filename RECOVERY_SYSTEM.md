# ByteWatt Integration Automatic Recovery System

## Overview

We've implemented a robust automatic recovery system for the ByteWatt Home Assistant integration to solve the issue where the plugin would randomly stop updating and not come back online. This document summarizes the key components of this system.

## Core Components

### 1. Heartbeat Monitoring

The integration now has a background monitoring system that checks data freshness every 2 minutes. If no fresh data has been received for 5 minutes, it begins a recovery process:

- **Location**: `coordinator.py` - `ByteWattDataUpdateCoordinator` class
- **Key method**: `_check_and_recover()`

### 2. Recovery Process

When stale data is detected for three consecutive checks, the system:

1. Resets the client state (closes and recreates the session)
2. Forces re-authentication with the ByteWatt servers
3. Refreshes all sensor data
4. Implements exponential backoff for retries

- **Location**: `coordinator.py` - `_perform_recovery()` method

### 3. Client Reinitialization

The ByteWatt client now has methods to safely reset its state:

- **Location**: `bytewatt_client.py` - `initialize()` method 
- **Purpose**: Creates a fresh API client with new session objects

### 4. Manual Recovery Service

We've added a service that users can call to manually trigger the recovery process:

- **Service name**: `bytewatt.force_reconnect`
- **Location**: `__init__.py` - `handle_force_reconnect()` service handler

## Technical Improvements

1. **Hysteresis Logic**: The system requires multiple consecutive failures before initiating recovery, preventing oscillation between states.

2. **Exponential Backoff**: Failed recovery attempts are retried with increasing frequency based on the attempt count.

3. **Clean Session Management**: Sessions are properly closed and recreated during recovery.

4. **Tracked Metrics**: The coordinator tracks important metrics like successful update time and consecutive stale checks.

## Usage Example

The recovery system works automatically in the background, but can also be manually triggered:

```yaml
# Example automation to force reconnect if needed
automation:
  - alias: "ByteWatt Recovery"
    trigger:
      - platform: state
        entity_id: sensor.bytewatt_soc
        for: 
          minutes: 10
    action:
      - service: bytewatt.force_reconnect
```

## Future Enhancements

Potential improvements for the recovery system:

1. Make recovery parameters configurable through Home Assistant UI
2. Add a persistent notification when recovery is triggered
3. Implement more sophisticated network diagnostics
4. Add telemetry for tracking recovery success rates (with user opt-in)

## Testing

The recovery system has been tested with simulated network failures to confirm that it properly detects and recovers from:

- Network interruptions
- API authentication failures
- Session timeouts
- Invalid responses