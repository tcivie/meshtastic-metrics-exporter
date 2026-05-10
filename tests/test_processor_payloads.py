"""Tests that the protobuf-driven processors produce the right calls into
DBHandler.  Skipped when the meshtastic protobuf package is unavailable."""

from unittest.mock import MagicMock

import pytest

try:
    from meshtastic.paxcount_pb2 import Paxcount
    from meshtastic.telemetry_pb2 import (
        DeviceMetrics,
        EnvironmentMetrics,
        Telemetry,
    )
    from meshtastic.mesh_pb2 import NeighborInfo, Position
except ImportError:
    try:
        from meshtastic.protobuf.paxcount_pb2 import Paxcount
        from meshtastic.protobuf.telemetry_pb2 import (
            DeviceMetrics,
            EnvironmentMetrics,
            Telemetry,
        )
        from meshtastic.protobuf.mesh_pb2 import NeighborInfo, Position
    except ImportError:
        pytest.skip("meshtastic protobuf modules unavailable", allow_module_level=True)

from exporter.client_details import ClientDetails
from exporter.processor.processors import (
    NeighborInfoAppProcessor,
    PaxCounterAppProcessor,
    PositionAppProcessor,
    TelemetryAppProcessor,
)


def _client(node_id="42"):
    return ClientDetails(node_id=node_id, short_name="x", long_name="y")


def _processor(klass):
    inst = klass.__new__(klass)
    inst.db_pool = MagicMock(name="pool")
    inst.db_handler = MagicMock(name="db_handler")
    return inst


class TestPaxCounterAppProcessor:
    def test_pax_payload_stores_uptime(self):
        payload = Paxcount(wifi=5, ble=7, uptime=600).SerializeToString()
        proc = _processor(PaxCounterAppProcessor)

        proc.process(payload, client_details=_client())

        proc.db_handler.store_pax_counter_metrics.assert_called_once()
        node_id, metrics = proc.db_handler.store_pax_counter_metrics.call_args.args
        assert node_id == "42"
        assert metrics == {"wifi_stations": 5, "ble_beacons": 7, "uptime": 600}


class TestTelemetryAppProcessor:
    def test_device_metrics_dispatch(self):
        payload = Telemetry(
            device_metrics=DeviceMetrics(
                battery_level=80,
                voltage=4.2,
                channel_utilization=12.5,
                air_util_tx=0.5,
                uptime_seconds=3600,
            )
        ).SerializeToString()

        proc = _processor(TelemetryAppProcessor)
        proc.process(payload, client_details=_client())

        proc.db_handler.store_device_metrics.assert_called_once()
        proc.db_handler.store_environment_metrics.assert_not_called()
        node_id, metrics = proc.db_handler.store_device_metrics.call_args.args
        assert node_id == "42"
        assert metrics["battery_level"] == 80
        assert metrics["uptime_seconds"] == 3600

    def test_environment_metrics_dispatch(self):
        payload = Telemetry(
            environment_metrics=EnvironmentMetrics(
                temperature=21.5, relative_humidity=55.0
            )
        ).SerializeToString()

        proc = _processor(TelemetryAppProcessor)
        proc.process(payload, client_details=_client())

        proc.db_handler.store_environment_metrics.assert_called_once()
        proc.db_handler.store_device_metrics.assert_not_called()


class TestPositionAppProcessor:
    def test_position_updates_node_details(self):
        payload = Position(
            latitude_i=329123456,
            longitude_i=-1175678910,
            altitude=10,
            precision_bits=14,
        ).SerializeToString()

        proc = _processor(PositionAppProcessor)
        proc.process(payload, client_details=_client())

        proc.db_handler.execute_db_operation.assert_called_once()

    def test_zero_position_is_ignored(self):
        payload = Position(latitude_i=0, longitude_i=0).SerializeToString()
        proc = _processor(PositionAppProcessor)
        proc.process(payload, client_details=_client())
        proc.db_handler.execute_db_operation.assert_not_called()


class TestNeighborInfoAppProcessor:
    def test_neighbors_replace_old_entries(self):
        info = NeighborInfo()
        for nid, snr in [(1, 4.5), (2, -3.0)]:
            n = info.neighbors.add()
            n.node_id = nid
            n.snr = snr
        payload = info.SerializeToString()

        proc = _processor(NeighborInfoAppProcessor)
        proc.process(payload, client_details=_client())

        proc.db_handler.execute_db_operation.assert_called_once()
