"""Unit tests for `exporter.db_handler.DBHandler`.

We mock out the connection pool with ``unittest.mock`` so the tests do not
require a running TimescaleDB. The intent is to pin down the SQL produced
by each `store_*` helper.
"""

from unittest.mock import MagicMock

from exporter.db_handler import DBHandler


def _make_pool():
    """Returns (pool_mock, conn_mock, cursor_mock).

    All three implement the relevant context-manager surface so the
    ``with self.db_pool.connection() as conn: with conn.cursor() as cur:``
    pattern in DBHandler "just works".
    """
    cur = MagicMock(name="cursor")
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone = MagicMock(return_value=None)
    cur.description = [("col1",)]

    conn = MagicMock(name="conn")
    conn.cursor.return_value = cur
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    pool = MagicMock(name="pool")
    pool.connection.return_value = conn
    return pool, conn, cur


def _last_sql(cursor):
    args, _ = cursor.execute.call_args_list[-1]
    return args[0]


def _last_values(cursor):
    args, _ = cursor.execute.call_args_list[-1]
    return args[1]


class TestDBHandlerWriteHelpers:
    def test_store_device_metrics_inserts_dynamic_columns(self):
        pool, _, cur = _make_pool()
        h = DBHandler(pool)

        h.store_device_metrics(
            "12345",
            {"battery_level": 80.0, "voltage": 4.2, "uptime_seconds": 3600},
        )

        sql = _last_sql(cur)
        values = _last_values(cur)

        assert "INSERT INTO device_metrics" in sql
        for col in ("time", "node_id", "battery_level", "voltage", "uptime_seconds"):
            assert col in sql
        # The placeholder count must equal the values count.
        assert sql.count("%s") == len(values)
        assert "12345" in values
        assert 80.0 in values

    def test_store_environment_metrics_skips_when_empty(self):
        pool, _, cur = _make_pool()
        h = DBHandler(pool)

        h.store_environment_metrics("99", {})

        # No SQL should have run because there were no metrics.
        cur.execute.assert_not_called()

    def test_store_pax_counter_includes_uptime(self):
        pool, _, cur = _make_pool()
        h = DBHandler(pool)

        h.store_pax_counter_metrics(
            "11", {"wifi_stations": 5, "ble_beacons": 7, "uptime": 600}
        )

        sql = _last_sql(cur)
        values = _last_values(cur)
        assert "uptime" in sql
        assert 600 in values

    def test_store_mesh_packet_metrics_inserts_unknown_node(self):
        """If source_id is not yet in node_details we expect an upsert
        before the metric INSERT."""
        pool, _, cur = _make_pool()
        # Make the existence checks return ``None`` so the helper inserts
        # both source and destination.
        cur.fetchone.side_effect = [None, None]
        h = DBHandler(pool)

        h.store_mesh_packet_metrics(
            "11",
            "22",
            {"portnum": "TELEMETRY_APP", "packet_id": 123, "channel": 0},
        )

        executed = [c.args[0] for c in cur.execute.call_args_list]
        # 2 SELECT existence checks, 2 INSERT-into-node_details, 1 INSERT-metrics.
        assert any("SELECT 1 FROM node_details" in s for s in executed)
        assert any("INSERT INTO node_details" in s for s in executed)
        assert any("INSERT INTO mesh_packet_metrics" in s for s in executed)

    def test_store_mesh_packet_broadcast_destination_uses_broadcast_label(self):
        pool, _, cur = _make_pool()
        cur.fetchone.side_effect = [None, None]
        h = DBHandler(pool)
        h.store_mesh_packet_metrics(
            "11",
            "4294967295",
            {"portnum": "POSITION_APP"},
        )
        broadcast_inserts = [
            c
            for c in cur.execute.call_args_list
            if "INSERT INTO node_details" in c.args[0]
            and "Broadcast" in (c.args[1] or ())
        ]
        assert broadcast_inserts, "broadcast destination should be tagged Broadcast"
