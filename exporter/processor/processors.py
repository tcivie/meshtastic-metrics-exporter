import os
from abc import ABC, abstractmethod
from datetime import datetime
from venv import logger

import psycopg
import unishox2

from exporter.db_handler import DBHandler
from exporter.metric.node_configuration_metrics import NodeConfigurationMetrics

try:
    from meshtastic.admin_pb2 import AdminMessage
    from meshtastic.mesh_pb2 import Position, User, HardwareModel, Routing, Waypoint, RouteDiscovery, NeighborInfo
    from meshtastic.mqtt_pb2 import MapReport
    from meshtastic.paxcount_pb2 import Paxcount
    from meshtastic.portnums_pb2 import PortNum
    from meshtastic.remote_hardware_pb2 import HardwareMessage
    from meshtastic.storeforward_pb2 import StoreAndForward
    from meshtastic.telemetry_pb2 import Telemetry, DeviceMetrics, EnvironmentMetrics, AirQualityMetrics, PowerMetrics
except ImportError:
    from meshtastic.protobuf.admin_pb2 import AdminMessage
    from meshtastic.protobuf.mesh_pb2 import Position, User, HardwareModel, Routing, Waypoint, RouteDiscovery, \
        NeighborInfo
    from meshtastic.protobuf.mqtt_pb2 import MapReport
    from meshtastic.protobuf.paxcount_pb2 import Paxcount
    from meshtastic.protobuf.portnums_pb2 import PortNum
    from meshtastic.protobuf.remote_hardware_pb2 import HardwareMessage
    from meshtastic.protobuf.storeforward_pb2 import StoreAndForward
    from meshtastic.protobuf.telemetry_pb2 import Telemetry, DeviceMetrics, EnvironmentMetrics, AirQualityMetrics, \
        PowerMetrics

from prometheus_client import CollectorRegistry
from psycopg_pool import ConnectionPool

from exporter.client_details import ClientDetails
from exporter.metric.node_metrics import Metrics


class Processor(ABC):
    def __init__(self, registry: CollectorRegistry, db_pool: ConnectionPool):
        self.db_pool = db_pool
        self.metrics = Metrics(registry, DBHandler(db_pool))

    @abstractmethod
    def process(self, payload: bytes, client_details: ClientDetails):
        pass


class ProcessorRegistry:
    _registry = {}

    @classmethod
    def register_processor(cls, port_num):
        def inner_wrapper(wrapped_class):
            if PortNum.DESCRIPTOR.values_by_number[port_num].name in os.getenv('EXPORTER_MESSAGE_TYPES_TO_FILTER',
                                                                               '').split(','):
                logger.info(f"Processor for port_num {port_num} is filtered out")
                return wrapped_class

            cls._registry[port_num] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_processor(cls, port_num) -> type(Processor):
        return cls._registry.get(port_num, UnknownAppProcessor)


########################################################################################################################
# PROCESSORS #
########################################################################################################################

@ProcessorRegistry.register_processor(PortNum.UNKNOWN_APP)
class UnknownAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        return None


@ProcessorRegistry.register_processor(PortNum.TEXT_MESSAGE_APP)
class TextMessageAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TEXT_MESSAGE_APP packet")
        pass


@ProcessorRegistry.register_processor(PortNum.REMOTE_HARDWARE_APP)
class RemoteHardwareAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received REMOTE_HARDWARE_APP packet")
        hardware_message = HardwareMessage()
        try:
            hardware_message.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse REMOTE_HARDWARE_APP packet: {e}")
            return


@ProcessorRegistry.register_processor(PortNum.POSITION_APP)
class PositionAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received POSITION_APP packet")
        position = Position()
        try:
            position.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse POSITION_APP packet: {e}")
            return

        self.metrics.update_metrics_position(
            position.latitude_i, position.longitude_i, position.altitude,
            position.precision_bits, client_details)
        pass


@ProcessorRegistry.register_processor(PortNum.NODEINFO_APP)
class NodeInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NODEINFO_APP packet")
        user = User()
        try:
            user.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse NODEINFO_APP packet: {e}")
            return

        def db_operation(cur, conn):
            # First, try to select the existing record
            cur.execute("""
                SELECT short_name, long_name, hardware_model, role
                FROM node_details
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
                    update_values.append(ClientDetails.get_hardware_model_name_from_code(user.hw_model))
                if user.role is not None:
                    update_fields.append("role = %s")
                    update_values.append(ClientDetails.get_role_name_from_role(user.role))

                if update_fields:
                    update_fields.append("updated_at = %s")
                    update_query = f"""
                        UPDATE node_details
                        SET {", ".join(update_fields)}
                        WHERE node_id = %s
                    """
                    cur.execute(update_query, update_values + [datetime.now().isoformat(), client_details.node_id])
            else:
                # If record doesn't exist, insert a new one
                cur.execute("""
                    INSERT INTO node_details (node_id, short_name, long_name, hardware_model, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, (client_details.node_id, user.short_name, user.long_name,
                      ClientDetails.get_hardware_model_name_from_code(user.hw_model),
                      ClientDetails.get_role_name_from_role(user.role)))

            conn.commit()

        self.metrics.get_db().execute_db_operation(db_operation)


@ProcessorRegistry.register_processor(PortNum.ROUTING_APP)
class RoutingAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ROUTING_APP packet")
        routing = Routing()
        try:
            routing.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse ROUTING_APP packet: {e}")
            return
        self.metrics.route_discovery_response_counter.labels(
            **client_details.to_dict(),
            response_type=self.get_error_name_from_routing(routing.error_reason)
        ).inc()

    @staticmethod
    def get_error_name_from_routing(error_code):
        for name, value in Routing.Error.__dict__.items():
            if isinstance(value, int) and value == error_code:
                return name
        return 'UNKNOWN_ERROR'


@ProcessorRegistry.register_processor(PortNum.ADMIN_APP)
class AdminAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ADMIN_APP packet")
        admin_message = AdminMessage()
        try:
            admin_message.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse ADMIN_APP packet: {e}")
            return


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
        try:
            waypoint.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse WAYPOINT_APP packet: {e}")
            return


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
        NodeConfigurationMetrics().process_pax_counter_update(client_details.node_id)
        paxcounter = Paxcount()
        try:
            paxcounter.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse PAXCOUNTER_APP packet: {e}")
            return
        self.metrics.pax_wifi_gauge.labels(
            **client_details.to_dict()
        ).set(paxcounter.wifi)
        self.metrics.pax_ble_gauge.labels(
            **client_details.to_dict()
        ).set(paxcounter.ble)
        self.metrics.pax_uptime_gauge.labels(
            **client_details.to_dict()
        ).set(paxcounter.uptime)



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
        try:
            store_and_forward.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse STORE_FORWARD_APP packet: {e}")
            return


@ProcessorRegistry.register_processor(PortNum.RANGE_TEST_APP)
class RangeTestAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received RANGE_TEST_APP packet")
        NodeConfigurationMetrics().process_range_test_update(client_details.node_id)
        pass  # NOTE: This portnum traffic is not sent to the public MQTT starting at firmware version 2.2.9


@ProcessorRegistry.register_processor(PortNum.TELEMETRY_APP)
class TelemetryAppProcessor(Processor):
    def __init__(self, registry: CollectorRegistry, db_connection: psycopg.connection):
        super().__init__(registry, db_connection)

    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received TELEMETRY_APP packet")
        telemetry = Telemetry()
        try:
            telemetry.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse TELEMETRY_APP packet: {e}")
            return

        if telemetry.HasField('device_metrics'):
            NodeConfigurationMetrics().process_device_update(client_details.node_id)
            device_metrics: DeviceMetrics = telemetry.device_metrics
            self.metrics.battery_level_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(device_metrics, 'battery_level', 0))

            self.metrics.voltage_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(device_metrics, 'voltage', 0))

            self.metrics.channel_utilization_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(device_metrics, 'channel_utilization', 0))

            self.metrics.air_util_tx_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(device_metrics, 'air_util_tx', 0))

            self.metrics.uptime_seconds_counter.labels(
                **client_details.to_dict()
            ).inc(getattr(device_metrics, 'uptime_seconds', 0))

        if telemetry.HasField('environment_metrics'):
            NodeConfigurationMetrics().process_environment_update(client_details.node_id)
            environment_metrics: EnvironmentMetrics = telemetry.environment_metrics
            self.metrics.temperature_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'temperature', 0))

            self.metrics.relative_humidity_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'relative_humidity', 0))

            self.metrics.barometric_pressure_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'barometric_pressure', 0))

            self.metrics.gas_resistance_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'gas_resistance', 0))

            self.metrics.iaq_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'iaq', 0))

            self.metrics.distance_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'distance', 0))

            self.metrics.lux_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'lux', 0))

            self.metrics.white_lux_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'white_lux', 0))

            self.metrics.ir_lux_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'ir_lux', 0))

            self.metrics.uv_lux_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'uv_lux', 0))

            self.metrics.wind_direction_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'wind_direction', 0))

            self.metrics.wind_speed_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'wind_speed', 0))

            self.metrics.weight_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(environment_metrics, 'weight', 0))

        if telemetry.HasField('air_quality_metrics'):
            NodeConfigurationMetrics().process_air_quality_update(client_details.node_id)
            air_quality_metrics: AirQualityMetrics = telemetry.air_quality_metrics
            self.metrics.pm10_standard_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm10_standard', 0))

            self.metrics.pm25_standard_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm25_standard', 0))

            self.metrics.pm100_standard_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm100_standard', 0))

            self.metrics.pm10_environmental_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm10_environmental', 0))

            self.metrics.pm25_environmental_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm25_environmental', 0))

            self.metrics.pm100_environmental_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'pm100_environmental', 0))

            self.metrics.particles_03um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_03um', 0))

            self.metrics.particles_05um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_05um', 0))

            self.metrics.particles_10um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_10um', 0))

            self.metrics.particles_25um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_25um', 0))

            self.metrics.particles_50um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_50um', 0))

            self.metrics.particles_100um_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(air_quality_metrics, 'particles_100um', 0))

        if telemetry.HasField('power_metrics'):
            NodeConfigurationMetrics().process_power_update(client_details.node_id)
            power_metrics: PowerMetrics = telemetry.power_metrics
            self.metrics.ch1_voltage_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(power_metrics, 'ch1_voltage', 0))

            self.metrics.ch1_current_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(power_metrics, 'ch1_current', 0))

            self.metrics.ch2_voltage_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(power_metrics, 'ch2_voltage', 0))

            self.metrics.ch2_current_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(power_metrics, 'ch2_current', 0))

            self.metrics.ch3_voltage_gauge.labels(
                **client_details.to_dict()
            ).set(getattr(power_metrics, 'ch3_voltage', 0))

            self.metrics.ch3_current_gauge.labels(
                **client_details.to_dict()
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
        try:
            traceroute.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse TRACEROUTE_APP packet: {e}")
            return
        if traceroute.route:
            route = traceroute.route
            self.metrics.route_discovery_gauge.labels(
                **client_details.to_dict()
            ).set(len(route))


@ProcessorRegistry.register_processor(PortNum.NEIGHBORINFO_APP)
class NeighborInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received NEIGHBORINFO_APP packet")
        NodeConfigurationMetrics().process_neighbor_info_update(client_details.node_id)
        neighbor_info = NeighborInfo()
        try:
            neighbor_info.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse NEIGHBORINFO_APP packet: {e}")
            return
        self.update_node_neighbors(neighbor_info, client_details)

    def update_node_neighbors(self, neighbor_info: NeighborInfo, client_details: ClientDetails):
        def operation(cur, conn):
            new_neighbor_ids = [str(neighbor.node_id) for neighbor in neighbor_info.neighbors]
            if new_neighbor_ids:
                placeholders = ','.join(['%s'] * len(new_neighbor_ids))
                cur.execute(f"""
                    DELETE FROM node_neighbors 
                    WHERE node_id = %s AND neighbor_id NOT IN ({placeholders})
                """, (client_details.node_id, *new_neighbor_ids))
            else:
                cur.execute("DELETE FROM node_neighbors WHERE node_id = %s", (client_details.node_id,))

            for neighbor in neighbor_info.neighbors:
                cur.execute("""
                    WITH upsert AS (
                        INSERT INTO node_neighbors (node_id, neighbor_id, snr)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (node_id, neighbor_id)
                        DO UPDATE SET snr = EXCLUDED.snr
                        RETURNING node_id, neighbor_id
                    )
                    INSERT INTO node_details (node_id)
                    SELECT node_id FROM upsert
                    WHERE NOT EXISTS (SELECT 1 FROM node_details WHERE node_id = upsert.node_id)
                    UNION
                    SELECT neighbor_id FROM upsert
                    WHERE NOT EXISTS (SELECT 1 FROM node_details WHERE node_id = upsert.neighbor_id)
                    ON CONFLICT (node_id) DO NOTHING;
                """, (str(client_details.node_id), str(neighbor.node_id), float(neighbor.snr)))

            conn.commit()

        self.metrics.get_db().execute_db_operation(operation)


@ProcessorRegistry.register_processor(PortNum.ATAK_PLUGIN)
class AtakPluginProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received ATAK_PLUGIN packet")
        pass  # NOTE: ATAK Plugin


@ProcessorRegistry.register_processor(PortNum.MAP_REPORT_APP)
class MapReportAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        logger.debug("Received MAP_REPORT_APP packet")
        NodeConfigurationMetrics().map_broadcast_update(client_details.node_id)
        map_report = MapReport()
        try:
            map_report.ParseFromString(payload)
        except Exception as e:
            logger.error(f"Failed to parse MAP_REPORT_APP packet: {e}")
            return


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
