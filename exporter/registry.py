import json
import os
from abc import ABC, abstractmethod
from venv import logger

import redis
import unishox2
from meshtastic.admin_pb2 import AdminMessage
from meshtastic.config_pb2 import Config
from meshtastic.mesh_pb2 import Position, User, Routing, Waypoint, RouteDiscovery, NeighborInfo, HardwareModel
from meshtastic.mqtt_pb2 import MapReport
from meshtastic.paxcount_pb2 import Paxcount
from meshtastic.portnums_pb2 import PortNum
from meshtastic.remote_hardware_pb2 import HardwareMessage
from meshtastic.storeforward_pb2 import StoreAndForward
from meshtastic.telemetry_pb2 import Telemetry, DeviceMetrics, EnvironmentMetrics, AirQualityMetrics, PowerMetrics
from prometheus_client import CollectorRegistry, Counter, Gauge


class _Metrics:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(_Metrics, cls).__new__(cls)
        return cls._instance

    def __init__(self, registry: CollectorRegistry):
        if not hasattr(self, 'initialized'):  # Ensuring __init__ runs only once
            self._registry = registry
            self._init_metrics()
            self.initialized = True  # Attribute to indicate initialization

    def _init_metrics(self):  # TODO: Go over the metrics and rethink some of them to be more like the longtitute and
        # latitude - The values should represent something and we shouldn't just label stuff. Also, the labels should
        # be less used looked upon like keys for the data
        self.message_counter = Counter(
            'text_message_app',
            'Text message app payload details',
            ['client_id', 'short_name', 'long_name', 'message_content'],
            registry=self._registry
        )
        self.telemetry_counter_device_metrics = Counter(
            'telemetry_app_device_metrics',
            'Telemetry app payload details - Device metrics',
            ['client_id', 'short_name', 'long_name'
                                        'battery_level', 'voltage', 'channel_utilization', 'air_until_tx',
             'uptime_seconds'
             ],
            registry=self._registry
        )
        self.telemetry_counter_environment_metrics = Counter(
            'telemetry_app_environment_metrics',
            'Telemetry app payload details - Environment metrics',
            ['client_id', 'short_name', 'long_name'
                                        'temperature', 'relative_humidity', 'barometric_pressure', 'gas_resistance',
             'voltage', 'current', 'iaq', 'distance', 'lux', 'white_lux', 'ir_lux', 'uv_lux', 'wind_direction',
             'wind_speed', 'weight'
             ],
            registry=self._registry
        )
        self.telemetry_counter_air_quality_metrics = Counter(
            'telemetry_app_air_quality_metrics',
            'Telemetry app payload details - Air quality metrics',
            ['client_id', 'short_name', 'long_name'
                                        'pm10_standard', 'pm25_standard', 'pm100_standard', 'pm10_environmental',
             'pm25_environmental', 'pm100_environmental', 'particles_03um', 'particles_05um', 'particles_10um',
             'particles_25um', 'particles_50um', 'particles_100um'
             ],
            registry=self._registry
        )
        self.telemetry_counter_power_metrics = Counter(
            'telemetry_app_power_metrics',
            'Telemetry app payload details - Power metrics',
            ['client_id', 'short_name', 'long_name'
                                        'ch1_voltage', 'ch1_current', 'ch2_voltage', 'ch2_current', 'ch3_voltage',
             'ch3_current'
             ],
            registry=self._registry
        )
        self.device_latitude_gauge = Gauge(
            'device_latitude',
            'Device latitude',
            ['client_id', 'short_name', 'long_name'],
            registry=self._registry
        )
        self.device_longitude_gauge = Gauge(
            'device_longitude',
            'Device longitude',
            ['client_id', 'short_name', 'long_name'],
            registry=self._registry
        )
        self.device_altitude_gauge = Gauge(
            'device_altitude',
            'Device altitude',
            ['client_id', 'short_name', 'long_name'],
            registry=self._registry
        )
        self.device_position_precision_gauge = Gauge(
            'device_position_precision',
            'Device position precision',
            ['client_id', 'short_name', 'long_name'],
            registry=self._registry
        )


class ClientDetails:
    def __init__(self, node_id, short_name='Unknown', long_name='Unknown', hardware_model=HardwareModel.UNSET,
                 role=None):
        self.node_id = node_id
        self.short_name = short_name
        self.long_name = long_name
        self.hardware_model: HardwareModel = hardware_model
        self.role: Config.DeviceConfig.Role = role


class Processor(ABC):
    def __init__(self, registry: CollectorRegistry, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.metrics = _Metrics(registry)

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

    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TEXT_MESSAGE_APP packet")
        message = payload.decode('utf-8')
        if os.getenv('HIDE_MESSAGE', 'true') == 'true':
            message = 'Hidden'
        self.metrics.message_counter.labels(
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
        self.metrics.device_latitude_gauge.labels(
            client_id=client_details.node_id,
            short_name=client_details.short_name,
            long_name=client_details.long_name
        ).set(position.latitude_i)
        self.metrics.device_longitude_gauge.labels(
            client_id=client_details.node_id,
            short_name=client_details.short_name,
            long_name=client_details.long_name
        ).set(position.longitude_i)
        self.metrics.device_altitude_gauge.labels(
            client_id=client_details.node_id,
            short_name=client_details.short_name,
            long_name=client_details.long_name
        ).set(position.altitude)
        self.metrics.device_position_precision_gauge.labels(
            client_id=client_details.node_id,
            short_name=client_details.short_name,
            long_name=client_details.long_name
        ).set(position.position_precision)
        pass


@ProcessorRegistry.register_processor(PortNum.NODEINFO_APP)
class NodeInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NODEINFO_APP packet")
        user = User()
        user.ParseFromString(payload)
        user_details = {
            'short_name': user.short_name,
            'long_name': user.long_name,
            'id': user.id,
            'hardware_model': user.hardware_model,
            'role': user.role,
        }
        user_details_json = json.dumps(user_details)
        self.redis_client.set(f"node:{client_details.node_id}", user_details_json)
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
        if telemetry.HasField('device_metrics'):
            device_metrics: DeviceMetrics = telemetry.device_metrics
            self.metrics.telemetry_counter_device_metrics.labels(
                client_id=client_details.node_id,
                short_name=client_details.short_name,
                long_name=client_details.long_name,
                battery_level=device_metrics.battery_level,
                voltage=device_metrics.voltage,
                channel_utilization=device_metrics.channel_utilization,
                air_until_tx=device_metrics.air_until_tx,
                uptime_seconds=device_metrics.uptime_seconds
            ).inc()
        if telemetry.HasField('environment_metrics'):
            environment_metrics: EnvironmentMetrics = telemetry.environment_metrics
            self.metrics.telemetry_counter_environment_metrics.labels(
                client_id=client_details.node_id,
                short_name=client_details.short_name,
                long_name=client_details.long_name,
                temperature=environment_metrics.temperature,
                relative_humidity=environment_metrics.relative_humidity,
                barometric_pressure=environment_metrics.barometric_pressure,
                gas_resistance=environment_metrics.gas_resistance,
                voltage=environment_metrics.voltage,
                current=environment_metrics.current,
                iaq=environment_metrics.iaq,
                distance=environment_metrics.distance,
                lux=environment_metrics.lux,
                white_lux=environment_metrics.white_lux,
                ir_lux=environment_metrics.ir_lux,
                uv_lux=environment_metrics.uv_lux,
                wind_direction=environment_metrics.wind_direction,
                wind_speed=environment_metrics.wind_speed,
                weight=environment_metrics.weight
            ).inc()
        if telemetry.HasField('air_quality_metrics'):
            air_quality_metrics: AirQualityMetrics = telemetry.air_quality_metrics
            self.metrics.telemetry_counter_air_quality_metrics.labels(
                client_id=client_details.node_id,
                short_name=client_details.short_name,
                long_name=client_details.long_name,
                pm10_standard=air_quality_metrics.pm10_standard,
                pm25_standard=air_quality_metrics.pm25_standard,
                pm100_standard=air_quality_metrics.pm100_standard,
                pm10_environmental=air_quality_metrics.pm10_environmental,
                pm25_environmental=air_quality_metrics.pm25_environmental,
                pm100_environmental=air_quality_metrics.pm100_environmental,
                particles_03um=air_quality_metrics.particles_03um,
                particles_05um=air_quality_metrics.particles_05um,
                particles_10um=air_quality_metrics.particles_10um,
                particles_25um=air_quality_metrics.particles_25um,
                particles_50um=air_quality_metrics.particles_50um,
                particles_100um=air_quality_metrics.particles_100um
            ).inc()
        if telemetry.HasField('power_metrics'):
            power_metrics: PowerMetrics = telemetry.power_metrics
            self.metrics.telemetry_counter_power_metrics.labels(
                client_id=client_details.node_id,
                short_name=client_details.short_name,
                long_name=client_details.long_name,
                ch1_voltage=power_metrics.ch1_voltage,
                ch1_current=power_metrics.ch1_current,
                ch2_voltage=power_metrics.ch2_voltage,
                ch2_current=power_metrics.ch2_current,
                ch3_voltage=power_metrics.ch3_voltage,
                ch3_current=power_metrics.ch3_current
            ).inc()


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
