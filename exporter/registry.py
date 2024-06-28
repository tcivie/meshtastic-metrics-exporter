import os
from abc import ABC, abstractmethod
from venv import logger

import psycopg
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
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from psycopg_pool import ConnectionPool


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
        # Histogram for the length of messages
        self._init_metrics_text_message()
        self._init_metrics_telemetry_device()
        self._init_metrics_telemetry_environment()
        self._init_metrics_telemetry_air_quality()
        self._init_metrics_telemetry_power()
        self._init_metrics_position()
        self._init_route_discovery_metrics()

    def _init_metrics_text_message(self):
        self.message_length_histogram = Histogram(
            'text_message_app_length',
            'Length of text messages processed by the app',
            ['client_id'],
            registry=self._registry
        )

    def _init_metrics_position(self):
        self.device_latitude_gauge = Gauge(
            'device_latitude',
            'Device latitude',
            ['client_id'],
            registry=self._registry
        )
        self.device_longitude_gauge = Gauge(
            'device_longitude',
            'Device longitude',
            ['client_id'],
            registry=self._registry
        )
        self.device_altitude_gauge = Gauge(
            'device_altitude',
            'Device altitude',
            ['client_id'],
            registry=self._registry
        )
        self.device_position_precision_gauge = Gauge(
            'device_position_precision',
            'Device position precision',
            ['client_id'],
            registry=self._registry
        )

    def _init_metrics_telemetry_power(self):
        self.ch1_voltage_gauge = Gauge(
            'telemetry_app_ch1_voltage',
            'Voltage measured by the device on channel 1',
            ['client_id'],
            registry=self._registry
        )

        self.ch1_current_gauge = Gauge(
            'telemetry_app_ch1_current',
            'Current measured by the device on channel 1',
            ['client_id'],
            registry=self._registry
        )

        self.ch2_voltage_gauge = Gauge(
            'telemetry_app_ch2_voltage',
            'Voltage measured by the device on channel 2',
            ['client_id'],
            registry=self._registry
        )

        self.ch2_current_gauge = Gauge(
            'telemetry_app_ch2_current',
            'Current measured by the device on channel 2',
            ['client_id'],
            registry=self._registry
        )

        self.ch3_voltage_gauge = Gauge(
            'telemetry_app_ch3_voltage',
            'Voltage measured by the device on channel 3',
            ['client_id'],
            registry=self._registry
        )

        self.ch3_current_gauge = Gauge(
            'telemetry_app_ch3_current',
            'Current measured by the device on channel 3',
            ['client_id'],
            registry=self._registry
        )

    def _init_metrics_telemetry_air_quality(self):
        self.pm10_standard_gauge = Gauge(
            'telemetry_app_pm10_standard',
            'Concentration Units Standard PM1.0',
            ['client_id'],
            registry=self._registry
        )

        self.pm25_standard_gauge = Gauge(
            'telemetry_app_pm25_standard',
            'Concentration Units Standard PM2.5',
            ['client_id'],
            registry=self._registry
        )

        self.pm100_standard_gauge = Gauge(
            'telemetry_app_pm100_standard',
            'Concentration Units Standard PM10.0',
            ['client_id'],
            registry=self._registry
        )

        self.pm10_environmental_gauge = Gauge(
            'telemetry_app_pm10_environmental',
            'Concentration Units Environmental PM1.0',
            ['client_id'],
            registry=self._registry
        )

        self.pm25_environmental_gauge = Gauge(
            'telemetry_app_pm25_environmental',
            'Concentration Units Environmental PM2.5',
            ['client_id'],
            registry=self._registry
        )

        self.pm100_environmental_gauge = Gauge(
            'telemetry_app_pm100_environmental',
            'Concentration Units Environmental PM10.0',
            ['client_id'],
            registry=self._registry
        )

        self.particles_03um_gauge = Gauge(
            'telemetry_app_particles_03um',
            '0.3um Particle Count',
            ['client_id'],
            registry=self._registry
        )

        self.particles_05um_gauge = Gauge(
            'telemetry_app_particles_05um',
            '0.5um Particle Count',
            ['client_id'],
            registry=self._registry
        )

        self.particles_10um_gauge = Gauge(
            'telemetry_app_particles_10um',
            '1.0um Particle Count',
            ['client_id'],
            registry=self._registry
        )

        self.particles_25um_gauge = Gauge(
            'telemetry_app_particles_25um',
            '2.5um Particle Count',
            ['client_id'],
            registry=self._registry
        )

        self.particles_50um_gauge = Gauge(
            'telemetry_app_particles_50um',
            '5.0um Particle Count',
            ['client_id'],
            registry=self._registry
        )

        self.particles_100um_gauge = Gauge(
            'telemetry_app_particles_100um',
            '10.0um Particle Count',
            ['client_id'],
            registry=self._registry
        )

    def _init_metrics_telemetry_environment(self):
        # Define gauges for environment metrics
        self.temperature_gauge = Gauge(
            'telemetry_app_temperature',
            'Temperature measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.relative_humidity_gauge = Gauge(
            'telemetry_app_relative_humidity',
            'Relative humidity percent measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.barometric_pressure_gauge = Gauge(
            'telemetry_app_barometric_pressure',
            'Barometric pressure in hPA measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.gas_resistance_gauge = Gauge(
            'telemetry_app_gas_resistance',
            'Gas resistance in MOhm measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.iaq_gauge = Gauge(
            'telemetry_app_iaq',
            'IAQ value measured by the device (0-500)',
            ['client_id'],
            registry=self._registry
        )

        self.distance_gauge = Gauge(
            'telemetry_app_distance',
            'Distance measured by the device in mm',
            ['client_id'],
            registry=self._registry
        )

        self.lux_gauge = Gauge(
            'telemetry_app_lux',
            'Ambient light measured by the device in Lux',
            ['client_id'],
            registry=self._registry
        )

        self.white_lux_gauge = Gauge(
            'telemetry_app_white_lux',
            'White light measured by the device in Lux',
            ['client_id'],
            registry=self._registry
        )

        self.ir_lux_gauge = Gauge(
            'telemetry_app_ir_lux',
            'Infrared light measured by the device in Lux',
            ['client_id'],
            registry=self._registry
        )

        self.uv_lux_gauge = Gauge(
            'telemetry_app_uv_lux',
            'Ultraviolet light measured by the device in Lux',
            ['client_id'],
            registry=self._registry
        )

        self.wind_direction_gauge = Gauge(
            'telemetry_app_wind_direction',
            'Wind direction in degrees measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.wind_speed_gauge = Gauge(
            'telemetry_app_wind_speed',
            'Wind speed in m/s measured by the device',
            ['client_id'],
            registry=self._registry
        )

        self.weight_gauge = Gauge(
            'telemetry_app_weight',
            'Weight in KG measured by the device',
            ['client_id'],
            registry=self._registry
        )

    def _init_metrics_telemetry_device(self):
        self.battery_level_gauge = Gauge(
            'telemetry_app_battery_level',
            'Battery level of the device (0-100, >100 means powered)',
            ['client_id'],
            registry=self._registry
        )

        self.voltage_gauge = Gauge(
            'telemetry_app_voltage',
            'Voltage measured by the device',
            ['client_id'],
            registry=self._registry
        )

        # Define gauges for channel utilization and air utilization for TX
        self.channel_utilization_gauge = Gauge(
            'telemetry_app_channel_utilization',
            'Utilization for the current channel, including well-formed TX, RX, and noise',
            ['client_id'],
            registry=self._registry
        )

        self.air_util_tx_gauge = Gauge(
            'telemetry_app_air_util_tx',
            'Percent of airtime for transmission used within the last hour',
            ['client_id'],
            registry=self._registry
        )

        # Define a counter for uptime in seconds
        self.uptime_seconds_counter = Counter(
            'telemetry_app_uptime_seconds',
            'How long the device has been running since the last reboot (in seconds)',
            ['client_id'],
            registry=self._registry
        )

    def _init_route_discovery_metrics(self):
        self.route_discovery_counter = Counter(
            'route_length',
            'Number of nodes in the route',
            ['client_id'],
            registry=self._registry
        )
        self.route_discovery_response_counter = Counter(
            'route_response',
            'Number of responses to route discovery',
            ['client_id', 'response_type'],
            registry=self._registry
        )


def get_hardware_model_name_from_code(hardware_model):
    descriptor = HardwareModel.DESCRIPTOR
    for enum_value in descriptor.values:
        if enum_value.number == hardware_model:
            return enum_value.name
    return 'UNKNOWN_HARDWARE_MODEL'


def get_role_name_from_role(role):
    descriptor = Config.DeviceConfig.Role.DESCRIPTOR
    for enum_value in descriptor.values:
        if enum_value.number == role:
            return enum_value.name
    return 'UNKNOWN_ROLE'


class ClientDetails:
    def __init__(self, node_id, short_name='Unknown', long_name='Unknown', hardware_model=HardwareModel.UNSET,
                 role=None):
        self.node_id = node_id
        self.short_name = short_name
        self.long_name = long_name
        self.hardware_model: HardwareModel = hardware_model
        self.role: Config.DeviceConfig.Role = role

    def to_dict(self):
        return {
            'node_id': self.node_id,
            'short_name': self.short_name,
            'long_name': self.long_name,
            'hardware_model': get_hardware_model_name_from_code(self.hardware_model),
            'role': get_role_name_from_role(self.role)
        }


class Processor(ABC):
    def __init__(self, registry: CollectorRegistry, db_pool: ConnectionPool):
        self.db_pool = db_pool
        self.metrics = _Metrics(registry)

    @abstractmethod
    def process(self, payload: bytes, client_details: ClientDetails):
        pass

    def execute_db_operation(self, operation):
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                return operation(cur, conn)


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
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TEXT_MESSAGE_APP packet")
        message = payload.decode('utf-8')
        if os.getenv('HIDE_MESSAGE', 'true') == 'true':
            message = 'Hidden'
        self.metrics.message_length_histogram.labels(
            client_id=client_details.node_id
        ).observe(len(message))


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
        ).set(position.latitude_i)
        self.metrics.device_longitude_gauge.labels(
            client_id=client_details.node_id,
        ).set(position.longitude_i)
        self.metrics.device_altitude_gauge.labels(
            client_id=client_details.node_id,
        ).set(position.altitude)
        self.metrics.device_position_precision_gauge.labels(
            client_id=client_details.node_id,
        ).set(position.precision_bits)
        pass


@ProcessorRegistry.register_processor(PortNum.NODEINFO_APP)
class NodeInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NODEINFO_APP packet")
        user = User()
        user.ParseFromString(payload)

        def db_operation(cur, conn):
            # First, try to select the existing record
            cur.execute("""
                SELECT short_name, long_name, hardware_model, role
                FROM client_details
                WHERE node_id = %s;
            """, (client_details.node_id,))
            existing_record = cur.fetchone()

            if existing_record:
                # If record exists, update only the fields that are provided in the new data
                update_fields = []
                update_values = []
                if user.short_name:
                    update_fields.append("short_name = %s")
                    update_values.append(user.short_name)
                if user.long_name:
                    update_fields.append("long_name = %s")
                    update_values.append(user.long_name)
                if user.hw_model != HardwareModel.UNSET:
                    update_fields.append("hardware_model = %s")
                    update_values.append(get_hardware_model_name_from_code(user.hw_model))
                if user.role is not None:
                    update_fields.append("role = %s")
                    update_values.append(get_role_name_from_role(user.role))

                if update_fields:
                    update_query = f"""
                        UPDATE client_details
                        SET {", ".join(update_fields)}
                        WHERE node_id = %s
                    """
                    cur.execute(update_query, update_values + [client_details.node_id])
            else:
                # If record doesn't exist, insert a new one
                cur.execute("""
                    INSERT INTO client_details (node_id, short_name, long_name, hardware_model, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, (client_details.node_id, user.short_name, user.long_name,
                      get_hardware_model_name_from_code(user.hw_model), get_role_name_from_role(user.role)))

            conn.commit()

        self.execute_db_operation(db_operation)



@ProcessorRegistry.register_processor(PortNum.ROUTING_APP)
class RoutingAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ROUTING_APP packet")
        routing = Routing()
        routing.ParseFromString(payload)
        self.metrics.route_discovery_response_counter.labels(
            client_id=client_details.node_id,
            response_type=self.get_error_name_from_routing(routing.error_reason)
        ).inc()

    def get_error_name_from_routing(self, error_code):
        for name, value in Routing.Error.__dict__.items():
            if isinstance(value, int) and value == error_code:
                return name
        return 'UNKNOWN_ERROR'


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
    def __init__(self, registry: CollectorRegistry, db_connection: psycopg.connection):
        super().__init__(registry, db_connection)

    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TELEMETRY_APP packet")
        telemetry = Telemetry()
        telemetry.ParseFromString(payload)

        if telemetry.HasField('device_metrics'):
            device_metrics: DeviceMetrics = telemetry.device_metrics
            self.metrics.battery_level_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(device_metrics, 'battery_level', 0))

            self.metrics.voltage_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(device_metrics, 'voltage', 0))

            self.metrics.channel_utilization_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(device_metrics, 'channel_utilization', 0))

            self.metrics.air_util_tx_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(device_metrics, 'air_util_tx', 0))

            self.metrics.uptime_seconds_counter.labels(
                client_id=client_details.node_id,
            ).inc(getattr(device_metrics, 'uptime_seconds', 0))

        if telemetry.HasField('environment_metrics'):
            environment_metrics: EnvironmentMetrics = telemetry.environment_metrics
            self.metrics.temperature_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'temperature', 0))

            self.metrics.relative_humidity_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'relative_humidity', 0))

            self.metrics.barometric_pressure_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'barometric_pressure', 0))

            self.metrics.gas_resistance_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'gas_resistance', 0))

            self.metrics.iaq_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'iaq', 0))

            self.metrics.distance_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'distance', 0))

            self.metrics.lux_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'lux', 0))

            self.metrics.white_lux_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'white_lux', 0))

            self.metrics.ir_lux_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'ir_lux', 0))

            self.metrics.uv_lux_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'uv_lux', 0))

            self.metrics.wind_direction_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'wind_direction', 0))

            self.metrics.wind_speed_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'wind_speed', 0))

            self.metrics.weight_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(environment_metrics, 'weight', 0))

        if telemetry.HasField('air_quality_metrics'):
            air_quality_metrics: AirQualityMetrics = telemetry.air_quality_metrics
            self.metrics.pm10_standard_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm10_standard', 0))

            self.metrics.pm25_standard_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm25_standard', 0))

            self.metrics.pm100_standard_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm100_standard', 0))

            self.metrics.pm10_environmental_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm10_environmental', 0))

            self.metrics.pm25_environmental_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm25_environmental', 0))

            self.metrics.pm100_environmental_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'pm100_environmental', 0))

            self.metrics.particles_03um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_03um', 0))

            self.metrics.particles_05um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_05um', 0))

            self.metrics.particles_10um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_10um', 0))

            self.metrics.particles_25um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_25um', 0))

            self.metrics.particles_50um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_50um', 0))

            self.metrics.particles_100um_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(air_quality_metrics, 'particles_100um', 0))

        if telemetry.HasField('power_metrics'):
            power_metrics: PowerMetrics = telemetry.power_metrics
            self.metrics.ch1_voltage_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch1_voltage', 0))

            self.metrics.ch1_current_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch1_current', 0))

            self.metrics.ch2_voltage_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch2_voltage', 0))

            self.metrics.ch2_current_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch2_current', 0))

            self.metrics.ch3_voltage_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch3_voltage', 0))

            self.metrics.ch3_current_gauge.labels(
                client_id=client_details.node_id,
            ).set(getattr(power_metrics, 'ch3_current', 0))


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
        if traceroute.route:
            route = traceroute.route
            self.metrics.route_discovery_counter.labels(
                client_id=client_details.node_id
            ).inc(len(route))


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
        pass  # Nothing interesting here


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
