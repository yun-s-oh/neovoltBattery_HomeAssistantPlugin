---
description: Steps to add a new custom Home Assistant service
---

# Adding New Services

When adding a new custom Home Assistant service, follow these steps:

## Steps

1. **Define Constant**: Register the service name constant in `const.py`.
2. **Add Handler**: Implement the service execution handler inside `__init__.py`.
3. **Define Schema**: Specify the service parameters and schema in `services.yaml`.
4. **Update API Client**: If needed, update the client methods in the `api/` directory to support the new service calls.
