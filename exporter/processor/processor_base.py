import base64
import json
import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from meshtastic.mesh_pb2 import Data, HardwareModel, MeshPacket
    from meshtastic.mqtt_pb2 import ServiceEnvelope
    from meshtastic.portnums_pb2 import PortNum
except ImportError:
    from meshtastic.protobuf.mesh_pb2 import Data, HardwareModel, MeshPacket
    from meshtastic.protobuf.mqtt_pb2 import ServiceEnvelope
    from meshtastic.protobuf.portnums_pb2 import PortNum

from psycopg_pool import ConnectionPool

from exporter.client_details import ClientDetails
from exporter.db_handler import BROADCAST_NODE_IDS, DBHandler
from exporter.processor.processors import ProcessorRegistry

DEFAULT_MQTT_KEY = "1PG7OiApB1nwvP+rz05pAQ=="
HIDDEN = "Hidden"


class MessageProcessor:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool
        self.db_handler = DBHandler(db_pool)
        self.processor_registry = ProcessorRegistry()

    @staticmethod
    def process_json_mqtt(message):
        json.loads(message.payload)

    @staticmethod
    def process_mqtt(
        topic: str,
        service_envelope: ServiceEnvelope,
        mesh_packet: MeshPacket,
    ):
        # Hook kept for future per-gateway/per-topic accounting; current
        # implementation is a no-op now that node_configurations is
        # maintained by the scheduled job.
        del topic, service_envelope, mesh_packet

    def process(self, mesh_packet: MeshPacket):
        try:
            if getattr(mesh_packet, "encrypted"):
                if not self._decrypt(mesh_packet):
                    return

            port_num = int(mesh_packet.decoded.portnum)
            payload = mesh_packet.decoded.payload

            source = self._client_details_for(
                getattr(mesh_packet, "from"), "MESH_HIDE_SOURCE_DATA"
            )
            destination = self._client_details_for(
                getattr(mesh_packet, "to"), "MESH_HIDE_DESTINATION_DATA"
            )

            self._record_packet(source, destination, mesh_packet, port_num)
            ProcessorRegistry.get_processor(port_num)(self.db_pool).process(
                payload, client_details=source
            )
        except Exception as e:
            logging.debug(f"Failed to process message: {e}")

    @staticmethod
    def get_port_name_from_portnum(port_num) -> str:
        for enum_value in PortNum.DESCRIPTOR.values:
            if enum_value.number == port_num:
                return enum_value.name
        return "UNKNOWN_PORT"

    # ---------- internals ----------

    def _decrypt(self, mesh_packet: MeshPacket) -> bool:
        key_bytes = base64.b64decode(
            os.getenv("MQTT_SERVER_KEY", DEFAULT_MQTT_KEY).encode("ascii")
        )
        nonce = getattr(mesh_packet, "id").to_bytes(8, "little") + getattr(
            mesh_packet, "from"
        ).to_bytes(8, "little")
        cipher = Cipher(
            algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decrypted = (
            decryptor.update(getattr(mesh_packet, "encrypted")) + decryptor.finalize()
        )
        data = Data()
        try:
            data.ParseFromString(decrypted)
        except Exception as e:
            sender = getattr(mesh_packet, "from", 0)
            packet_id = getattr(mesh_packet, "id", 0)
            logging.debug(
                f"Failed to decrypt packet {packet_id} from node {sender:x}: {e}"
            )
            return False
        mesh_packet.decoded.CopyFrom(data)
        return True

    def _client_details_for(self, node_id: int, hide_env_var: str) -> ClientDetails:
        details = self._get_client_details(node_id)
        if os.getenv(hide_env_var, "false").lower() == "true":
            return ClientDetails(
                node_id=details.node_id, short_name=HIDDEN, long_name=HIDDEN
            )
        return details

    def _record_packet(
        self,
        source: ClientDetails,
        destination: ClientDetails,
        mesh_packet: MeshPacket,
        port_num: int,
    ):
        self.db_handler.store_mesh_packet_metrics(
            source.node_id,
            destination.node_id,
            {
                "portnum": self.get_port_name_from_portnum(port_num),
                "packet_id": mesh_packet.id,
                "channel": mesh_packet.channel,
                "rx_time": mesh_packet.rx_time,
                "rx_snr": mesh_packet.rx_snr,
                "rx_rssi": mesh_packet.rx_rssi,
                "hop_limit": mesh_packet.hop_limit,
                "hop_start": mesh_packet.hop_start,
                "want_ack": mesh_packet.want_ack,
                "via_mqtt": mesh_packet.via_mqtt,
                "message_size_bytes": mesh_packet.ByteSize(),
            },
        )

    def _get_client_details(self, node_id: int) -> ClientDetails:
        node_id_str = str(node_id)
        if node_id_str in BROADCAST_NODE_IDS:
            self._upsert_broadcast(node_id_str)
            return ClientDetails(
                node_id=node_id_str, short_name="Broadcast", long_name="Broadcast"
            )
        return self._fetch_or_create_node(node_id_str)

    def _upsert_broadcast(self, node_id: str):
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO node_details
                        (node_id, short_name, long_name, hardware_model, role)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (node_id) DO NOTHING
                    """,
                    (node_id, "Broadcast", "Broadcast", "BROADCAST", "BROADCAST"),
                )
                conn.commit()

    def _fetch_or_create_node(self, node_id: str) -> ClientDetails:
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT node_id, short_name, long_name, hardware_model, role "
                    "FROM node_details WHERE node_id = %s",
                    (node_id,),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "INSERT INTO node_details "
                        "(node_id, short_name, long_name, hardware_model, role) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "RETURNING node_id, short_name, long_name, hardware_model, role",
                        (node_id, "Unknown", "Unknown", HardwareModel.UNSET, None),
                    )
                    row = cur.fetchone()
                    conn.commit()
        return ClientDetails(
            node_id=row[0],
            short_name=row[1],
            long_name=row[2],
            hardware_model=row[3],
            role=row[4],
        )
