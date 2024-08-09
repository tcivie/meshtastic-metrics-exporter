import os

from psycopg_pool import ConnectionPool

from exporter.db_handler import DBHandler


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class NodeConfigurationMetrics(metaclass=Singleton):
    def __init__(self, connection_pool: ConnectionPool = None):
        self.db = DBHandler(connection_pool)
        self.report = os.getenv('REPORT_NODE_CONFIGURATIONS', True)

    def process_environment_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (node_id, 
            environment_update_interval,
            environment_update_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
            environment_update_interval = NOW() - node_configurations.environment_update_last_timestamp,
            environment_update_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_device_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (node_id, 
            device_update_interval,
            device_update_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
            device_update_interval = NOW() - node_configurations.device_update_last_timestamp,
            device_update_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_power_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (node_id, 
            power_update_interval,
            power_update_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
            power_update_interval = NOW() - node_configurations.power_update_last_timestamp,
            power_update_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def map_broadcast_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (node_id, 
            map_broadcast_interval,
            map_broadcast_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
            map_broadcast_interval = NOW() - node_configurations.map_broadcast_last_timestamp,
            map_broadcast_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_air_quality_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (node_id, 
            air_quality_update_interval,
            air_quality_update_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
            air_quality_update_interval = NOW() - node_configurations.air_quality_update_last_timestamp,
            air_quality_update_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_range_test_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
                INSERT INTO node_configurations (
                    node_id, 
                    range_test_interval,
                    range_test_packets_total,
                    range_test_first_packet_timestamp,
                    range_test_last_packet_timestamp
                ) VALUES (%s, %s, NOW(), NOW(), NOW())
                ON CONFLICT(node_id)
                DO UPDATE SET
                    range_test_interval = NOW() - node_configurations.range_test_last_packet_timestamp,
                    range_test_packets_total = CASE 
                        WHEN EXCLUDED.range_test_last_packet_timestamp - node_configurations.range_test_first_packet_timestamp >= INTERVAL '1 hour' 
                        THEN 1
                        ELSE node_configurations.range_test_packets_total + 1
                    END,
                    range_test_first_packet_timestamp = CASE 
                        WHEN EXCLUDED.range_test_last_packet_timestamp - node_configurations.range_test_first_packet_timestamp >= INTERVAL '1 hour' 
                        THEN NOW()
                        ELSE node_configurations.range_test_first_packet_timestamp
                    END,
                    range_test_last_packet_timestamp = NOW()
                """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_pax_counter_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (
                node_id, 
                pax_counter_interval,
                pax_counter_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
                pax_counter_interval = NOW() - node_configurations.pax_counter_last_timestamp,
                pax_counter_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_neighbor_info_update(self, node_id: str):
        if not self.report:
            return

        def db_operation(cur, conn):
            cur.execute("""
            INSERT INTO node_configurations (
                node_id, 
                neighbor_info_interval,
                neighbor_info_last_timestamp
            ) VALUES (%s, %s, NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
                neighbor_info_interval = NOW() - node_configurations.neighbor_info_last_timestamp,
                neighbor_info_last_timestamp = NOW()
            """, (node_id, '0 seconds'))
            conn.commit()

        self.db.execute_db_operation(db_operation)

    def process_mqtt_update(self, node_id: str, mqtt_encryption_enabled=None, mqtt_json_enabled=None,
                            mqtt_configured_root_topic=None):
        if not self.report:
            return

        def db_operation(cur, conn):
            # Update the last MQTT message timestamp for every message
            cur.execute("""
            UPDATE node_configurations
            SET mqtt_info_last_timestamp = NOW()
            WHERE node_id = %s
            """, (node_id,))

            # If it's a JSON message, update the JSON message timestamp
            if mqtt_json_enabled:
                cur.execute("""
                UPDATE node_configurations
                SET mqtt_json_message_timestamp = NOW(),
                    mqtt_json_enabled = TRUE
                WHERE node_id = %s
                """, (node_id,))

            # Perform the main update
            cur.execute("""
            INSERT INTO node_configurations (
                node_id, 
                mqtt_encryption_enabled,
                mqtt_json_enabled,
                mqtt_configured_root_topic,
                mqtt_info_last_timestamp
            ) VALUES (%s, COALESCE(%s, FALSE), COALESCE(%s, FALSE), COALESCE(%s, ''), NOW())
            ON CONFLICT(node_id)
            DO UPDATE SET
                mqtt_encryption_enabled = COALESCE(EXCLUDED.mqtt_encryption_enabled, node_configurations.mqtt_encryption_enabled),
                mqtt_json_enabled = CASE
                    WHEN (node_configurations.mqtt_info_last_timestamp - node_configurations.mqtt_json_message_timestamp) > INTERVAL '1 hour'
                    THEN FALSE
                    ELSE COALESCE(EXCLUDED.mqtt_json_enabled, node_configurations.mqtt_json_enabled)
                END,
                mqtt_configured_root_topic = COALESCE(EXCLUDED.mqtt_configured_root_topic, node_configurations.mqtt_configured_root_topic),
                mqtt_info_last_timestamp = NOW()
            RETURNING mqtt_json_enabled
            """, (node_id, mqtt_encryption_enabled, mqtt_json_enabled, mqtt_configured_root_topic))
            conn.commit()

        self.db.execute_db_operation(db_operation)
