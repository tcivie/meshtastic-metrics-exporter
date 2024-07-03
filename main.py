import logging
import os
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

try:
    from meshtastic.mesh_pb2 import MeshPacket
    from meshtastic.mqtt_pb2 import ServiceEnvelope
except ImportError:
    from meshtastic.protobuf.mesh_pb2 import MeshPacket
    from meshtastic.protobuf.mqtt_pb2 import ServiceEnvelope

from paho.mqtt.enums import CallbackAPIVersion
from prometheus_client import CollectorRegistry, start_http_server
from psycopg_pool import ConnectionPool

from exporter.processor_base import MessageProcessor

# Global connection pool
connection_pool = None


def get_connection():
    return connection_pool.getconn()


def release_connection(conn):
    connection_pool.putconn(conn)


def handle_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    client.subscribe(os.getenv('MQTT_TOPIC', 'msh/israel/#'))


def handle_message(client, userdata, message):
    current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Received message on topic '{message.topic}' at {current_timestamp}")
    if '/stat/' in message.topic:
        print(f"Filtered out message from topic containing '/stat/': {message.topic}")
        return

    envelope = ServiceEnvelope()
    envelope.ParseFromString(message.payload)
    packet: MeshPacket = envelope.packet

    with connection_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM messages WHERE id = %s", (str(packet.id),))
            if cur.fetchone() is not None:
                logging.debug(f"Packet {packet.id} already processed")
                return

            cur.execute("INSERT INTO messages (id, received_at) VALUES (%s, NOW()) ON CONFLICT (id) DO NOTHING",
                        (str(packet.id),))
            conn.commit()

    processor.process(packet)


if __name__ == "__main__":
    load_dotenv()

    # Setup a connection pool
    connection_pool = ConnectionPool(
        os.getenv('DATABASE_URL'),
        min_size=1,
        max_size=10
    )

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
    processor = MessageProcessor(registry, connection_pool)

    mqtt_client.loop_forever()
