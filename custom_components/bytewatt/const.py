"""Constants for the Byte-Watt integration."""

DOMAIN = "bytewatt"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # 1 minute
MIN_SCAN_INTERVAL = 30  # 30 seconds

# Services
SERVICE_SET_DISCHARGE_TIME = "set_discharge_time"  # Legacy service
SERVICE_SET_DISCHARGE_START_TIME = "set_discharge_start_time"
SERVICE_SET_CHARGE_START_TIME = "set_charge_start_time"
SERVICE_SET_CHARGE_END_TIME = "set_charge_end_time"
SERVICE_SET_MINIMUM_SOC = "set_minimum_soc"
SERVICE_UPDATE_BATTERY_SETTINGS = "update_battery_settings"
SERVICE_FORCE_RECONNECT = "force_reconnect"  # Force client reconnection for troubleshooting

# Service attributes
ATTR_END_DISCHARGE = "end_discharge"
ATTR_START_DISCHARGE = "start_discharge"
ATTR_START_CHARGE = "start_charge"
ATTR_END_CHARGE = "end_charge"
ATTR_MINIMUM_SOC = "minimum_soc"

# Sensor types
SENSOR_SOC = "soc"
SENSOR_GRID_CONSUMPTION = "grid_consumption"
SENSOR_HOUSE_CONSUMPTION = "house_consumption"
SENSOR_BATTERY_POWER = "battery_power"
SENSOR_PV = "pv_power"
SENSOR_LAST_UPDATE = "last_update"

# Battery settings sensor types
SENSOR_DISCHARGE_START = "discharge_start_time"
SENSOR_DISCHARGE_END = "discharge_end_time"
SENSOR_CHARGE_START = "charge_start_time"
SENSOR_CHARGE_END = "charge_end_time"
SENSOR_MIN_SOC = "minimum_soc"

# Grid stats sensor types
SENSOR_TOTAL_SOLAR = "total_solar_generation"
SENSOR_TOTAL_FEED_IN = "total_feed_in"
SENSOR_TOTAL_BATTERY_CHARGE = "total_battery_charge"
SENSOR_PV_POWER_HOUSE = "pv_power_house"
SENSOR_PV_CHARGING_BATTERY = "pv_charging_battery"
SENSOR_TOTAL_HOUSE_CONSUMPTION = "total_house_consumption"
SENSOR_GRID_BATTERY_CHARGE = "grid_battery_charge"
SENSOR_GRID_POWER_CONSUMPTION = "grid_power_consumption"
