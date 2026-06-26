DOMAIN = "adaptive_alerting"

CONF_SENSOR_ENTITY_ID = "sensor_entity_id"
CONF_LEARNING_WINDOW_DAYS = "learning_window_days"
CONF_SENSITIVITY = "sensitivity"  # Number of std deviations to trigger

DEFAULT_LEARNING_WINDOW_DAYS = 14
DEFAULT_SENSITIVITY = 2.5

STORAGE_KEY = "adaptive_alerting_baseline"
STORAGE_VERSION = 1

EVENT_ANOMALY_DETECTED = "adaptive_alerting_anomaly"
