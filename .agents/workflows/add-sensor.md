---
description: Steps to add a new sensor entity to the integration
---

# Adding New Sensors

When implementing a new sensor entity, follow these steps:

## Steps

1. **Define Constant**: Add the new sensor type constant in `const.py`.
2. **Configure Sensor**: Define the sensor logic and behavior in `sensor.py`.
3. **Update Coordinator**: If the new sensor requires new API data fields, update the data extraction logic in `coordinator.py`.
4. **Translations**: Add the corresponding display name translations in `translations/en.json`.
