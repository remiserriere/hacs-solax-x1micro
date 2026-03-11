"""Constants for the SolaX X1-Micro integration."""

DOMAIN = "solax_x1micro"

CONF_SERIAL_NUMBER = "serial_number"
CONF_INVERTER_TYPE = "inverter_type"

PLATFORMS = ["sensor"]

MQTT_TOPIC_DATA = "loc/tsp/{}"
MQTT_TOPIC_STATUS = "loc/sup/{}"

INVERTER_TYPE_X1_MICRO_2IN1 = "x1_micro_2in1"

INVERTER_TYPES: dict[str, str] = {
    INVERTER_TYPE_X1_MICRO_2IN1: "X1-Micro 2 in 1",
}
