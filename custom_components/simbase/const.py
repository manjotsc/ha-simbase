"""Constants for the Simbase integration."""


class _Unset:
    """Sentinel distinguishing 'argument omitted' from an explicit ``None``.

    ``None`` is a meaningful value for the Simbase API (it clears a nullable
    field), so partial-update helpers use this sentinel as their default to
    mean "leave unchanged".
    """

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()

DOMAIN = "simbase"

# Fallback thresholds used when a usage-limit toggle is switched on without a
# previously known value (e.g. after a restart). Users adjust via the Number.
DEFAULT_DATA_LIMIT_MB = 1024  # 1 GB
DEFAULT_SMS_LIMIT = 1000

# Currency used for monetary sensors when the account balance (which carries
# the account's billing currency) is unavailable.
DEFAULT_CURRENCY = "USD"

# API Constants
API_BASE_URL = "https://api.simbase.com/v2"
API_ENDPOINT_SIMCARDS = "/simcards"
API_ENDPOINT_USAGE = "/usage/simcards"
API_ENDPOINT_BALANCE = "/account/balance"
API_ENDPOINT_PLANS = "/account/plans"

# Configuration
CONF_API_KEY = "api_key"
CONF_SCAN_INTERVAL = "scan_interval"

# Sensor options
CONF_ENABLE_SENSORS = "enable_sensors"
CONF_ENABLE_BINARY_SENSORS = "enable_binary_sensors"
CONF_ENABLE_SWITCH = "enable_switch"

# Control options
CONF_ENABLE_DEVICE_TRACKER = "enable_device_tracker"
CONF_ENABLE_USAGE_LIMITS = "enable_usage_limits"
CONF_ENABLE_PLAN_CONTROLS = "enable_plan_controls"
CONF_ENABLE_RESET_BUTTON = "enable_reset_button"

# Sensor keys
SENSOR_DATA_USAGE = "data_usage"
SENSOR_STATUS = "status"
SENSOR_NETWORK = "network"
SENSOR_IP_ADDRESS = "ip_address"
SENSOR_ICCID = "iccid"
SENSOR_IMEI = "imei"
SENSOR_MSISDN = "msisdn"
SENSOR_PLAN = "plan"
SENSOR_MONTHLY_COST = "monthly_cost"
SENSOR_SMS_COUNT = "sms_count"
SENSOR_SMS_SENT = "sms_sent"
SENSOR_SMS_RECEIVED = "sms_received"
SENSOR_HARDWARE = "hardware"
SENSOR_SESSION_STATUS = "session_status"
SENSOR_LOCATION = "location"

# Binary sensor keys
BINARY_SENSOR_ONLINE = "online"
BINARY_SENSOR_THROTTLED = "throttled"

# All available sensors with display names
AVAILABLE_SENSORS = {
    SENSOR_DATA_USAGE: "Data Usage",
    SENSOR_STATUS: "Status",
    SENSOR_PLAN: "Coverage Plan",
    SENSOR_MONTHLY_COST: "Monthly Cost",
    SENSOR_SMS_COUNT: "SMS Total",
    SENSOR_SMS_SENT: "SMS Sent",
    SENSOR_SMS_RECEIVED: "SMS Received",
    SENSOR_HARDWARE: "Hardware",
    SENSOR_ICCID: "ICCID",
    SENSOR_IMEI: "IMEI",
    SENSOR_MSISDN: "Phone Number (MSISDN)",
    SENSOR_IP_ADDRESS: "IP Address",
    # Available via the v2 SIM details endpoint (connection / location / session):
    SENSOR_NETWORK: "Network Operator",
    SENSOR_SESSION_STATUS: "Session Status",
    SENSOR_LOCATION: "Location",
}

AVAILABLE_BINARY_SENSORS = {
    BINARY_SENSOR_ONLINE: "Online Status",
    BINARY_SENSOR_THROTTLED: "Throttled",
}

# Default enabled sensors
DEFAULT_SENSORS = [
    SENSOR_DATA_USAGE,
    SENSOR_STATUS,
    SENSOR_PLAN,
    SENSOR_MONTHLY_COST,
]

DEFAULT_BINARY_SENSORS = [
    BINARY_SENSOR_ONLINE,
]

DEFAULT_ENABLE_SWITCH = True
DEFAULT_ENABLE_DEVICE_TRACKER = True
DEFAULT_ENABLE_USAGE_LIMITS = True
DEFAULT_ENABLE_PLAN_CONTROLS = True
DEFAULT_ENABLE_RESET_BUTTON = True

# Defaults
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Platforms
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "switch",
    "button",
    "number",
    "select",
    "date",
    "device_tracker",
]

# SIM States
SIM_STATE_ACTIVE = "active"
SIM_STATE_INACTIVE = "inactive"
SIM_STATE_SUSPENDED = "suspended"

# Attributes
ATTR_ICCID = "iccid"
ATTR_IMEI = "imei"
ATTR_MSISDN = "msisdn"
ATTR_DATA_USAGE = "data_usage"
ATTR_DATA_LIMIT = "data_limit"
ATTR_SIM_STATE = "sim_state"
ATTR_NETWORK = "network"
ATTR_COUNTRY = "country"
ATTR_PLAN = "plan"
ATTR_LAST_SEEN = "last_seen"

# Services
SERVICE_ACTIVATE_SIM = "activate_sim"
SERVICE_DEACTIVATE_SIM = "deactivate_sim"
SERVICE_SEND_SMS = "send_sms"
SERVICE_READ_SMS = "read_sms"
SERVICE_RESET_CONNECTION = "reset_connection"
SERVICE_SET_AUTODISABLE = "set_autodisable"
SERVICE_SET_USAGE_LIMITS = "set_usage_limits"
SERVICE_SET_RATEPLAN = "set_rateplan"
