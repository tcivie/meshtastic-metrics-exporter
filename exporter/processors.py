from meshtastic.mesh_pb2 import MeshPacket
from prometheus_client import CollectorRegistry

from exporter.registry import ProcessorRegistry


class MessageProcessor:
    def __init__(self, registry: CollectorRegistry):
        self.registry = registry

    def process(self, mesh_packet: MeshPacket):
        port_num = mesh_packet.decoded.portnum
        payload = mesh_packet.decoded.payload
        processor = ProcessorRegistry.get_processor(port_num)(self.registry)

        processor.process(payload)
