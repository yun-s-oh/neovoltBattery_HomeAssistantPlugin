# ByteWatt Home Assistant Integration Context

## Repository Overview

This is a Home Assistant custom integration for monitoring and controlling ByteWatt/Neovolt battery systems. The integration provides comprehensive real-time monitoring of solar, battery, and grid power flows with sophisticated recovery mechanisms and battery control capabilities.

### Current Status
- **Version**: 1.0.0 (HACS compatible)
- **Architecture**: Production-ready with robust error handling and automatic recovery
- **Recent Cleanup**: Technical debt removed, modular architecture implemented (2024-12)

## Project Structure

```
custom_components/bytewatt/
├── __init__.py                 # Main integration entry point & services
├── bytewatt_client.py         # High-level API wrapper
├── config_flow.py             # Configuration UI flow
├── const.py                   # Constants and configuration
├── coordinator.py             # Data update coordinator with recovery
├── models.py                  # Data models for the integration
├── sensor.py                  # All sensor entity definitions
├── services.yaml              # Service definitions for Home Assistant
├── validation.py              # Minimal data validation (cleaned up)
├── manifest.json              # Integration metadata
├── translations/
│   └── en.json               # English translations
├── api/                      # Low-level API clients
│   ├── __init__.py
│   ├── neovolt_auth.py       # Authentication handling
│   ├── neovolt_client.py     # Core API client with async methods
│   └── settings.py           # Battery settings API
└── utilities/                # Utility modules (new modular architecture)
    ├── __init__.py
    ├── circuit_breaker.py    # Circuit breaker pattern implementation
    ├── connection_stats.py   # Connection health statistics
    ├── diagnostic_service.py # Health checks and diagnostics
    └── time_utils.py         # Time manipulation utilities
```

## Architecture

### Core Components
- **`bytewatt_client.py`**: High-level async API wrapper with battery control methods
- **`coordinator.py`**: DataUpdateCoordinator with circuit breaker pattern and automatic recovery
- **`sensor.py`**: All sensor entities (50+ sensors for comprehensive monitoring)
- **`config_flow.py`**: UI configuration flow with validation
- **`const.py`**: All constants, defaults, and configuration keys

### API Layer (`api/`)
- **`neovolt_client.py`**: Low-level async HTTP client with authentication
- **`neovolt_auth.py`**: Password encryption and authentication logic
- **`settings.py`**: Battery settings API with validation and retry logic

### Utility Modules (`utilities/`)
- **`circuit_breaker.py`**: Implements circuit breaker pattern for API resilience
- **`connection_stats.py`**: Tracks connection health and response times
- **`diagnostic_service.py`**: Health checks, diagnostics, and logging
- **`time_utils.py`**: Time format validation and manipulation

### Key Features
1. **Real-time Monitoring**: Battery SOC, power flows, energy statistics
2. **Daily Statistics**: PV generation, consumption, self-sufficiency metrics
3. **Battery Control**: Charge/discharge scheduling, minimum SOC setting
4. **Automatic Recovery**: Circuit breaker pattern with exponential backoff
5. **Health Monitoring**: Comprehensive diagnostics and connectivity checks
6. **HACS Compatible**: Installable through Home Assistant Community Store

### Services Available
- `bytewatt.set_discharge_time` - Set battery discharge end time (legacy)
- `bytewatt.set_discharge_start_time` - Set battery discharge start time 1
- `bytewatt.set_discharge_end_time1` - Set battery discharge end time 1
- `bytewatt.set_charge_start_time` - Set battery charge start time 1
- `bytewatt.set_charge_end_time` - Set battery charge end time 1
- `bytewatt.set_discharge_start_time_2` - Set battery discharge start time 2
- `bytewatt.set_discharge_end_time_2` - Set battery discharge end time 2
- `bytewatt.set_charge_start_time_2` - Set battery charge start time 2
- `bytewatt.set_charge_end_time_2` - Set battery charge end time 2
- `bytewatt.set_minimum_soc` - Set minimum state of charge
- `bytewatt.update_battery_settings` - Update multiple settings at once
- `bytewatt.force_reconnect` - Force API reconnection
- `bytewatt.health_check` - Run comprehensive health check
- `bytewatt.toggle_diagnostics` - Enable/disable diagnostic logging

### Configuration Options
- `scan_interval`: Data update frequency (default: 60s, min: 30s)
- `heartbeat_interval`: Health check frequency (default: 120s)
- `max_data_age`: Max age before data considered stale (default: 300s)
- `stale_checks_threshold`: Failed checks before recovery (default: 3)
- `notify_on_recovery`: Show recovery notifications (default: true)
- `diagnostics_mode`: Enable detailed logging (default: false)
- `auto_reconnect_time`: Daily reconnect time (default: "03:30:00")

## Recent Changes (May 2026)

### Grid Feed-In Control Integration & Test Automation
- ✅ **Core Home Assistant Grid Feed-in Entities**:
  - **Toggle Switch**: Grid Feed-in Control entity (`battery_en` / `batteryEn` toggle).
  - **Start/End Times**: Start/End time entities for slots 1 and 2, mapped dynamically based on the schedule `sort` field.
  - **Power Limits**: Bounded number entities dynamically restricted by inverter capacity `poinv` for slots 1 and 2.
  - **Discharging Cutoff SOC**: A number entity covering SOC cutoff limits with a strict range of 5% to 100%.
  - **Setup Guards**: All feed-in entities load ONLY on individual serial configurations (disabled on "All" serial configurations).
- ✅ **API Schedule Normalization**:
  - Integrated a serialization loop in `neovolt_client.py` ensuring *all* active or pre-populated schedules contain a valid `sys_sn` before saving to prevent transient payload rejection from the server.
- ✅ **Automated Unit Test Coverage**:
  - Created [test_feed_in_control.py](file:///tests/test_feed_in_control.py) to validate parsing, defaults, dynamic limits, validation ranges, switches, and client payload normalization.
- ✅ **New API Settings Endpoints**:
  - **GET**: `api/iterate/sysSet/getFeedStrategyList?id=` (retrieves battery feedCutoffSoc, poinv, precharge settings, and active schedules)
  - **POST**: `api/iterate/sysSet/saveFeedStrategy` (saves grid feed-in schedules and configuration)
- ✅ **Standalone PEP 8 Test Scripts**:
  - [test_feed_strategy.py](file:///tests/test_feed_strategy.py) — Fetches and formats feed-in settings and active schedule tables.
  - [test_save_feed_strategy.py](file:///tests/test_save_feed_strategy.py) — Builds dynamic DTO payloads to safely test and mutate/restore grid schedules.
- ✅ **Intelligent Serial Number Lookup**: Added robust auto-discovery to automatically resolve system serial numbers (e.g., `25000SP265W00123`) to internal system IDs via the inverter list.
- ✅ **Commit & Staging Workflows**: Integrated pre-commit validations and synchronized `.antigravity/` updates to the central commit guide.

## Recent Changes (December 2024)

### Technical Debt Cleanup
- ✅ **Removed 1000+ lines of disabled validation code** from `validation.py`
- ✅ **Split coordinator.py** (896 lines) into focused utility modules
- ✅ **Re-enabled battery control services** - API supports these features
- ✅ **Replaced magic numbers** with named constants
- ✅ **Cleaned up imports** and standardized error logging

### API Updates
- ✅ **Updated to new settings API endpoints**:
  - **GET**: `api/iterate/sysSet/getChargeConfigInfo?id=` (retrieve settings)
  - **POST**: `api/iterate/sysSet/updateChargeConfigInfo` (update settings)
- ✅ **Simplified device handling**: Using `id=""` (empty) to apply to all devices
- ✅ **New API data format**: Updated to use `timeChaf1`, `batUseCap`, `gridCharge`, etc.
- ✅ **Removed old API support**: Legacy endpoints no longer supported

### Battery Settings API Format

**GET Settings** (`getChargeConfigInfo?id=`):
```json
{
  "code": 200,
  "msg": "Success", 
  "data": {
    "gridCharge": 0,
    "timeChaf1": "14:30",
    "timeChae1": "16:00",
    "ctrDis": 0,
    "timeDisf1": "16:00", 
    "timeDise1": "06:00",
    "batUseCap": 6,
    "batHighCap": 100
  }
}
```

**POST Settings** (`updateChargeConfigInfo`):
```json
{
  "id": "",
  "gridCharge": 0,
  "timeChaf1": "14:30",
  "timeChae1": "16:00",
  "ctrDis": 0,
  "timeDisf1": "16:00",
  "timeDise1": "06:00",
  "batUseCap": 6,
  "batHighCap": 100,
  "batCapRange": [5, 100],
  "isJapaneseDevice": false,
  "upsReserveEnable": true,
  "chargeModeSetting": 0
}
```

### New Modular Architecture
- **Circuit Breaker Pattern**: `utilities/circuit_breaker.py` - Prevents API flooding during outages
- **Connection Statistics**: `utilities/connection_stats.py` - Tracks API health metrics
- **Diagnostic Service**: `utilities/diagnostic_service.py` - Health checks and troubleshooting
- **Improved Error Handling**: Exponential backoff, proper exception types

### Battery Control Features (Re-enabled)
- All battery control services now functional (previously disabled)
- Async battery settings API with validation and retry logic
- Support for charge/discharge time scheduling and minimum SOC
- Proper error handling and user feedback

## Testing & Validation

### Test Data Structure
```
TestData/
├── comparison_results/        # Validator comparison outputs
├── validatedJsonFiles/        # Known good data samples
└── [various validators]       # Historical validation scripts
```

### Validation Strategy
- **Basic Validation**: SOC range checks, required field validation
- **API Response Validation**: Server-side data is trusted as accurate
- **Retry Logic**: Exponential backoff for transient failures
- **Circuit Breaker**: Prevents cascading failures during outages
```
