import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from meshtastic.mesh_pb2 import MeshPacket, Data, HardwareModel
from meshtastic.portnums_pb2 import PortNum
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge
from psycopg_pool import ConnectionPool

from exporter.registry import ProcessorRegistry, ClientDetails


class MessageProcessor:
    def __init__(self, registry: CollectorRegistry, db_pool: ConnectionPool):
        self.rx_rssi_gauge = None
        self.channel_counter = None
        self.packet_id_counter = None
        self.hop_start_gauge = None
        self.via_mqtt_counter = None
        self.want_ack_counter = None
        self.hop_limit_counter = None
        self.rx_snr_gauge = None
        self.rx_time_histogram = None
        self.total_packets_counter = None
        self.destination_message_type_counter = None
        self.source_message_type_counter = None
        self.registry = registry
        self.db_pool = db_pool
        self.init_metrics()
        self.processor_registry = ProcessorRegistry()

    def init_metrics(self):
        # Source-related counters
        self.source_message_type_counter = Counter(
            'mesh_packet_source_types',
            'Types of mesh packets processed by source',
            ['source_id', 'portnum'],
            registry=self.registry
        )
        # Destination-related counters
        self.destination_message_type_counter = Counter(
            'mesh_packet_destination_types',
            'Types of mesh packets processed by destination',
            ['destination_id', 'portnum'],
            registry=self.registry
        )
        # Counters for the total number of packets
        self.total_packets_counter = Counter(
            'mesh_packet_total',
            'Total number of mesh packets processed',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Histogram for the rx_time (time in seconds)
        self.rx_time_histogram = Histogram(
            'mesh_packet_rx_time',
            'Receive time of mesh packets (seconds since 1970)',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Gauge for the rx_snr (signal-to-noise ratio)
        self.rx_snr_gauge = Gauge(
            'mesh_packet_rx_snr',
            'Receive SNR of mesh packets',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Counter for hop_limit
        self.hop_limit_counter = Counter(
            'mesh_packet_hop_limit',
            'Hop limit of mesh packets',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Counter for want_ack (occurrences of want_ack set to true)
        self.want_ack_counter = Counter(
            'mesh_packet_want_ack',
            'Occurrences of want ACK for mesh packets',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Counter for via_mqtt (occurrences of via_mqtt set to true)
        self.via_mqtt_counter = Counter(
            'mesh_packet_via_mqtt',
            'Occurrences of mesh packets sent via MQTT',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Gauge for hop_start
        self.hop_start_gauge = Gauge(
            'mesh_packet_hop_start',
            'Hop start of mesh packets',
            ['source_id', 'destination_id'],
            registry=self.registry
        )
        # Counter for unique packet IDs
        self.packet_id_counter = Counter(
            'mesh_packet_ids',
            'Unique IDs for mesh packets',
            ['source_id', 'destination_id', 'packet_id'],
            registry=self.registry
        )
        # Counter for the channel used
        self.channel_counter = Counter(
            'mesh_packet_channel',
            'Channel used for mesh packets',
            ['source_id', 'destination_id', 'channel'],
            registry=self.registry
        )
        # Gauge for the rx_rssi (received signal strength indicator)
        self.rx_rssi_gauge = Gauge(
            'mesh_packet_rx_rssi',
            'Receive RSSI of mesh packets',
            ['source_id', 'destination_id'],
            registry=self.registry
        )

    def process(self, mesh_packet: MeshPacket):
        if getattr(mesh_packet, 'encrypted'):
            key_bytes = base64.b64decode(os.getenv('MQTT_SERVER_KEY', '1PG7OiApB1nwvP+rz05pAQ==').encode('ascii'))
            nonce_packet_id = getattr(mesh_packet, "id").to_bytes(8, "little")
            nonce_from_node = getattr(mesh_packet, "from").to_bytes(8, "little")

            # Put both parts into a single byte array.
            nonce = nonce_packet_id + nonce_from_node

            cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_bytes = decryptor.update(getattr(mesh_packet, "encrypted")) + decryptor.finalize()

            data = Data()
            data.ParseFromString(decrypted_bytes)
            mesh_packet.decoded.CopyFrom(data)
        port_num = int(mesh_packet.decoded.portnum)
        payload = mesh_packet.decoded.payload

        source_node_id = getattr(mesh_packet, 'from')
        source_client_details = self._get_client_details(source_node_id)
        if os.getenv('MESH_HIDE_SOURCE_DATA', 'false') == 'true':
            source_client_details = ClientDetails(node_id=source_client_details.node_id, short_name='Hidden',
                                                  long_name='Hidden')

        destination_node_id = getattr(mesh_packet, 'to')
        destination_client_details = self._get_client_details(destination_node_id)
        if os.getenv('MESH_HIDE_DESTINATION_DATA', 'false') == 'true':
            destination_client_details = ClientDetails(node_id=destination_client_details.node_id, short_name='Hidden',
                                                       long_name='Hidden')

        if port_num in map(int, os.getenv('FILTERED_PORTS', '1').split(',')):  # Filter out ports
            return None  # Ignore this packet

        self.process_simple_packet_details(destination_client_details, mesh_packet, port_num, source_client_details)

        processor = ProcessorRegistry.get_processor(port_num)(self.registry, self.db_pool)
        processor.process(payload, client_details=source_client_details)

    def get_port_name_from_portnum(self, port_num):
        descriptor = PortNum.DESCRIPTOR
        for enum_value in descriptor.values:
            if enum_value.number == port_num:
                return enum_value.name
        return 'UNKNOWN_PORT'

    def process_simple_packet_details(self, destination_client_details, mesh_packet, port_num, source_client_details):
        self.source_message_type_counter.labels(
            source_id=source_client_details.node_id,
            portnum=self.get_port_name_from_portnum(port_num)
        ).inc()

        self.destination_message_type_counter.labels(
            destination_id=destination_client_details.node_id,
            portnum=self.get_port_name_from_portnum(port_num)
        ).inc()

        # Increment the total packets counter
        self.total_packets_counter.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).inc()

        # Observe the rx_time in the histogram
        self.rx_time_histogram.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).observe(mesh_packet.rx_time)

        # Set the rx_snr in the gauge
        self.rx_snr_gauge.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).set(mesh_packet.rx_snr)

        # Increment the hop_limit counter
        self.hop_limit_counter.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).inc(mesh_packet.hop_limit)

        # Increment the want_ack counter if want_ack is true
        if mesh_packet.want_ack:
            self.want_ack_counter.labels(
                source_id=source_client_details.node_id,
                destination_id=destination_client_details.node_id
            ).inc()

        # Increment the via_mqtt counter if via_mqtt is true
        if mesh_packet.via_mqtt:
            self.via_mqtt_counter.labels(
                source_id=source_client_details.node_id,
                destination_id=destination_client_details.node_id
            ).inc()

        # Set the hop_start in the gauge
        self.hop_start_gauge.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).set(mesh_packet.hop_start)

        # Increment the unique packet ID counter
        self.packet_id_counter.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id,
            packet_id=mesh_packet.id
        ).inc()

        # Increment the channel counter
        self.channel_counter.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id,
            channel=mesh_packet.channel
        ).inc()

        # Set the rx_rssi in the gauge
        self.rx_rssi_gauge.labels(
            source_id=source_client_details.node_id,
            destination_id=destination_client_details.node_id
        ).set(mesh_packet.rx_rssi)

    def _get_client_details(self, node_id: int) -> ClientDetails:
        node_id_str = str(node_id)  # Convert the integer to a string
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                # First, try to select the existing record
                cur.execute("""
                    SELECT node_id, short_name, long_name, hardware_model, role 
                    FROM client_details 
                    WHERE node_id = %s;
                """, (node_id_str,))
                result = cur.fetchone()

                if not result:
                    # If the client is not found, insert a new record
                    cur.execute("""
                        INSERT INTO client_details (node_id, short_name, long_name, hardware_model, role)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING node_id, short_name, long_name, hardware_model, role;
                    """, (node_id_str, 'Unknown', 'Unknown', HardwareModel.UNSET, None))
                    conn.commit()
                    result = cur.fetchone()

        # At this point, we should always have a result, either from SELECT or INSERT
        return ClientDetails(
            node_id=result[0],
            short_name=result[1],
            long_name=result[2],
            hardware_model=result[3],
            role=result[4]
        )
