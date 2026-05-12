---
description: Run linting, type checking, and syntax validation before committing
---

# Code Validation and Linting

Before submitting changes, ensure the code passes all quality checks.

## Commands

- **Linting**:
  ```bash
  flake8 custom_components/bytewatt --max-line-length=100
  ```
  // turbo
- **Type Checking**:
  ```bash
  mypy custom_components/bytewatt --ignore-missing-imports
  ```
  // turbo
- **Syntax Check**:
  ```bash
  python3 -m py_compile custom_components/bytewatt/**/*.py
  ```
  // turbo
- **Home Assistant Validation**:
  ```bash
  hass-config-check custom_components/bytewatt
  ```
