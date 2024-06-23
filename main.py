import logging
import os

import paho.mqtt.client as mqtt
import redis
from dotenv import load_dotenv
from meshtastic.mesh_pb2 import MeshPacket
from meshtastic.mqtt_pb2 import ServiceEnvelope
from prometheus_client import push_to_gateway, CollectorRegistry

from exporter.processors import MessageProcessor


def handle_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    client.subscribe(os.getenv('mqtt_topic', 'msh/israel/#'))


def handle_message(client, userdata, message):
    print(f"Received message '{message.payload.decode()}' on topic '{message.topic}'")
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
    redis_client = redis.Redis(
        host=os.getenv('redis_host'),
        port=int(os.getenv('redis_port')),
        db=int(os.getenv('redis_db', 0)),
        password=os.getenv('redis_password', None),
    )

    # Configure Prometheus exporter
    registry = CollectorRegistry()
    push_to_gateway(
        os.getenv('prometheus_pushgateway'),
        job=os.getenv('prometheus_job'),
        registry=registry,
    )

    # Create an MQTT client
    mqtt_client = mqtt.Client()

    mqtt_client.on_connect = handle_connect
    mqtt_client.on_message = handle_message

    if bool(os.getenv('mqtt_is_tls', False)):
        tls_context = mqtt.ssl.create_default_context()
        mqtt_client.tls_set_context(tls_context)

    if os.getenv('mqtt_username', None) and os.getenv('mqtt_password', None):
        mqtt_client.username_pw_set(os.getenv('mqtt_username'), os.getenv('mqtt_password'))

    mqtt_client.connect(
        os.getenv('mqtt_host'),
        int(os.getenv('mqtt_port')),
        keepalive=int(os.getenv('mqtt_keepalive', 60)),
    )
    # Configure the Processor and the Exporter
    processor = MessageProcessor(registry, redis_client)

    mqtt_client.loop_forever()
