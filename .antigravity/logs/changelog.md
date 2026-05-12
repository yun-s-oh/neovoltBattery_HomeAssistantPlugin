# Changelog

All notable changes to this project will be documented in this file.

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
- Updated Battery UPS Reserve Enable logic to derive from `upsReserve` value (0=False, 1=True) instead of `upsReserveEnable` boolean.
- Removed "Battery Off-Grid SOC Control" switch and configuration options as they are no longer required.
- Cleaned up API parameters and models to reflect these changes.
- Added support for secondary charge and discharge time controls, enabling two configurable windows.
- Renamed existing single time settings to "1" (e.g., Charge Start Time 1) and added matching "2" settings.
- Enforced strict documentation updates across `.agents` and `.antigravity` via new `documentation-updates.md` rule.
