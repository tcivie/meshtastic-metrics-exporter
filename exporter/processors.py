import redis
from meshtastic.mesh_pb2 import MeshPacket
from prometheus_client import CollectorRegistry, Counter

from exporter.registry import ProcessorRegistry


class MessageProcessor:
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
        self.registry = registry
        self.redis_client = redis_client
        self.counter = Counter('mesh_packets', 'Number of mesh packets processed',
                               ['source_id', 'source_short_name', 'source_long_name', 'portnum'],
                               registry=self.registry)

    def process(self, mesh_packet: MeshPacket):
        port_num = mesh_packet.decoded.portnum
        payload = mesh_packet.decoded.payload
        processor = ProcessorRegistry.get_processor(port_num)(self.registry, self.redis_client)

        client_details = self._get_client_details(mesh_packet)
        self.counter.labels(
            source_id=client_details['id'],
            source_short_name=client_details['short_name'],
            source_long_name=client_details['long_name'],
            portnum=port_num
        ).inc()
        processor.process_packet(payload)

    def _get_client_details(self, mesh_packet: MeshPacket):
        from_id = mesh_packet['from']

        details = self.redis_client.hgetall(f"node:{from_id}")
        if details:
            return details

        return {
            'id': from_id,
            'short_name': 'Unknown',
            'long_name': 'Unknown',
        }
