import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Optional, Type

import unishox2

logger = logging.getLogger(__name__)

try:
    from meshtastic.admin_pb2 import AdminMessage
    from meshtastic.mesh_pb2 import (
        HardwareModel,
        NeighborInfo,
        Position,
        RouteDiscovery,
        Routing,
        User,
        Waypoint,
    )
    from meshtastic.mqtt_pb2 import MapReport
    from meshtastic.paxcount_pb2 import Paxcount
    from meshtastic.portnums_pb2 import PortNum
    from meshtastic.remote_hardware_pb2 import HardwareMessage
    from meshtastic.storeforward_pb2 import StoreAndForward
    from meshtastic.telemetry_pb2 import Telemetry
except ImportError:
    from meshtastic.protobuf.admin_pb2 import AdminMessage
    from meshtastic.protobuf.mesh_pb2 import (
        HardwareModel,
        NeighborInfo,
        Position,
        RouteDiscovery,
        Routing,
        User,
        Waypoint,
    )
    from meshtastic.protobuf.mqtt_pb2 import MapReport
    from meshtastic.protobuf.paxcount_pb2 import Paxcount
    from meshtastic.protobuf.portnums_pb2 import PortNum
    from meshtastic.protobuf.remote_hardware_pb2 import HardwareMessage
    from meshtastic.protobuf.storeforward_pb2 import StoreAndForward
    from meshtastic.protobuf.telemetry_pb2 import Telemetry

from psycopg_pool import ConnectionPool

from exporter.client_details import ClientDetails
from exporter.db_handler import DBHandler


DEVICE_METRIC_FIELDS = (
    "battery_level",
    "voltage",
    "channel_utilization",
    "air_util_tx",
    "uptime_seconds",
)
ENVIRONMENT_METRIC_FIELDS = (
    "temperature",
    "relative_humidity",
    "barometric_pressure",
    "gas_resistance",
    "iaq",
    "distance",
    "lux",
    "white_lux",
    "ir_lux",
    "uv_lux",
    "wind_direction",
    "wind_speed",
    "weight",
)
AIR_QUALITY_METRIC_FIELDS = (
    "pm10_standard",
    "pm25_standard",
    "pm100_standard",
    "pm10_environmental",
    "pm25_environmental",
    "pm100_environmental",
    "particles_03um",
    "particles_05um",
    "particles_10um",
    "particles_25um",
    "particles_50um",
    "particles_100um",
)
POWER_METRIC_FIELDS = (
    "ch1_voltage",
    "ch1_current",
    "ch2_voltage",
    "ch2_current",
    "ch3_voltage",
    "ch3_current",
)
LOCAL_STATS_FIELDS = (
    "num_packets_tx",
    "num_packets_rx",
    "num_packets_rx_bad",
    "num_online_nodes",
    "num_total_nodes",
    "num_rx_dupe",
    "num_tx_relay",
    "num_tx_relay_canceled",
)
# Overlap fields shared between LocalStats and DeviceMetrics.  When a
# packet carries the local_stats variant we copy these into
# device_metrics so charts have a single source of truth.
LOCAL_STATS_TO_DEVICE_FIELDS = (
    "uptime_seconds",
    "channel_utilization",
    "air_util_tx",
)


def _to_dict(message, fields: Iterable[str]) -> dict:
    return {f: getattr(message, f, 0) for f in fields}


def _enum_name(message_cls, field_name: str, value: int) -> str | None:
    field = message_cls.DESCRIPTOR.fields_by_name.get(field_name)
    if field is None or field.enum_type is None:
        return None
    val = field.enum_type.values_by_number.get(int(value))
    return val.name if val is not None else None


def _safe_parse(payload: bytes, message_cls, label: str):
    msg = message_cls()
    try:
        msg.ParseFromString(payload)
        return msg
    except Exception as e:
        logger.debug(f"Failed to parse {label} packet: {e}")
        return None


class Processor(ABC):
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool
        self.db_handler = DBHandler(db_pool)

    @abstractmethod
    def process(self, payload: bytes, client_details: ClientDetails): ...


class ProcessorRegistry:
    _registry: dict[int, Type[Processor]] = {}

    @classmethod
    def register_processor(cls, port_num):
        def inner(wrapped_class):
            filtered = os.getenv("EXPORTER_MESSAGE_TYPES_TO_FILTER", "").split(",")
            name = PortNum.DESCRIPTOR.values_by_number[port_num].name
            if name in filtered:
                logger.info(f"Processor for port_num {port_num} is filtered out")
                return wrapped_class
            cls._registry[port_num] = wrapped_class
            return wrapped_class

        return inner

    @classmethod
    def get_processor(cls, port_num) -> Type[Processor]:
        return cls._registry.get(port_num, UnknownAppProcessor)


def _noop(
    port_num: int, message_cls: Optional[type] = None, name: Optional[str] = None
):
    """Register a parse-and-drop processor for ports we don't yet store
    anything for.  ``message_cls=None`` means the payload is opaque and
    we don't even attempt to parse."""

    def _build(cls):
        ProcessorRegistry.register_processor(port_num)(cls)
        return cls

    label = name or PortNum.DESCRIPTOR.values_by_number[port_num].name

    class _NoopProcessor(Processor):
        _label = label
        _message_cls = message_cls

        def process(self, payload: bytes, client_details: ClientDetails):
            if self._message_cls is not None:
                _safe_parse(payload, self._message_cls, self._label)

    _NoopProcessor.__name__ = f"{label.title().replace('_', '')}Processor"
    _build(_NoopProcessor)
    return _NoopProcessor


# ---------------------------------------------------------------------------
# Stored-data processors
# ---------------------------------------------------------------------------


@ProcessorRegistry.register_processor(PortNum.UNKNOWN_APP)
class UnknownAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        return None


@ProcessorRegistry.register_processor(PortNum.POSITION_APP)
class PositionAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        position = _safe_parse(payload, Position, "POSITION_APP")
        if position is None:
            return
        if position.latitude_i == 0 and position.longitude_i == 0:
            return

        def db_op(cur, conn):
            cur.execute(
                """
                UPDATE node_details
                SET latitude   = %s,
                    longitude  = %s,
                    altitude   = %s,
                    precision  = %s,
                    updated_at = %s
                WHERE node_id = %s
                """,
                (
                    position.latitude_i,
                    position.longitude_i,
                    position.altitude,
                    position.precision_bits,
                    datetime.now(),
                    client_details.node_id,
                ),
            )
            conn.commit()

        self.db_handler.execute_db_operation(db_op)

        self.db_handler.store_node_position(
            client_details.node_id,
            {
                "latitude": position.latitude_i,
                "longitude": position.longitude_i,
                "altitude": getattr(position, "altitude", 0),
                "sats_in_view": getattr(position, "sats_in_view", 0),
                "ground_speed": getattr(position, "ground_speed", 0),
                "ground_track": getattr(position, "ground_track", 0),
                "pdop": getattr(position, "PDOP", 0),
                "hdop": getattr(position, "HDOP", 0),
                "vdop": getattr(position, "VDOP", 0),
                "precision_bits": getattr(position, "precision_bits", 0),
            },
        )


@ProcessorRegistry.register_processor(PortNum.NODEINFO_APP)
class NodeInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        user = _safe_parse(payload, User, "NODEINFO_APP")
        if user is None:
            return
        self.db_handler.execute_db_operation(
            lambda cur, conn: self._upsert_user(cur, conn, user, client_details)
        )

    @staticmethod
    def _upsert_user(cur, conn, user: User, client_details: ClientDetails):
        cur.execute(
            "SELECT 1 FROM node_details WHERE node_id = %s",
            (client_details.node_id,),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO node_details
                    (node_id, short_name, long_name, hardware_model, role)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    client_details.node_id,
                    user.short_name,
                    user.long_name,
                    ClientDetails.get_hardware_model_name_from_code(user.hw_model),
                    ClientDetails.get_role_name_from_role(user.role),
                ),
            )
            conn.commit()
            return

        updates: list[tuple[str, object]] = []
        if user.short_name:
            updates.append(("short_name", user.short_name))
        if user.long_name:
            updates.append(("long_name", user.long_name))
        if user.hw_model != HardwareModel.UNSET:
            updates.append(
                (
                    "hardware_model",
                    ClientDetails.get_hardware_model_name_from_code(user.hw_model),
                )
            )
        if user.role is not None:
            updates.append(("role", ClientDetails.get_role_name_from_role(user.role)))

        if not updates:
            return

        set_clause = ", ".join(f"{col} = %s" for col, _ in updates)
        values = [v for _, v in updates] + [datetime.now(), client_details.node_id]
        cur.execute(
            f"UPDATE node_details SET {set_clause}, updated_at = %s WHERE node_id = %s",
            values,
        )
        conn.commit()


@ProcessorRegistry.register_processor(PortNum.PAXCOUNTER_APP)
class PaxCounterAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        paxcounter = _safe_parse(payload, Paxcount, "PAXCOUNTER_APP")
        if paxcounter is None:
            return
        self.db_handler.store_pax_counter_metrics(
            client_details.node_id,
            {
                "wifi_stations": getattr(paxcounter, "wifi", 0),
                "ble_beacons": getattr(paxcounter, "ble", 0),
                "uptime": getattr(paxcounter, "uptime", 0),
            },
        )


@ProcessorRegistry.register_processor(PortNum.TELEMETRY_APP)
class TelemetryAppProcessor(Processor):
    _DISPATCH = (
        ("device_metrics", DEVICE_METRIC_FIELDS, "store_device_metrics"),
        ("environment_metrics", ENVIRONMENT_METRIC_FIELDS, "store_environment_metrics"),
        ("air_quality_metrics", AIR_QUALITY_METRIC_FIELDS, "store_air_quality_metrics"),
        ("power_metrics", POWER_METRIC_FIELDS, "store_power_metrics"),
        ("local_stats", LOCAL_STATS_FIELDS, "store_local_stats"),
    )

    def process(self, payload: bytes, client_details: ClientDetails):
        telemetry = _safe_parse(payload, Telemetry, "TELEMETRY_APP")
        if telemetry is None:
            return
        for field, columns, store_fn in self._DISPATCH:
            if telemetry.HasField(field):
                getattr(self.db_handler, store_fn)(
                    client_details.node_id,
                    _to_dict(getattr(telemetry, field), columns),
                )
        # local_stats and device_metrics share three columns (uptime,
        # ChUtil, AirUtilTX). When a packet carries local_stats, mirror
        # those columns into device_metrics so charts only ever read one
        # table for those values.
        if telemetry.HasField("local_stats"):
            self.db_handler.store_device_metrics(
                client_details.node_id,
                _to_dict(telemetry.local_stats, LOCAL_STATS_TO_DEVICE_FIELDS),
            )


@ProcessorRegistry.register_processor(PortNum.NEIGHBORINFO_APP)
class NeighborInfoAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        neighbor_info = _safe_parse(payload, NeighborInfo, "NEIGHBORINFO_APP")
        if neighbor_info is None:
            return
        self.db_handler.execute_db_operation(
            lambda cur, conn: self._update(cur, conn, neighbor_info, client_details)
        )

    @staticmethod
    def _update(cur, conn, neighbor_info: NeighborInfo, client_details: ClientDetails):
        new_ids = [str(n.node_id) for n in neighbor_info.neighbors]
        if new_ids:
            placeholders = ",".join(["%s"] * len(new_ids))
            cur.execute(
                f"DELETE FROM node_neighbors WHERE node_id = %s AND neighbor_id NOT IN ({placeholders})",
                (client_details.node_id, *new_ids),
            )
        else:
            cur.execute(
                "DELETE FROM node_neighbors WHERE node_id = %s",
                (client_details.node_id,),
            )

        for neighbor in neighbor_info.neighbors:
            cur.execute(
                """
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
                ON CONFLICT (node_id) DO NOTHING
                """,
                (
                    str(client_details.node_id),
                    str(neighbor.node_id),
                    float(neighbor.snr),
                ),
            )
        conn.commit()


@ProcessorRegistry.register_processor(PortNum.MAP_REPORT_APP)
class MapReportAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        map_report = _safe_parse(payload, MapReport, "MAP_REPORT_APP")
        if map_report is None:
            return

        region = _enum_name(MapReport, "region", getattr(map_report, "region", 0))
        modem_preset = _enum_name(
            MapReport, "modem_preset", getattr(map_report, "modem_preset", 0)
        )

        row = (
            client_details.node_id,
            getattr(map_report, "short_name", "") or "Unknown",
            getattr(map_report, "long_name", "") or "Unknown",
            ClientDetails.get_hardware_model_name_from_code(
                getattr(map_report, "hw_model", HardwareModel.UNSET)
            ),
            ClientDetails.get_role_name_from_role(getattr(map_report, "role", 0)),
            getattr(map_report, "latitude_i", 0),
            getattr(map_report, "longitude_i", 0),
            getattr(map_report, "altitude", 0),
            getattr(map_report, "position_precision", 0),
            getattr(map_report, "firmware_version", "") or None,
            region,
            modem_preset,
            bool(getattr(map_report, "has_default_channel", False)),
            int(getattr(map_report, "num_online_local_nodes", 0) or 0),
            datetime.now(),
        )

        def db_op(cur, conn):
            cur.execute(
                """
                INSERT INTO node_details (
                    node_id, short_name, long_name, hardware_model, role,
                    latitude, longitude, altitude, precision,
                    firmware_version, region, modem_preset,
                    has_default_channel, num_online_local, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (node_id) DO UPDATE SET
                    short_name          = EXCLUDED.short_name,
                    long_name           = EXCLUDED.long_name,
                    hardware_model      = EXCLUDED.hardware_model,
                    role                = EXCLUDED.role,
                    latitude            = EXCLUDED.latitude,
                    longitude           = EXCLUDED.longitude,
                    altitude            = EXCLUDED.altitude,
                    precision           = EXCLUDED.precision,
                    firmware_version    = EXCLUDED.firmware_version,
                    region              = EXCLUDED.region,
                    modem_preset        = EXCLUDED.modem_preset,
                    has_default_channel = EXCLUDED.has_default_channel,
                    num_online_local    = EXCLUDED.num_online_local,
                    updated_at          = EXCLUDED.updated_at
                """,
                row,
            )
            conn.commit()

        self.db_handler.execute_db_operation(db_op)


@ProcessorRegistry.register_processor(PortNum.ROUTING_APP)
class RoutingAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        _safe_parse(payload, Routing, "ROUTING_APP")

    @staticmethod
    def get_error_name_from_routing(error_code: int) -> str:
        for name, value in Routing.Error.__dict__.items():
            if isinstance(value, int) and value == error_code:
                return name
        return "UNKNOWN_ERROR"


@ProcessorRegistry.register_processor(PortNum.TEXT_MESSAGE_COMPRESSED_APP)
class TextMessageCompressedAppProcessor(Processor):
    def process(self, payload: bytes, client_details: ClientDetails):
        try:
            unishox2.decompress(payload, len(payload))
        except Exception as e:
            logger.debug(f"Failed to decompress TEXT_MESSAGE_COMPRESSED_APP: {e}")


# ---------------------------------------------------------------------------
# Parse-and-drop ports.  These exist for completeness; firmware sends them
# but we don't yet have a use for the payloads.  ``message_cls`` is None
# when the payload is opaque (audio, ATAK, etc.) so we skip parsing.
# ---------------------------------------------------------------------------

_noop(PortNum.TEXT_MESSAGE_APP)
_noop(PortNum.REMOTE_HARDWARE_APP, HardwareMessage)
_noop(PortNum.ADMIN_APP, AdminMessage)
_noop(PortNum.WAYPOINT_APP, Waypoint)
_noop(PortNum.AUDIO_APP)
_noop(PortNum.DETECTION_SENSOR_APP)
_noop(PortNum.REPLY_APP)
_noop(PortNum.IP_TUNNEL_APP)
_noop(PortNum.SERIAL_APP)
_noop(PortNum.STORE_FORWARD_APP, StoreAndForward)
_noop(PortNum.RANGE_TEST_APP)
_noop(PortNum.ZPS_APP)
_noop(PortNum.SIMULATOR_APP)
_noop(PortNum.TRACEROUTE_APP, RouteDiscovery)
_noop(PortNum.ATAK_PLUGIN)
_noop(PortNum.PRIVATE_APP)
_noop(PortNum.ATAK_FORWARDER)
_noop(PortNum.MAX)
