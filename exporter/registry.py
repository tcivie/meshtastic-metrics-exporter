import os
from abc import ABC, abstractmethod
from venv import logger

import redis
import unishox2
from meshtastic.admin_pb2 import AdminMessage
from meshtastic.mesh_pb2 import Position, User, Routing, Waypoint, RouteDiscovery, NeighborInfo
from meshtastic.mqtt_pb2 import MapReport
from meshtastic.paxcount_pb2 import Paxcount
from meshtastic.portnums_pb2 import PortNum
from meshtastic.remote_hardware_pb2 import HardwareMessage
from meshtastic.storeforward_pb2 import StoreAndForward
from meshtastic.telemetry_pb2 import Telemetry
from prometheus_client import CollectorRegistry, Counter


class ClientDetails:
    def __init__(self, node_id, short_name, long_name):
        self.node_id = node_id
        self.short_name = short_name
        self.long_name = long_name


class Processor(ABC):
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
        self.registry = registry
        self.redis_client = redis_client

    @abstractmethod
    def process(self, payload: bytes, client_details: ClientDetails):
        pass


class ProcessorRegistry:
    _registry = {}

    @classmethod
    def register_processor(cls, port_num):
        def inner_wrapper(wrapped_class):
            cls._registry[port_num] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_processor(cls, port_num) -> type(Processor):
        return cls._registry.get(port_num, UnknownAppProcessor)


@ProcessorRegistry.register_processor(PortNum.UNKNOWN_APP)
class UnknownAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received UNKNOWN_APP packet")
        return None


@ProcessorRegistry.register_processor(PortNum.TEXT_MESSAGE_APP)
class TextMessageAppProcessor(Processor):
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
        super().__init__(registry, redis_client)
        self.message_counter = Counter(
            'text_message_app',
            'Text message app payload details',
            ['client_id', 'short_name', 'long_name', 'message_content'],
            registry=self.registry
        )

    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TEXT_MESSAGE_APP packet")
        message = payload.decode('utf-8')
        if os.getenv('HIDE_MESSAGE', 'true') == 'true':
            message = 'Hidden'
        self.message_counter.labels(
            client_id=client_details.node_id,
            short_name=client_details.short_name,
            long_name=client_details.long_name,
            message_content=message
        ).inc()


@ProcessorRegistry.register_processor(PortNum.REMOTE_HARDWARE_APP)
class RemoteHardwareAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received REMOTE_HARDWARE_APP packet")
        hardware_message = HardwareMessage()
        hardware_message.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.POSITION_APP)
class PositionAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received POSITION_APP packet")
        position = Position()
        position.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.NODEINFO_APP)
class NodeInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NODEINFO_APP packet")
        user = User()
        user.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.ROUTING_APP)
class RoutingAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ROUTING_APP packet")
        routing = Routing()
        routing.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.ADMIN_APP)
class AdminAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ADMIN_APP packet")
        admin_message = AdminMessage()
        admin_message.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.TEXT_MESSAGE_COMPRESSED_APP)
class TextMessageCompressedAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TEXT_MESSAGE_COMPRESSED_APP packet")
        decompressed_payload = unishox2.decompress(payload, len(payload))
        pass


@ProcessorRegistry.register_processor(PortNum.WAYPOINT_APP)
class WaypointAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received WAYPOINT_APP packet")
        waypoint = Waypoint()
        waypoint.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.AUDIO_APP)
class AudioAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received AUDIO_APP packet")
        pass  # NOTE: Audio packet. should probably be processed


@ProcessorRegistry.register_processor(PortNum.DETECTION_SENSOR_APP)
class DetectionSensorAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received DETECTION_SENSOR_APP packet")
        pass  # NOTE: This portnum traffic is not sent to the public MQTT starting at firmware version 2.2.9


@ProcessorRegistry.register_processor(PortNum.REPLY_APP)
class ReplyAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received REPLY_APP packet")
        pass  # NOTE: Provides a 'ping' service that replies to any packet it receives. This is useful for testing.


@ProcessorRegistry.register_processor(PortNum.IP_TUNNEL_APP)
class IpTunnelAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received IP_TUNNEL_APP packet")
        pass  # NOTE: IP Packet. Handled by the python API, firmware ignores this one and passes it on.


@ProcessorRegistry.register_processor(PortNum.PAXCOUNTER_APP)
class PaxCounterAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received PAXCOUNTER_APP packet")
        paxcounter = Paxcount()
        paxcounter.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.SERIAL_APP)
class SerialAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received SERIAL_APP packet")
        pass  # NOTE: Provides a hardware serial interface to send and receive from the Meshtastic network.


@ProcessorRegistry.register_processor(PortNum.STORE_FORWARD_APP)
class StoreForwardAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received STORE_FORWARD_APP packet")
        store_and_forward = StoreAndForward()
        store_and_forward.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.RANGE_TEST_APP)
class RangeTestAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received RANGE_TEST_APP packet")
        pass  # NOTE: This portnum traffic is not sent to the public MQTT starting at firmware version 2.2.9


@ProcessorRegistry.register_processor(PortNum.TELEMETRY_APP)
class TelemetryAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TELEMETRY_APP packet")
        telemetry = Telemetry()
        telemetry.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.ZPS_APP)
class ZpsAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ZPS_APP packet")
        pass  # NOTE: Experimental tools for estimating node position without a GPS


@ProcessorRegistry.register_processor(PortNum.SIMULATOR_APP)
class SimulatorAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received SIMULATOR_APP packet")
        pass  # NOTE: Used to let multiple instances of Linux native applications communicate as if they did using their LoRa chip.


@ProcessorRegistry.register_processor(PortNum.TRACEROUTE_APP)
class TraceRouteAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TRACEROUTE_APP packet")
        traceroute = RouteDiscovery()
        traceroute.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.NEIGHBORINFO_APP)
class NeighborInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NEIGHBORINFO_APP packet")
        neighbor_info = NeighborInfo()
        neighbor_info.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.ATAK_PLUGIN)
class AtakPluginProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ATAK_PLUGIN packet")
        pass  # NOTE: ATAK Plugin


@ProcessorRegistry.register_processor(PortNum.MAP_REPORT_APP)
class MapReportAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received MAP_REPORT_APP packet")
        map_report = MapReport()
        map_report.ParseFromString(payload)
        pass


@ProcessorRegistry.register_processor(PortNum.PRIVATE_APP)
class PrivateAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received PRIVATE_APP packet")
        pass  # NOTE: Private application portnum


@ProcessorRegistry.register_processor(PortNum.ATAK_FORWARDER)
class AtakForwarderProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ATAK_FORWARDER packet")
        pass  # NOTE: ATAK Forwarder


@ProcessorRegistry.register_processor(PortNum.MAX)
class MaxProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received MAX packet")
        pass  # NOTE: Maximum portnum value
