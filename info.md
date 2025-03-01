# Byte-Watt Battery Monitor

Monitor and control your Byte-Watt battery system through Home Assistant.

{% if installed %}
## Integration is installed

Thanks for installing this integration!

**To configure:**
1. Go to **Configuration** → **Integrations**
2. Click the **+ ADD INTEGRATION** button
3. Search for "Byte-Watt Battery Monitor" and click to add
4. Enter your Byte-Watt username and password
{% endif %}

## Features

- Monitor battery percentage, power flow, and energy statistics
- Control charge/discharge times
- Set minimum battery SOC level

## Available Services

| Service | Description |
|---------|-------------|
| `bytewatt.set_discharge_start_time` | Set discharge start time |
| `bytewatt.set_discharge_time` | Set discharge end time |
| `bytewatt.set_charge_start_time` | Set charge start time |
| `bytewatt.set_charge_end_time` | Set charge end time |
| `bytewatt.set_minimum_soc` | Set minimum SOC percentage |

## Sensors

This integration creates sensors for:
- Battery percentage
- Grid consumption (watts)
- House consumption (watts)
- Battery power (watts)
- PV power (watts)
- Total solar generation (kWh)
- And more!

[Full Documentation](https://github.com/YOURUSERNAME/bytewatt)
