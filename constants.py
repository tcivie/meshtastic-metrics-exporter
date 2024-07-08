import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

protocol_map = {
    'MQTTv31': mqtt.MQTTv31,
    'MQTTv311': mqtt.MQTTv311,
    'MQTTv5': mqtt.MQTTv5
}

callback_api_version_map = {
    'VERSION1': CallbackAPIVersion.VERSION1,
    'VERSION2': CallbackAPIVersion.VERSION2
}
