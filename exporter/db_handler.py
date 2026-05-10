from datetime import datetime
from typing import Any, Dict, Iterable

from psycopg_pool import ConnectionPool


BROADCAST_NODE_IDS = {"4294967295", "1"}


class DBHandler:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def get_connection(self):
        return self.db_pool.getconn()

    def release_connection(self, conn):
        self.db_pool.putconn(conn)

    def execute_db_operation(self, operation):
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                return operation(cur, conn)

    def store_device_metrics(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("device_metrics", node_id, metrics)

    def store_environment_metrics(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("environment_metrics", node_id, metrics)

    def store_air_quality_metrics(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("air_quality_metrics", node_id, metrics)

    def store_power_metrics(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("power_metrics", node_id, metrics)

    def store_pax_counter_metrics(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("pax_counter_metrics", node_id, metrics)

    def store_local_stats(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("local_stats", node_id, metrics)

    def store_node_position(self, node_id: str, metrics: Dict[str, Any]):
        self._insert_node_metrics("node_position_metrics", node_id, metrics)

    def store_mesh_packet_metrics(
        self, source_id: str, destination_id: str, metrics: Dict[str, Any]
    ):
        if not metrics:
            return

        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                self._ensure_node_exists(cur, source_id)
                self._ensure_node_exists(cur, destination_id)
                self._insert_row(
                    cur,
                    "mesh_packet_metrics",
                    {
                        "time": datetime.now(),
                        "source_id": source_id,
                        "destination_id": destination_id,
                        **metrics,
                    },
                )
                conn.commit()

    def get_latest_metrics(self, node_id: str) -> Dict[str, Any]:
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM node_telemetry WHERE node_id = %s",
                    (node_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {}
                columns = [c[0] for c in cur.description]
                return dict(zip(columns, row))

    # ---------- internals ----------

    def _insert_node_metrics(self, table: str, node_id: str, metrics: Dict[str, Any]):
        if not metrics:
            return
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                self._insert_row(
                    cur,
                    table,
                    {"time": datetime.now(), "node_id": node_id, **metrics},
                )
                conn.commit()

    @staticmethod
    def _insert_row(cur, table: str, row: Dict[str, Any]):
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        cur.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            _values(row),
        )

    @staticmethod
    def _ensure_node_exists(cur, node_id: str):
        cur.execute("SELECT 1 FROM node_details WHERE node_id = %s", (node_id,))
        if cur.fetchone():
            return
        if node_id in BROADCAST_NODE_IDS:
            cur.execute(
                """
                INSERT INTO node_details
                    (node_id, short_name, long_name, hardware_model, role)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (node_id) DO NOTHING
                """,
                (node_id, "Broadcast", "Broadcast", "BROADCAST", "BROADCAST"),
            )
        else:
            cur.execute(
                """
                INSERT INTO node_details (node_id, short_name, long_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (node_id) DO NOTHING
                """,
                (node_id, "Unknown", "Unknown"),
            )


def _values(row: Dict[str, Any]) -> Iterable[Any]:
    return tuple(row.values())
