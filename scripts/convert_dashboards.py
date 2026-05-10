#!/usr/bin/env python3
"""
One-shot rewrite of the legacy Prometheus dashboard JSON files into pure
TimescaleDB / PostgreSQL queries.

Run from the repo root:

    python3 scripts/convert_dashboards.py

The script walks every dashboard under
docker/grafana/provisioning/dashboards/, normalises every panel's
datasource to the provisioned PostgreSQL datasource, and replaces every
PromQL target with a SQL target keyed by (panel id, refId).

Idempotent: re-running on already-converted dashboards is a no-op.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DASHBOARD_DIR = (
    Path(__file__).resolve().parent.parent
    / "docker"
    / "grafana"
    / "provisioning"
    / "dashboards"
)

PG_DS = {"type": "grafana-postgresql-datasource", "uid": "PA942B37CCFAF5A81"}

# (dashboard_filename, panel_id, refId) -> SQL
SQL_OVERRIDES: dict[tuple[str, int, str], str] = {
    # ---------------------------------------------------------------- Main
    ("Main Dashboard.json", 22, "A"): """
SELECT COUNT(*) AS value
FROM mesh_packet_metrics
WHERE source_id IN ($Nodes)
  AND $__timeFilter(time)
""".strip(),
    ("Main Dashboard.json", 6, "A"): """
SELECT COALESCE(SUM(message_size_bytes), 0)::bigint AS value
FROM mesh_packet_metrics
WHERE source_id IN ($Nodes)
  AND time >= NOW() - INTERVAL '1 hour'
""".strip(),
    ("Main Dashboard.json", 23, "Average Chanel Utilization"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(channel_utilization) AS "Average Channel Utilization"
FROM device_metrics
WHERE node_id IN ($Nodes)
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Main Dashboard.json", 3, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    COALESCE(nd.long_name, dm.node_id) AS metric,
    AVG(dm.air_util_tx) AS value
FROM device_metrics dm
LEFT JOIN node_details nd ON nd.node_id = dm.node_id
WHERE dm.node_id IN ($Nodes)
  AND $__timeFilter(dm.time)
GROUP BY 1, 2
ORDER BY 1
""".strip(),
    ("Main Dashboard.json", 26, "A"): """
WITH top_nodes AS (
    SELECT node_id, AVG(channel_utilization) AS util
    FROM device_metrics
    WHERE node_id IN ($Nodes)
      AND $__timeFilter(time)
      AND channel_utilization > 0
    GROUP BY node_id
    ORDER BY util DESC
    LIMIT 3
)
SELECT
    time_bucket($__interval, dm.time) AS time,
    COALESCE(nd.long_name, nd.short_name, dm.node_id) AS metric,
    AVG(dm.channel_utilization) AS value
FROM device_metrics dm
JOIN top_nodes tn ON tn.node_id = dm.node_id
LEFT JOIN node_details nd ON nd.node_id = dm.node_id
WHERE $__timeFilter(dm.time)
GROUP BY 1, 2
ORDER BY 1
""".strip(),
    ("Main Dashboard.json", 5, "A"): """
SELECT
    portnum AS metric,
    COUNT(*) AS value
FROM mesh_packet_metrics
WHERE source_id IN ($Nodes)
  AND $__timeFilter(time)
GROUP BY portnum
ORDER BY value DESC
""".strip(),
    ("Main Dashboard.json", 9, "A"): """
SELECT
    COALESCE(nd.long_name, m.source_id) AS metric,
    MAX(m.hop_start) AS value
FROM mesh_packet_metrics m
LEFT JOIN node_details nd ON nd.node_id = m.source_id
WHERE m.source_id IN ($Nodes)
  AND $__timeFilter(m.time)
  AND m.hop_start > 0
GROUP BY 1
ORDER BY value DESC
""".strip(),
    # ---------------------------------------------------------------- Node
    ("Node Dashboard.json", 10, "A"): """
SELECT COUNT(*) AS value
FROM mesh_packet_metrics
WHERE source_id = '$nodeID'
  AND $__timeFilter(time)
""".strip(),
    ("Node Dashboard.json", 11, "A"): """
SELECT
    portnum AS metric,
    COUNT(*) AS value
FROM mesh_packet_metrics
WHERE source_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY portnum
ORDER BY value DESC
""".strip(),
    ("Node Dashboard.json", 12, "A"): """
SELECT EXTRACT(EPOCH FROM MAX(time))::bigint AS value
FROM mesh_packet_metrics
WHERE source_id = '$nodeID'
""".strip(),
    ("Node Dashboard.json", 14, "A"): """
SELECT COUNT(*) AS value
FROM mesh_packet_metrics
WHERE destination_id = '$nodeID'
  AND $__timeFilter(time)
""".strip(),
    ("Node Dashboard.json", 15, "A"): """
SELECT
    portnum AS metric,
    COUNT(*) AS value
FROM mesh_packet_metrics
WHERE destination_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY portnum
ORDER BY value DESC
""".strip(),
    ("Node Dashboard.json", 16, "A"): """
SELECT EXTRACT(EPOCH FROM MAX(time))::bigint AS value
FROM mesh_packet_metrics
WHERE destination_id = '$nodeID'
""".strip(),
    ("Node Dashboard.json", 5, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(temperature) AS temperature
FROM environment_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 6, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(relative_humidity) AS relative_humidity
FROM environment_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 7, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(barometric_pressure) AS barometric_pressure
FROM environment_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 2, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(battery_level) AS battery_level
FROM device_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 3, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(voltage) AS voltage
FROM device_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 18, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch1_current) AS "Channel 1"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 18, "B"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch2_current) AS "Channel 2"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 18, "C"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch3_current) AS "Channel 3"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 19, "A"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch1_voltage) AS "Channel 1"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 19, "B"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch2_voltage) AS "Channel 2"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("Node Dashboard.json", 19, "C"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ch3_voltage) AS "Channel 3"
FROM power_metrics
WHERE node_id = '$nodeID'
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    # ---------------------------------------------------------------- PAX
    ("PAX Dashboard.json", 5, "Bluetooth"): """
SELECT
    nd.longitude * 1e-7 AS longitude,
    nd.latitude  * 1e-7 AS latitude,
    nd.long_name AS metric,
    AVG(p.ble_beacons)  AS ble
FROM pax_counter_metrics p
JOIN node_details nd ON nd.node_id = p.node_id
WHERE p.node_id IN ($Nodes)
  AND nd.longitude IS NOT NULL AND nd.longitude <> 0
  AND $__timeFilter(p.time)
GROUP BY nd.node_id, nd.longitude, nd.latitude, nd.long_name
""".strip(),
    ("PAX Dashboard.json", 5, "Wifi"): """
SELECT
    nd.longitude * 1e-7 AS longitude,
    nd.latitude  * 1e-7 AS latitude,
    nd.long_name AS metric,
    AVG(p.wifi_stations) AS wifi
FROM pax_counter_metrics p
JOIN node_details nd ON nd.node_id = p.node_id
WHERE p.node_id IN ($Nodes)
  AND nd.longitude IS NOT NULL AND nd.longitude <> 0
  AND $__timeFilter(p.time)
GROUP BY nd.node_id, nd.longitude, nd.latitude, nd.long_name
""".strip(),
    ("PAX Dashboard.json", 3, "A"): """
SELECT COALESCE(MAX(uptime), 0) AS value
FROM pax_counter_metrics
WHERE node_id IN ($Nodes)
  AND $__timeFilter(time)
""".strip(),
    ("PAX Dashboard.json", 2, "Bluetooth"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(ble_beacons) AS "BLE beacons"
FROM pax_counter_metrics
WHERE node_id IN ($Nodes)
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    ("PAX Dashboard.json", 2, "Wifi"): """
SELECT
    time_bucket($__interval, time) AS time,
    AVG(wifi_stations) AS "WiFi stations"
FROM pax_counter_metrics
WHERE node_id IN ($Nodes)
  AND $__timeFilter(time)
GROUP BY 1
ORDER BY 1
""".strip(),
    # ----------------------------------------------------- Investigation
    ("Investigation Board.json", 3, "Packet Types"): """
SELECT
    source_id,
    portnum,
    COUNT(*) AS count
FROM mesh_packet_metrics
WHERE $__timeFilter(time)
GROUP BY source_id, portnum
ORDER BY count DESC
""".strip(),
}


def normalize_datasource(obj):
    """Recursively rewrite any prometheus / generic datasource pointers to
    our PostgreSQL datasource."""
    if isinstance(obj, dict):
        if "datasource" in obj and isinstance(obj["datasource"], dict):
            ds_type = obj["datasource"].get("type")
            if ds_type in {"prometheus", "datasource", "postgres"}:
                obj["datasource"] = dict(PG_DS)
        for v in obj.values():
            normalize_datasource(v)
    elif isinstance(obj, list):
        for v in obj:
            normalize_datasource(v)


def rewrite_targets(filename: str, panels: list) -> int:
    """Rewrite PromQL targets to SQL. Returns count of rewrites."""
    rewrites = 0
    for panel in panels:
        for tg in panel.get("targets", []) or []:
            key = (filename, panel.get("id"), tg.get("refId"))
            sql = SQL_OVERRIDES.get(key)
            if sql is None:
                # Drop residual prometheus-only fields if any.
                if "expr" in tg:
                    # Unmapped prom target — leave untouched but flag.
                    print(f"  WARN: unmapped prom target {key}", file=sys.stderr)
                continue
            tg.pop("expr", None)
            tg.pop("instant", None)
            tg.pop("range", None)
            tg.pop("interval", None)
            tg.pop("legendFormat", None)
            tg["datasource"] = dict(PG_DS)
            tg["rawQuery"] = True
            tg["rawSql"] = sql
            tg["format"] = "time_series" if "time_bucket" in sql else "table"
            tg["editorMode"] = "code"
            rewrites += 1
        if "panels" in panel:
            rewrites += rewrite_targets(filename, panel["panels"])
    return rewrites


def main():
    if not DASHBOARD_DIR.is_dir():
        sys.exit(f"dashboard dir not found: {DASHBOARD_DIR}")
    for path in sorted(DASHBOARD_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        normalize_datasource(d)
        n = rewrite_targets(path.name, d.get("panels", []))
        path.write_text(json.dumps(d, indent=2) + "\n")
        print(f"{path.name}: rewrote {n} targets")


if __name__ == "__main__":
    main()
