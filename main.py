import logging
import os
from logging.handlers import RotatingFileHandler

import humanfriendly
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from constants import callback_api_version_map, protocol_map

try:
    from meshtastic.mesh_pb2 import MeshPacket
    from meshtastic.mqtt_pb2 import ServiceEnvelope
except ImportError:
    from meshtastic.protobuf.mesh_pb2 import MeshPacket
    from meshtastic.protobuf.mqtt_pb2 import ServiceEnvelope

from psycopg_pool import ConnectionPool

connection_pool = None


def handle_connect(client, userdata, flags, reason_code, properties):
    topics = os.getenv('MQTT_TOPIC', 'msh/israel/#').split(',')
    topics_tuples = [(topic, 0) for topic in topics]
    err, code = client.subscribe(topics_tuples)
    if err:
        logging.error(
            f"Error subscribing to topics: {err} with code {code} for {topics_tuples} and reason code {reason_code}")


def update_node_status(node_number, status):
    with connection_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO node_details (node_id, mqtt_status, short_name, long_name) VALUES (%s, %s, %s, %s)"
                        "ON CONFLICT(node_id)"
                        "DO UPDATE SET mqtt_status = %s",
                        (node_number, status, 'Unknown (MQTT)', 'Unknown (MQTT)', status))
            conn.commit()


def handle_message(client, userdata, message):
    logging.debug(f"Received message on topic '{message.topic}'")
    if '/json/' in message.topic:
        try:
            processor.process_json_mqtt(message)
        except Exception as e:
            logging.error(f"Failed to handle JSON message: {e}")
        # Ignore JSON messages as there are also protobuf messages sent on other topic
        # Source: https://github.com/meshtastic/firmware/blob/master/src/mqtt/MQTT.cpp#L448
        return

    if '/stat/' in message.topic or '/tele/' in message.topic:
        try:
            user_id = message.topic.split('/')[-1]  # Hexadecimal user ID
            if user_id[0] == '!':
                node_number = str(int(user_id[1:], 16))
                update_node_status(node_number, message.payload.decode('utf-8'))
            return
        except Exception as e:
            logging.error(f"Failed to handle user MQTT stat: {e}")
            return

    envelope = ServiceEnvelope()
    try:
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
        processor.process_mqtt(message.topic, envelope, packet)
        processor.process(packet)
    except Exception as e:
        logging.error(f"Failed to handle message: {e}")
        return


if __name__ == "__main__":
    load_dotenv()

    # Configure logging
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_file_max_size = humanfriendly.parse_size(os.getenv('LOG_FILE_MAX_SIZE', '10MB'))
    log_files_count = int(os.getenv('LOG_FILE_BACKUP_COUNT', 5))  # 5 backup files
    handlers = [
        RotatingFileHandler(
            'exporter.log', maxBytes=log_file_max_size, backupCount=log_files_count
        )
    ]
    if os.getenv('ENABLE_STREAM_HANDLER', 'true').lower() == 'true':
        handlers.append(logging.StreamHandler())
    else:
        print("!!! Stream handler disabled !!! only file handler will be used - check exporter.log for logs")

    logging.basicConfig(
        handlers=handlers,
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # We have to load_dotenv before we can import MessageProcessor to allow filtering of message types
    from exporter.processor.processor_base import MessageProcessor

    # Setup a connection pool
    connection_pool = ConnectionPool(
        os.getenv('DATABASE_URL'),
        max_size=100
    )
    # Node configuration is now handled by the database timestamps

    # No need for Prometheus exporter anymore

    # Create an MQTT client
    mqtt_protocol = os.getenv('MQTT_PROTOCOL', 'MQTTv5')
    mqtt_callback_api_version = os.getenv('MQTT_CALLBACK_API_VERSION', 'VERSION2')
    mqtt_client = mqtt.Client(
        callback_api_version=callback_api_version_map.get(mqtt_callback_api_version, mqtt.CallbackAPIVersion.VERSION2),
        protocol=protocol_map.get(mqtt_protocol, mqtt.MQTTv5)
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

    # Configure the Processor
    processor = MessageProcessor(connection_pool)

    mqtt_client.loop_forever()
