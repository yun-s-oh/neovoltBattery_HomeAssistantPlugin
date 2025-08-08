# ByteWatt Home Assistant Integration Instructions

## Commands
- **Manual Install**: Copy `custom_components/bytewatt` to Home Assistant's `custom_components` directory
- **Lint**: `flake8 custom_components/bytewatt --max-line-length=100`
- **Type Check**: `mypy custom_components/bytewatt --ignore-missing-imports`
- **Validate**: `hass-config-check custom_components/bytewatt`
- **Debug**: Add to HA configuration.yaml: `logger: default: debug`
- **Syntax Check**: `python3 -m py_compile custom_components/bytewatt/**/*.py`

## Code Style
- **Python**: Version 3.9+ compatible
- **Formatting**: 4 spaces (not tabs), <100 char lines
- **Imports**: Standard lib → Third party → Home Assistant, grouped with blank lines
- **Naming**: CamelCase (classes), UPPER_CASE (constants), snake_case (variables/functions)
- **Error handling**: Try/except with appropriate logging levels
- **Comments**: Docstrings with triple double quotes
- **Type hints**: Required for all new functions/methods
- **Magic Numbers**: Use named constants from `const.py`

## Development Notes

### Adding New Sensors
1. Define sensor type constant in `const.py`
2. Add sensor configuration in `sensor.py`
3. Update `coordinator.py` if new data extraction needed
4. Add translations in `translations/en.json`

### Adding New Services
1. Define service constant in `const.py`
2. Add service handler in `__init__.py`
3. Define service schema in `services.yaml`
4. Update client methods if API changes needed

### Error Handling Best Practices
- Use specific exception types from API layers
- Log at appropriate levels (debug/info/warning/error)
- Implement retry logic with exponential backoff
- Use circuit breaker for external API calls
- Provide meaningful error messages to users

### Performance Considerations
- Minimum scan interval: 30 seconds (to prevent API abuse)
- Connection pooling for HTTP requests
- Efficient data structures for historical tracking
- Automatic cleanup of diagnostic logs (max 100 entries)

### Change Tracking
- Ensure all notable modifications or additions are logged in `.antigravity/logs/changelog.md`.