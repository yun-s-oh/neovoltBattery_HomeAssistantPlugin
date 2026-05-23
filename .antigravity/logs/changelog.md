# Changelog

All notable changes to this project will be documented in this file.

## 2026-05-23
- Implemented core Home Assistant integration support for Grid Feed-In Control entities:
  - Registered main Feed-In Control Toggle Switch (`battery_en` / `batteryEn`).
  - Registered Feed-In Start and End Time entities for schedule slots 1 and 2 (mapping to `sort` fields, defaulting to `"00:00"`).
  - Registered Feed-In Power Limit number entities bounded dynamically by inverter capacity `poinv`.
  - Registered Discharging Cutoff SOC number entity with a strict range of 5% to 100%.
  - Guarded all feed-in entities to load ONLY on individual serial configurations (disabled on "All" serial configurations).
- Implemented automatic schedule normalization in the API client payload compilation, fixing a critical validation bug where the server rejected updates when any schedule slot had a blank serial number (`sys_sn`).
- Added a comprehensive automated test suite `tests/test_feed_in_control.py` covering models, platforms, dynamic limits, and serialization/normalization logic.
- Implemented standalone, PEP 8-compliant test scripts `tests/test_feed_strategy.py` and `tests/test_save_feed_strategy.py` for the new ByteWatt settings endpoints (`getFeedStrategyList` and `saveFeedStrategy`).
- Integrated intelligent serial number resolution into both test scripts, allowing automatic lookup of system IDs from the connected inverter list by supplying serial numbers (e.g., `25000SP265W00123`).
- Added support for `--action add-schedule` in `test_save_feed_strategy.py` to test adding multiple schedules with custom start/end times and power limits.
- Validated live schedule additions on the ByteWatt server, successfully storing multiple configured feed-in time windows.
- Restructured the commit workflow at `.agents/workflows/commit-changes.md` to specify pre-commit checks and synchronized `.antigravity/` documentation updates.

## 2026-05-22
- Fixed an issue where "today" sensor values aggregated data across all inverters by passing the specific `sysSn` to the `/api/report/power/staticsByDay` API endpoint.
- Created the `.agents/workflows/update-docs.md` workflow to standardize documentation and changelog updates.

## 2026-05-12
- Created `.antigravity` folder for project instructions and context.
- Migrated legacy `CLAUDE.md` and split its contents.
  - Instructions and style guidelines moved to `.antigravity/instructions.md`.
  - Architecture and historical context moved to `.antigravity/context.md`.
- Initialized `.antigravity/logs` directory and `changelog.md` to track future changes.
- Created `.antigravity/workflows/api_testing.md` to standardize testing using `.env`.
- Created `.antigravity/skills.md` to document reusable domain knowledge and patterns.
- Reorganized `.antigravity/` to follow standard structure:
  - Split `skills.md` → `skills/auth_handshake.md`, `skills/circuit_breaker.md`.
  - Split `workflows.md` → `workflows/add_sensor.md`, `workflows/add_service.md`, `workflows/code_validation.md`, `workflows/error_handling.md`.
  - Updated `instructions.md` as the central index linking all files.
- Migrated skills and workflows from `.antigravity/` to `.agents/` (standard location):
  - `skills/auth-handshake.md`, `skills/circuit-breaker.md` → `.agents/skills/`
  - `add-sensor.md`, `add-service.md`, `api-testing.md`, `code-validation.md`, `error-handling.md` → `.agents/workflows/`
  - Fixed `KeyError: 'bytewatt'` crash in `config_flow` by ensuring `hass.data[DOMAIN]` and `API_LOCK` are initialized in `ByteWattClient`.
- Improved config flow error handling with specific translations for connection issues and unexpected errors.

## 2026-05-13
- Added Docker support to project setup.
- Updated Battery UPS Reserve Enable API logic to derive from `upsReserve` value (0=False, 1=True). Note: The `upsReserveEnable` boolean switch is not implemented yet.
- Removed "Battery Off-Grid SOC Control" switch and configuration options as they are no longer required.
- Cleaned up API parameters and models to reflect these changes.
- Added support for secondary charge and discharge time controls, enabling two configurable windows.
- Renamed existing single time settings to "1" (e.g., Charge Start Time 1) and added matching "2" settings.
- Enforced strict documentation updates across `.agents` and `.antigravity` via new `documentation-updates.md` rule.
