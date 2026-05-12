---
trigger: always_on
---

# Code Style Guide

This project follows the PEP 8 style guide for Python code and requires all code to be properly commented.

## Python Standards
- **Version**: Python 3.9+ compatible.
- **Formatting**: Use 4 spaces for indentation (no tabs).
- **Line Length**: Limit lines to a maximum of 100 characters.
- **Imports**: Group imports logically, separated by blank lines:
  1. Standard library
  2. Third-party packages
  3. Home Assistant modules
- **Comments and Documentation**:
  - Ensure all code is properly commented to explain "why" rather than "what".
  - Use docstrings with triple double quotes (`"""`) for modules, classes, and complex functions.
- **Type Hints**: Required for all new functions and methods.
- **Error Handling**: Use `try/except` blocks with appropriate logging levels (debug, info, warning, error).
- **Magic Numbers**: Avoid magic numbers in the codebase; always use named constants defined in `const.py`.

## Naming Conventions
- **Classes**: `CamelCase` (e.g., `ByteWattCoordinator`)
- **Constants**: `UPPER_CASE` (e.g., `DEFAULT_SCAN_INTERVAL`)
- **Variables and Functions**: `snake_case` (e.g., `get_battery_status`)