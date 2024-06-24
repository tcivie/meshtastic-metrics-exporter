import os

import redis
from meshtastic.config_pb2 import Config
from meshtastic.mesh_pb2 import MeshPacket, HardwareModel
from prometheus_client import CollectorRegistry, Counter

from exporter.registry import ProcessorRegistry, ClientDetails


class MessageProcessor:
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
        self.registry = registry
        self.redis_client = redis_client
        self.counter = Counter('mesh_packets', 'Number of mesh packets processed',
                               [
                                   'source_id', 'source_short_name', 'source_long_name',
                                   'destination_id', 'destination_short_name', 'destination_long_name',
                                   'portnum',
                                   'rx_time', 'rx_snr', 'hop_limit', 'want_ack', 'via_mqtt', 'hop_start'
                               ],
                               registry=self.registry)
        self.processor_registry = ProcessorRegistry()

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

        self.counter.labels(
            source_id=source_client_details.node_id,
            source_short_name=source_client_details.short_name,
            source_long_name=source_client_details.long_name,

            destination_id=destination_client_details.node_id,
            destination_short_name=destination_client_details.short_name,
            destination_long_name=destination_client_details.long_name,

            rx_time=mesh_packet.rx_time,
            rx_snr=mesh_packet.rx_snr,
            hop_limit=mesh_packet.hop_limit,
            want_ack=mesh_packet.want_ack,
            via_mqtt=mesh_packet.via_mqtt,
            hop_start=mesh_packet.hop_start,
            portnum=port_num
        ).inc()

        processor = ProcessorRegistry.get_processor(port_num)(self.registry, self.redis_client)
        processor.process(payload, client_details=source_client_details)

    def _get_client_details(self, node_id: str) -> ClientDetails:
        details = self.redis_client.hgetall(f"node:{node_id}")
        if details:
            return ClientDetails(node_id=node_id,
                                 short_name=details.get('short_name', 'Unknown'),
                                 long_name=details.get('long_name', 'Unknown'),
                                 hardware_model=details.get('hardware_model', HardwareModel.UNSET),
                                 role=details.get('role', Config.DeviceConfig.Role.ValueType.UNSET),
                                 )

        return ClientDetails(node_id=node_id)
