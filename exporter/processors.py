import json
import os

import redis
from meshtastic.config_pb2 import Config
from meshtastic.mesh_pb2 import MeshPacket, HardwareModel
from meshtastic.portnums_pb2 import PortNum
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge

from exporter.registry import ProcessorRegistry, ClientDetails


class MessageProcessor:
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
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
        self.redis_client = redis_client
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
        port_num = int(mesh_packet.decoded.portnum)
        payload = mesh_packet.decoded.payload

        source_client_details = self._get_client_details(getattr(mesh_packet, 'from'))
        if os.getenv('MESH_HIDE_SOURCE_DATA', 'false') == 'true':
            source_client_details = ClientDetails(node_id=source_client_details.node_id, short_name='Hidden',
                                                  long_name='Hidden')

        destination_client_details = self._get_client_details(getattr(mesh_packet, 'to'))
        if os.getenv('MESH_HIDE_DESTINATION_DATA', 'false') == 'true':
            destination_client_details = ClientDetails(node_id=destination_client_details.node_id, short_name='Hidden',
                                                       long_name='Hidden')

        if port_num in map(int, os.getenv('FILTERED_PORTS', '1').split(',')):  # Filter out ports
            return None  # Ignore this packet

        self.process_simple_packet_details(destination_client_details, mesh_packet, port_num, source_client_details)

        processor = ProcessorRegistry.get_processor(port_num)(self.registry, self.redis_client)
        processor.process(payload, client_details=source_client_details)

    def get_port_name_from_portnum(self, port_num):
        for name, value in PortNum.__dict__.items():
            if isinstance(value, int) and value == port_num:
                return name
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

    def _get_client_details(self, node_id: str) -> ClientDetails:
        user_details_json = self.redis_client.get(f"node:{node_id}")
        if user_details_json is not None:
            # Decode the JSON string to a Python dictionary
            user_details = json.loads(user_details_json)
            return ClientDetails(node_id=node_id,
                                 short_name=user_details.get('short_name', 'Unknown'),
                                 long_name=user_details.get('long_name', 'Unknown'),
                                 hardware_model=user_details.get('hardware_model', HardwareModel.UNSET),
                                 role=user_details.get('role', Config.DeviceConfig.Role.ValueType),
                                 )

        return ClientDetails(node_id=node_id)
