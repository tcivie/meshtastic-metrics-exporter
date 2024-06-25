import logging
import os
from datetime import datetime

import paho.mqtt.client as mqtt
import redis
from dotenv import load_dotenv
from meshtastic.mesh_pb2 import MeshPacket
from meshtastic.mqtt_pb2 import ServiceEnvelope
from paho.mqtt.enums import CallbackAPIVersion
from prometheus_client import CollectorRegistry, start_http_server

from exporter.processors import MessageProcessor


def handle_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    client.subscribe(os.getenv('MQTT_TOPIC', 'msh/israel/#'))


def handle_message(client, userdata, message):
    current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Received message on topic '{message.topic}' at {current_timestamp}")
    envelope = ServiceEnvelope()
    envelope.ParseFromString(message.payload)

    packet: MeshPacket = envelope.packet
    if redis_client.set(str(packet.id), 1, nx=True, ex=os.getenv('redis_expiration', 60), get=True) is not None:
        logging.debug(f"Packet {packet.id} already processed")
        return

    # Process the packet
    processor.process(packet)


if __name__ == "__main__":
    load_dotenv()
    # Create Redis client
    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT')),
            db=int(os.getenv('REDIS_DB', 0)),
            password=os.getenv('REDIS_PASSWORD', None),
        )
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        exit(1)

    # Configure Prometheus exporter
    registry = CollectorRegistry()
    start_http_server(int(os.getenv('PROMETHEUS_COLLECTOR_PORT', 8000)), registry=registry)

    # Create an MQTT client
    mqtt_client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5
    )

    mqtt_client.on_connect = handle_connect
    mqtt_client.on_message = handle_message

    if os.getenv('MQTT_IS_TLS', 'false') == 'true':
        tls_context = mqtt.ssl.create_default_context()
        mqtt_client.tls_set_context(tls_context)

    if os.getenv('MQTT_USERNAME', None) and os.getenv('MQTT_PASSWORD', None):
        mqtt_client.username_pw_set(os.getenv('MQTT_USERNAME'), os.getenv('MQTT_PASSWORD'))

    try:
        mqtt_client.connect(
            os.getenv('MQTT_HOST'),
            int(os.getenv('MQTT_PORT')),
            keepalive=int(os.getenv('MQTT_KEEPALIVE', 60)),

        )
    except Exception as e:
        logging.error(f"Failed to connect to MQTT broker: {e}")
        exit(1)
    # Configure the Processor and the Exporter
    processor = MessageProcessor(registry, redis_client)

    mqtt_client.loop_forever()
