"""Constants for the Byte-Watt integration."""

DOMAIN = "bytewatt"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_END_DISCHARGE = "end_discharge"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # 1 minute
MIN_SCAN_INTERVAL = 30  # 30 seconds

# Service
SERVICE_SET_DISCHARGE_TIME = "set_discharge_time"
ATTR_END_DISCHARGE = "end_discharge"

# Sensor types
SENSOR_SOC = "soc"
SENSOR_GRID_CONSUMPTION = "grid_consumption"
SENSOR_HOUSE_CONSUMPTION = "house_consumption"
SENSOR_BATTERY_POWER = "battery_power"
SENSOR_PV = "pv_power"
SENSOR_LAST_UPDATE = "last_update"

# Grid stats sensor types
SENSOR_TOTAL_SOLAR = "total_solar_generation"
SENSOR_TOTAL_FEED_IN = "total_feed_in"
SENSOR_TOTAL_BATTERY_CHARGE = "total_battery_charge"
SENSOR_PV_POWER_HOUSE = "pv_power_house"
SENSOR_PV_CHARGING_BATTERY = "pv_charging_battery"
SENSOR_TOTAL_HOUSE_CONSUMPTION = "total_house_consumption"
SENSOR_GRID_BATTERY_CHARGE = "grid_battery_charge"
SENSOR_GRID_POWER_CONSUMPTION = "grid_power_consumption"
