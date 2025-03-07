# ByteWatt Home Assistant Integration Development Guide

## Commands
- **Manual Install**: Copy `custom_components/bytewatt` to Home Assistant's `custom_components` directory
- **Lint**: `flake8 custom_components/bytewatt`
- **Type Check**: `mypy custom_components/bytewatt`
- **Validate**: `hass-config-check custom_components/bytewatt`
- **Debug**: Add to HA configuration.yaml: `logger: default: debug`

## Code Style
- **Python**: Version 3.9+ compatible
- **Formatting**: 4 spaces (not tabs), <100 char lines
- **Imports**: Standard lib → Third party → Home Assistant, grouped with blank lines
- **Naming**: CamelCase (classes), UPPER_CASE (constants), snake_case (variables/functions)
- **Error handling**: Try/except with appropriate logging levels
- **Comments**: Docstrings with triple double quotes
- **Type hints**: Required for all new functions/methods

## Architecture
- API client logic in `bytewatt_client.py`
- Use `DataUpdateCoordinator` for efficient updates
- Entity code in `sensor.py`, configuration in `config_flow.py`
- Constants in `const.py`
- Services defined in `services.yaml`