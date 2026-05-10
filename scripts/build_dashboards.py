#!/usr/bin/env python3
"""Generate the five Meshtastic Grafana dashboards from one source of
truth. Replaces the hand-edited JSON under
docker/grafana/provisioning/dashboards/.

Run from the repo root:

    python3 scripts/build_dashboards.py

The output is deterministic; commit the JSON it produces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DS = {"type": "grafana-postgresql-datasource", "uid": "PA942B37CCFAF5A81"}

DASH_UIDS = {
    "overview": "mesh-overview",
    "node": "mesh-node-detail",
    "map": "mesh-network-map",
    "pax": "mesh-pax",
    "investigation": "mesh-investigation",
}

OUT = (
    Path(__file__).resolve().parent.parent
    / "docker"
    / "grafana"
    / "provisioning"
    / "dashboards"
)


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------


def grid(x: int, y: int, w: int, h: int) -> dict[str, int]:
    return {"x": x, "y": y, "w": w, "h": h}


def target(sql: str, refId: str = "A", fmt: str = "table") -> dict[str, Any]:
    return {
        "datasource": dict(DS),
        "editorMode": "code",
        "format": fmt,
        "rawQuery": True,
        "rawSql": sql,
        "refId": refId,
    }


def _drill_override(field: str, dashboard_uid: str, var_name: str) -> dict:
    url = (
        f"/d/{dashboard_uid}?var-{var_name}="
        f"${{__data.fields.{field}}}&${{__url_time_range}}"
    )
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {"id": "links", "value": [{"title": "Open node detail", "url": url}]}
        ],
    }


def _color_threshold_override(field: str, mode: str, steps: list) -> dict:
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {
                "id": "custom.cellOptions",
                "value": {"type": "color-background", "mode": "basic"},
            },
            {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}},
            {"id": "color", "value": {"mode": mode}},
        ],
    }


def stat_panel(
    panel_id: int, title: str, sql: str, grid_pos: dict, opts: dict | None = None
) -> dict[str, Any]:
    opts = opts or {}
    thresholds = opts.get("thresholds") or [{"color": "green", "value": None}]
    panel: dict[str, Any] = {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "description": opts.get("description", ""),
        "datasource": dict(DS),
        "gridPos": grid_pos,
        "targets": [target(sql)],
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": thresholds},
                "unit": opts.get("unit", "short"),
                "noValue": opts.get("no_value", "0"),
            },
            "overrides": [],
        },
        "options": {
            "colorMode": opts.get("color_mode", "background"),
            "graphMode": "area",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": opts.get("text_mode", "auto"),
            "wideLayout": True,
        },
    }
    if opts.get("drill_url"):
        panel["links"] = [
            {
                "title": opts.get("drill_title", "Drill in"),
                "url": opts["drill_url"],
                "targetBlank": False,
            }
        ]
    return panel


def timeseries_panel(
    panel_id: int, title: str, sql: str, grid_pos: dict, opts: dict | None = None
) -> dict[str, Any]:
    """`opts.legend` controls layout:
    - "hidden"     → no legend (default for single-series).
    - "bottom"     → list legend below chart (default for multi-series).
    - "table-right"→ table legend with stat columns on the right.
    """
    opts = opts or {}
    layout = opts.get("legend", "bottom")
    if layout == "hidden":
        legend = {"displayMode": "list", "placement": "bottom", "showLegend": False}
    elif layout == "table-right":
        legend = {
            "displayMode": "table",
            "placement": "right",
            "showLegend": True,
            "calcs": opts.get("legend_calcs") or ["lastNotNull", "mean", "max"],
        }
    else:
        legend = {
            "displayMode": "list",
            "placement": "bottom",
            "showLegend": True,
            "calcs": [],
        }
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "description": opts.get("description", ""),
        "datasource": dict(DS),
        "gridPos": grid_pos,
        "targets": [target(sql, fmt="time_series")],
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line",
                    "fillOpacity": 10,
                    "lineInterpolation": "smooth",
                    "lineWidth": 2,
                    "pointSize": 4,
                    "showPoints": "never",
                    "spanNulls": True,
                    "axisGridShow": True,
                    "axisLabel": "",
                },
                "unit": opts.get("unit", "short"),
            },
            "overrides": [],
        },
        "options": {
            "legend": legend,
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def piechart_panel(
    panel_id: int, title: str, sql: str, grid_pos: dict, opts: dict | None = None
) -> dict[str, Any]:
    opts = opts or {}
    return {
        "id": panel_id,
        "type": "piechart",
        "title": title,
        "description": opts.get("description", ""),
        "datasource": dict(DS),
        "gridPos": grid_pos,
        "targets": [target(sql, fmt="time_series")],
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "mappings": [],
                "unit": "short",
            },
            "overrides": [],
        },
        "options": {
            "displayLabels": ["percent"],
            "legend": {
                "displayMode": "table",
                "placement": "right",
                "showLegend": True,
                "values": ["value", "percent"],
            },
            "pieType": "donut",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "tooltip": {"mode": "single", "sort": "none"},
        },
    }


def table_panel(
    panel_id: int, title: str, sql: str, grid_pos: dict, opts: dict | None = None
) -> dict[str, Any]:
    opts = opts or {}
    panel: dict[str, Any] = {
        "id": panel_id,
        "type": "table",
        "title": title,
        "description": opts.get("description", ""),
        "datasource": dict(DS),
        "gridPos": grid_pos,
        "targets": [target(sql)],
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "custom": {
                    "align": "auto",
                    "cellOptions": {"type": "auto"},
                    "filterable": True,
                    "inspect": False,
                },
                "mappings": [],
            },
            "overrides": [],
        },
        "options": {
            "footer": {
                "countRows": False,
                "fields": "",
                "reducer": ["sum"],
                "show": False,
            },
            "showHeader": True,
        },
    }
    drill_uid = opts.get("drill_dashboard_uid")
    drill_var = opts.get("drill_var_name", "nodeID")
    drill_fields = opts.get("drill_fields") or []
    if opts.get("drill_field"):
        drill_fields = [opts["drill_field"], *drill_fields]
    if drill_uid:
        for field in drill_fields:
            panel["fieldConfig"]["overrides"].append(
                _drill_override(field, drill_uid, drill_var)
            )
    for field, steps in (opts.get("color_thresholds") or {}).items():
        panel["fieldConfig"]["overrides"].append(
            _color_threshold_override(field, "thresholds", steps)
        )
    return panel


def row(panel_id: int, title: str, y: int, collapsed: bool = False) -> dict[str, Any]:
    return {
        "id": panel_id,
        "type": "row",
        "title": title,
        "gridPos": grid(0, y, 24, 1),
        "collapsed": collapsed,
        "panels": [],
    }


def dashboard(
    uid: str, title: str, panels: list, opts: dict | None = None
) -> dict[str, Any]:
    opts = opts or {}
    return {
        "annotations": {"list": []},
        "description": opts.get("description", ""),
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [
            {
                "asDropdown": True,
                "icon": "external link",
                "includeVars": False,
                "keepTime": True,
                "tags": ["meshtastic"],
                "targetBlank": False,
                "title": "Mesh dashboards",
                "tooltip": "Switch dashboard",
                "type": "dashboards",
            }
        ],
        "panels": panels,
        "refresh": opts.get("refresh", "30s"),
        "schemaVersion": 39,
        "tags": opts.get("tags", ["meshtastic"]),
        "templating": {"list": opts.get("templating_vars") or []},
        "time": {"from": opts.get("time_from", "now-6h"), "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 1,
        "weekStart": "",
    }


def query_var(
    name: str, label: str, sql: str, opts: dict | None = None
) -> dict[str, Any]:
    opts = opts or {}
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": dict(DS),
        "definition": sql,
        "query": sql,
        "refresh": 1,
        "regex": "",
        "sort": 1,
        "multi": opts.get("multi", False),
        "includeAll": opts.get("include_all", False),
        "allValue": None,
        "current": {
            "text": opts.get("current_text", ""),
            "value": opts.get("current_value", ""),
        },
        "options": [],
        "skipUrlSync": False,
        "hide": 0,
    }


# ---------------------------------------------------------------------------
# 1. NETWORK OVERVIEW — lobby of health tiles
# ---------------------------------------------------------------------------

T_HEALTH_RED_GREEN = [
    {"color": "red", "value": None},
    {"color": "orange", "value": 1},
    {"color": "yellow", "value": 20},
    {"color": "green", "value": 100},
]
T_RATE = [
    {"color": "red", "value": None},
    {"color": "yellow", "value": 1},
    {"color": "green", "value": 10},
]
T_CHUTIL = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 15},
    {"color": "red", "value": 25},
]
T_SNR = [
    {"color": "red", "value": None},
    {"color": "yellow", "value": -13},
    {"color": "green", "value": -7},
]
T_NAMING = [
    {"color": "red", "value": None},
    {"color": "yellow", "value": 30},
    {"color": "green", "value": 70},
]


def _overview_health_tiles() -> list:
    drill_traffic = f"/d/{DASH_UIDS['investigation']}?${{__url_time_range}}"
    drill_map = f"/d/{DASH_UIDS['map']}?${{__url_time_range}}"
    return [
        stat_panel(
            2,
            "Active nodes (30m)",
            "SELECT COUNT(DISTINCT source_id) AS value "
            "FROM mesh_packet_metrics WHERE time > NOW() - INTERVAL '30 minutes'",
            grid(0, 1, 4, 4),
            {
                "description": "Distinct nodes that sent any packet in the last 30 minutes.",
                "thresholds": T_HEALTH_RED_GREEN,
                "drill_url": drill_traffic,
                "drill_title": "Investigate traffic",
            },
        ),
        stat_panel(
            3,
            "Total nodes seen",
            "SELECT COUNT(*) AS value FROM node_details "
            "WHERE node_id NOT IN ('4294967295','1','0')",
            grid(4, 1, 4, 4),
            {
                "description": "All nodes ever observed (excluding broadcast).",
                "thresholds": [{"color": "blue", "value": None}],
                "color_mode": "value",
                "drill_url": drill_map,
                "drill_title": "Open network map",
            },
        ),
        stat_panel(
            4,
            "Packets / min (5m avg)",
            "SELECT (COUNT(*)::float / 5.0) AS value "
            "FROM mesh_packet_metrics WHERE time > NOW() - INTERVAL '5 minutes'",
            grid(8, 1, 4, 4),
            {
                "description": "Packets/min over the last 5 minutes (RED-method 'Rate').",
                "thresholds": T_RATE,
                "drill_url": drill_traffic,
                "drill_title": "Investigate traffic",
            },
        ),
        stat_panel(
            5,
            "Median ChUtil (1h)",
            "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY channel_utilization)::float AS value "
            "FROM device_metrics "
            "WHERE time > NOW() - INTERVAL '1 hour' AND channel_utilization > 0",
            grid(12, 1, 4, 4),
            {
                "description": "Median channel utilization over the last hour. >25% = congested.",
                "unit": "percent",
                "thresholds": T_CHUTIL,
            },
        ),
        stat_panel(
            6,
            "Median SNR (1h)",
            "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rx_snr)::float AS value "
            "FROM mesh_packet_metrics "
            "WHERE time > NOW() - INTERVAL '1 hour' "
            "  AND rx_snr IS NOT NULL AND rx_snr <> 0 "
            "  AND destination_id NOT IN ('4294967295','1','0')",
            grid(16, 1, 4, 4),
            {
                "description": (
                    "Median unicast SNR over the last hour. Excludes rx_snr=0 (firmware default / not measured). "
                    "<-7 dB marginal, <-13 dB poor."
                ),
                "unit": "none",
                "thresholds": T_SNR,
            },
        ),
        stat_panel(
            7,
            "Named nodes",
            "SELECT (100.0 * COUNT(*) FILTER (WHERE long_name IS NOT NULL "
            "  AND long_name <> 'Unknown')) / NULLIF(COUNT(*), 0) AS value "
            "FROM node_details WHERE node_id NOT IN ('4294967295','1','0')",
            grid(20, 1, 4, 4),
            {
                "description": "Percent of nodes with a known long_name. Low = missing NodeInfo packets.",
                "unit": "percent",
                "thresholds": T_NAMING,
            },
        ),
    ]


def _overview_activity_panels() -> list:
    return [
        timeseries_panel(
            9,
            "Packets per minute",
            "SELECT $__timeGroupAlias(time, $__interval), "
            "       portnum AS metric, COUNT(*)::float AS value "
            "FROM mesh_packet_metrics WHERE $__timeFilter(time) "
            "GROUP BY 1, portnum ORDER BY 1",
            grid(0, 6, 16, 7),
            {"description": "Mesh-wide packet rate broken out by portnum."},
        ),
        piechart_panel(
            10,
            "Packet types",
            "SELECT NOW() AS time, portnum AS metric, COUNT(*)::float AS value "
            "FROM mesh_packet_metrics WHERE $__timeFilter(time) "
            "GROUP BY portnum ORDER BY value DESC",
            grid(16, 6, 8, 7),
            {"description": "Distribution of packet types over the selected range."},
        ),
    ]


def _overview_quality_panels() -> list:
    # Series name = bare node_id so a Grafana data link can pass
    # ${__field.name} straight through as the nodeID variable. Click any
    # series in the legend to open Node Detail.
    top_util_sql = (
        "WITH top_nodes AS ("
        "  SELECT node_id, AVG(channel_utilization) AS util "
        "  FROM device_metrics "
        "  WHERE $__timeFilter(time) AND channel_utilization > 0 "
        "  GROUP BY node_id ORDER BY util DESC LIMIT 10"
        ") "
        "SELECT $__timeGroupAlias(dm.time, $__interval), "
        "       dm.node_id AS metric, "
        "       AVG(dm.channel_utilization) AS value "
        "FROM device_metrics dm "
        "JOIN top_nodes tn ON tn.node_id = dm.node_id "
        "WHERE $__timeFilter(dm.time) GROUP BY 1, 2 ORDER BY 1"
    )
    panel = timeseries_panel(
        12,
        "Top 10 channel utilizers",
        top_util_sql,
        grid(0, 14, 24, 9),
        {
            "description": "Top 10 nodes by avg ChUtil. Click a series in the legend to drill into Node Detail.",
            "unit": "percent",
        },
    )
    panel["fieldConfig"]["defaults"]["links"] = [
        {
            "title": "Open node ${__field.name}",
            "url": f"/d/{DASH_UIDS['node']}?var-nodeID=${{__field.name}}&${{__url_time_range}}",
            "targetBlank": False,
        }
    ]
    return [panel]


def _overview_directory() -> list:
    sql = (
        "SELECT m.source_id AS node_id, "
        "       COALESCE(nd.long_name, nd.short_name, m.source_id) AS name, "
        "       nd.hardware_model AS hardware, nd.role AS role, "
        "       COUNT(*) AS packets, MAX(m.time) AS last_seen "
        "FROM mesh_packet_metrics m "
        "LEFT JOIN node_details nd ON nd.node_id = m.source_id "
        "WHERE m.time > NOW() - INTERVAL '1 hour' "
        "GROUP BY m.source_id, nd.long_name, nd.short_name, nd.hardware_model, nd.role "
        "ORDER BY packets DESC LIMIT 50"
    )
    return [
        table_panel(
            15,
            "Most active nodes (1h)",
            sql,
            grid(0, 24, 24, 12),
            {
                "description": "Top 50 senders. Click any node_id to open the Node Detail dashboard.",
                "drill_field": "node_id",
                "drill_dashboard_uid": DASH_UIDS["node"],
            },
        )
    ]


def _overview_fleet_panels() -> list:
    hw_sql = (
        "SELECT NOW() AS time, "
        "       COALESCE(NULLIF(hardware_model,''),'unknown') AS metric, "
        "       COUNT(*)::float AS value "
        "FROM node_details WHERE node_id NOT IN ('4294967295','1','0') "
        "GROUP BY 2 ORDER BY value DESC LIMIT 20"
    )
    role_sql = (
        "SELECT NOW() AS time, "
        "       COALESCE(NULLIF(role,''),'unknown') AS metric, "
        "       COUNT(*)::float AS value "
        "FROM node_details WHERE node_id NOT IN ('4294967295','1','0') "
        "GROUP BY 2 ORDER BY value DESC"
    )
    preset_sql = (
        "SELECT NOW() AS time, "
        "       CASE WHEN modem_preset IS NULL OR modem_preset IN ('UNSET','') "
        "            THEN 'unknown' ELSE modem_preset END AS metric, "
        "       COUNT(*)::float AS value "
        "FROM node_details "
        "WHERE node_id NOT IN ('4294967295','1','0') "
        "GROUP BY 2 ORDER BY value DESC"
    )
    return [
        piechart_panel(
            16,
            "Hardware models",
            hw_sql,
            grid(0, 37, 8, 8),
            {
                "description": "Distribution of hardware models reported via NodeInfo / MapReport."
            },
        ),
        piechart_panel(
            17,
            "Node roles",
            role_sql,
            grid(8, 37, 8, 8),
            {"description": "What each node does (CLIENT / ROUTER / REPEATER / ...)."},
        ),
        piechart_panel(
            18,
            "Modem preset",
            preset_sql,
            grid(16, 37, 8, 8),
            {
                "description": (
                    "Modem preset (LONG_FAST, LONG_SLOW, ...). Only nodes that have "
                    "broadcast a MAP_REPORT_APP packet appear here — sparse on the public mesh."
                )
            },
        ),
    ]


def build_overview() -> dict[str, Any]:
    panels: list = [row(1, "Mesh health", 0)]
    panels.extend(_overview_health_tiles())
    panels.append(row(8, "Activity", 5))
    panels.extend(_overview_activity_panels())
    panels.append(row(11, "Mesh quality", 13))
    panels.extend(_overview_quality_panels())
    panels.append(row(14, "Nodes", 23))
    panels.extend(_overview_directory())
    panels.append(row(19, "Fleet composition", 36))
    panels.extend(_overview_fleet_panels())
    return dashboard(
        DASH_UIDS["overview"],
        "Mesh — Network Overview",
        panels,
        {
            "description": "Landing dashboard. Health tiles + activity. Click any node_id to drill into a node.",
            "tags": ["meshtastic", "overview"],
        },
    )


# ---------------------------------------------------------------------------
# 2. NODE DETAIL — per-node deep dive
# ---------------------------------------------------------------------------


def _node_header() -> dict:
    sql = (
        "SELECT node_id, short_name, long_name, hardware_model, role, mqtt_status, "
        "       latitude  * 1e-7 AS latitude, "
        "       longitude * 1e-7 AS longitude, altitude, updated_at "
        "FROM node_details WHERE node_id = '$nodeID' LIMIT 1"
    )
    return table_panel(
        1,
        "Node",
        sql,
        grid(0, 0, 12, 8),
        {"description": "Latest known state for the selected node."},
    )


def _node_map() -> dict:
    sql = (
        "SELECT node_id, "
        "       COALESCE(NULLIF(long_name,'Unknown'), short_name, node_id) AS name, "
        "       hardware_model, role, "
        "       longitude * 1e-7 AS longitude_norm, "
        "       latitude  * 1e-7 AS latitude_norm, altitude "
        "FROM node_details "
        "WHERE node_id = '$nodeID' AND longitude IS NOT NULL AND longitude <> 0"
    )
    return {
        "id": 30,
        "type": "geomap",
        "title": "Location",
        "description": "Last-known position for this node. Empty if the node hasn't broadcast a Position or MapReport.",
        "datasource": dict(DS),
        "gridPos": grid(12, 0, 12, 8),
        "targets": [target(sql, refId="Nodes")],
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {
            "basemap": {"config": {}, "name": "Basemap", "type": "default"},
            "controls": {
                "mouseWheelZoom": True,
                "showAttribution": True,
                "showDebug": False,
                "showMeasure": False,
                "showScale": True,
                "showZoom": True,
            },
            "layers": [
                {
                    "name": "Node",
                    "type": "markers",
                    "config": {
                        "showLegend": False,
                        "style": {
                            "color": {"fixed": "red"},
                            "opacity": 1,
                            "size": {"fixed": 10},
                            "symbol": {
                                "fixed": "img/icons/marker/circle.svg",
                                "mode": "fixed",
                            },
                        },
                    },
                    "filterData": {"id": "byRefId", "options": "Nodes"},
                    "location": {
                        "latitude": "latitude_norm",
                        "longitude": "longitude_norm",
                        "mode": "coords",
                    },
                    "tooltip": True,
                }
            ],
            "tooltip": {"mode": "details"},
            "view": {"id": "fit", "allLayers": True, "lastOnly": False, "padding": 30},
        },
    }


def _node_traffic_stats() -> list:
    return [
        stat_panel(
            3,
            "Sent (range)",
            "SELECT COUNT(*)::float AS value FROM mesh_packet_metrics "
            "WHERE source_id = '$nodeID' AND $__timeFilter(time)",
            grid(0, 9, 8, 4),
            {"description": "Packets sent by this node in the time range."},
        ),
        stat_panel(
            4,
            "Received (range)",
            "SELECT COUNT(*)::float AS value FROM mesh_packet_metrics "
            "WHERE destination_id = '$nodeID' AND $__timeFilter(time)",
            grid(8, 9, 8, 4),
            {"description": "Unicast packets addressed to this node."},
        ),
        stat_panel(
            5,
            "Last seen",
            "SELECT EXTRACT(EPOCH FROM MAX(time))::bigint * 1000 AS value "
            "FROM mesh_packet_metrics WHERE source_id = '$nodeID'",
            grid(16, 9, 8, 4),
            {
                "description": "Most recent packet from this node.",
                "unit": "dateTimeAsIso",
                "thresholds": [{"color": "blue", "value": None}],
                "no_value": "never",
            },
        ),
        piechart_panel(
            6,
            "Sent — by portnum",
            "SELECT NOW() AS time, portnum AS metric, COUNT(*)::float AS value "
            "FROM mesh_packet_metrics WHERE source_id = '$nodeID' "
            "AND $__timeFilter(time) GROUP BY portnum",
            grid(0, 13, 12, 6),
            {"description": "Packet types sent by this node."},
        ),
        piechart_panel(
            7,
            "Received — by portnum",
            "SELECT NOW() AS time, portnum AS metric, COUNT(*)::float AS value "
            "FROM mesh_packet_metrics WHERE destination_id = '$nodeID' "
            "AND $__timeFilter(time) GROUP BY portnum",
            grid(12, 13, 12, 6),
            {"description": "Unicast packet types addressed to this node."},
        ),
    ]


def _node_telemetry() -> list:
    return [
        timeseries_panel(
            9,
            "Battery level",
            "SELECT $__timeGroupAlias(time, $__interval), AVG(battery_level) AS battery "
            "FROM device_metrics WHERE node_id = '$nodeID' AND $__timeFilter(time) "
            "GROUP BY 1 ORDER BY 1",
            grid(0, 20, 12, 7),
            {
                "description": "Battery level reported via TELEMETRY_APP.",
                "unit": "percent",
                "legend": "hidden",
            },
        ),
        timeseries_panel(
            10,
            "Voltage",
            "SELECT $__timeGroupAlias(time, $__interval), AVG(voltage) AS voltage "
            "FROM device_metrics WHERE node_id = '$nodeID' AND $__timeFilter(time) "
            "GROUP BY 1 ORDER BY 1",
            grid(12, 20, 12, 7),
            {
                "description": "Voltage reported via TELEMETRY_APP.",
                "unit": "volt",
                "legend": "hidden",
            },
        ),
        timeseries_panel(
            11,
            "Channel utilization & airtime",
            "SELECT $__timeGroupAlias(time, $__interval), "
            '       AVG(channel_utilization) AS "ChUtil", '
            '       AVG(air_util_tx)         AS "AirUtilTX" '
            "FROM device_metrics WHERE node_id = '$nodeID' AND $__timeFilter(time) "
            "GROUP BY 1 ORDER BY 1",
            grid(0, 27, 24, 7),
            {
                "description": "ChUtil = receive-busy fraction. AirUtilTX = transmit duty cycle.",
                "unit": "percent",
            },
        ),
    ]


def _node_environment() -> list:
    base = (
        "SELECT $__timeGroupAlias(time, $__interval), AVG({col}) AS {alias} "
        "FROM environment_metrics WHERE node_id = '$nodeID' AND $__timeFilter(time) "
        "GROUP BY 1 ORDER BY 1"
    )
    return [
        timeseries_panel(
            13,
            "Temperature",
            base.format(col="temperature", alias="temperature"),
            grid(0, 35, 8, 7),
            {
                "description": "Temperature reading from ENVIRONMENT_METRICS.",
                "unit": "celsius",
                "legend": "hidden",
            },
        ),
        timeseries_panel(
            14,
            "Humidity",
            base.format(col="relative_humidity", alias="humidity"),
            grid(8, 35, 8, 7),
            {
                "description": "Relative humidity in percent.",
                "unit": "humidity",
                "legend": "hidden",
            },
        ),
        timeseries_panel(
            15,
            "Barometric pressure",
            base.format(col="barometric_pressure", alias="pressure"),
            grid(16, 35, 8, 7),
            {
                "description": "Barometric pressure in hPa.",
                "unit": "pressurehpa",
                "legend": "hidden",
            },
        ),
    ]


def _node_power() -> list:
    base = (
        "SELECT $__timeGroupAlias(time, $__interval), "
        '       AVG(ch1_{kind}) AS "Ch1", '
        '       AVG(ch2_{kind}) AS "Ch2", '
        '       AVG(ch3_{kind}) AS "Ch3" '
        "FROM power_metrics WHERE node_id = '$nodeID' AND $__timeFilter(time) "
        "GROUP BY 1 ORDER BY 1"
    )
    return [
        timeseries_panel(
            17,
            "Channel current",
            base.format(kind="current"),
            grid(0, 43, 12, 7),
            {"description": "Current measured on power channels.", "unit": "amp"},
        ),
        timeseries_panel(
            18,
            "Channel voltage",
            base.format(kind="voltage"),
            grid(12, 43, 12, 7),
            {"description": "Voltage measured on power channels.", "unit": "volt"},
        ),
    ]


def _node_topology() -> dict:
    nodes_sql = (
        "WITH peers AS ("
        "  SELECT destination_id AS node_id FROM mesh_packet_metrics "
        "  WHERE source_id = '$nodeID' "
        "    AND destination_id NOT IN ('4294967295','1','0') "
        "    AND $__timeFilter(time) "
        "  UNION SELECT source_id FROM mesh_packet_metrics "
        "  WHERE destination_id = '$nodeID' "
        "    AND source_id NOT IN ('4294967295','1','0') "
        "    AND $__timeFilter(time) "
        "  UNION SELECT '$nodeID'"
        ") "
        'SELECT cd.node_id AS "id", '
        "       COALESCE(NULLIF(cd.long_name,'Unknown'), cd.short_name, cd.node_id) AS \"title\", "
        '       cd.short_name AS "subtitle", '
        '       cd.hardware_model AS "detail__Hardware", '
        '       cd.role           AS "detail__Role", '
        "       CASE WHEN cd.node_id = '$nodeID' THEN '#3498DB' "
        "            WHEN cd.mqtt_status = 'online' THEN '#2ECC71' "
        "            ELSE '#7F8C8D' END AS \"color\" "
        "FROM node_details cd JOIN peers p ON p.node_id = cd.node_id"
    )
    edges_sql = (
        "WITH ids AS ("
        "  SELECT destination_id AS node_id FROM mesh_packet_metrics "
        "  WHERE source_id = '$nodeID' AND destination_id NOT IN ('4294967295','1','0') AND $__timeFilter(time) "
        "  UNION SELECT source_id FROM mesh_packet_metrics "
        "  WHERE destination_id = '$nodeID' AND source_id NOT IN ('4294967295','1','0') AND $__timeFilter(time) "
        "  UNION SELECT '$nodeID'"
        ") "
        "SELECT source_id || '_' || destination_id AS id, "
        '       source_id      AS "source", destination_id AS "target", '
        '       ROUND(AVG(NULLIF(rx_snr,0))::numeric, 1) AS "mainstat", '
        '       COUNT(*) AS "secondarystat", '
        "       CASE WHEN AVG(NULLIF(rx_snr,0)) < -13 THEN '#E74C3C' "
        "            WHEN AVG(NULLIF(rx_snr,0)) <  -7 THEN '#F4D03F' "
        "            ELSE '#2ECC71' END AS \"color\", "
        '       GREATEST(0.5, LEAST(4, LOG(COUNT(*) + 1))) AS "thickness" '
        "FROM mesh_packet_metrics "
        "WHERE destination_id NOT IN ('4294967295','1','0') "
        "  AND source_id      IN (SELECT node_id FROM ids) "
        "  AND destination_id IN (SELECT node_id FROM ids) "
        "  AND $__timeFilter(time) "
        "GROUP BY source_id, destination_id"
    )
    drill_url = (
        f"/d/{DASH_UIDS['node']}?var-nodeID=${{__data.fields.id}}&${{__url_time_range}}"
    )
    drill_links = [{"title": "Open node detail", "url": drill_url}]
    return {
        "id": 21,
        "type": "nodeGraph",
        "title": "Topology around this node",
        "description": (
            "This node (blue) plus every peer it has exchanged unicast traffic with in the time range. "
            "Edge thickness = packet count; color = avg SNR (green ≥ -7, yellow -13..-7, red < -13). "
            "Click any peer node to drill in."
        ),
        "datasource": dict(DS),
        "gridPos": grid(0, 51, 24, 12),
        "targets": [
            target(nodes_sql, refId="nodes"),
            target(edges_sql, refId="edges"),
        ],
        "fieldConfig": {
            "defaults": {"custom": {}},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "id"},
                    "properties": [{"id": "links", "value": drill_links}],
                },
                {
                    "matcher": {"id": "byName", "options": "title"},
                    "properties": [{"id": "links", "value": drill_links}],
                },
            ],
        },
        "options": {
            "nodes": {
                "mainStatUnit": "short",
                "secondaryStatUnit": "short",
                "arcs": [],
            },
            "edges": {"mainStatUnit": "short", "secondaryStatUnit": "short"},
            "nodeRadius": 40,
            "edgeRadius": 4,
            "zoomMode": "cooperative",
            "layoutAlgorithm": "force",
        },
    }


def _node_neighbors() -> dict:
    # Combine NEIGHBORINFO_APP (rare) with unicast traffic peers so the
    # panel shows the same connectivity the Network Map topology does.
    sql = (
        "WITH outgoing AS ("
        "  SELECT 'out' AS direction, destination_id AS peer_id, "
        "         COUNT(*) AS pkts, "
        "         ROUND(AVG(NULLIF(rx_snr, 0))::numeric, 1)  AS avg_snr, "
        "         ROUND(AVG(NULLIF(rx_rssi, 0))::numeric, 0) AS avg_rssi, "
        "         MAX(time)::timestamptz AS last_seen "
        "  FROM mesh_packet_metrics "
        "  WHERE source_id = '$nodeID' "
        "    AND destination_id NOT IN ('4294967295','1','0') "
        "    AND $__timeFilter(time) "
        "  GROUP BY destination_id"
        "), incoming AS ("
        "  SELECT 'in'  AS direction, source_id AS peer_id, "
        "         COUNT(*) AS pkts, "
        "         ROUND(AVG(NULLIF(rx_snr, 0))::numeric, 1)  AS avg_snr, "
        "         ROUND(AVG(NULLIF(rx_rssi, 0))::numeric, 0) AS avg_rssi, "
        "         MAX(time)::timestamptz AS last_seen "
        "  FROM mesh_packet_metrics "
        "  WHERE destination_id = '$nodeID' "
        "    AND source_id NOT IN ('4294967295','1','0') "
        "    AND $__timeFilter(time) "
        "  GROUP BY source_id"
        "), traffic AS ("
        "  SELECT * FROM outgoing UNION ALL SELECT * FROM incoming"
        "), neighbors AS ("
        "  SELECT 'neighbor' AS direction, neighbor_id AS peer_id, "
        "         NULL::bigint AS pkts, "
        "         ROUND(snr::numeric, 1) AS avg_snr, "
        "         NULL::numeric AS avg_rssi, "
        "         NULL::timestamptz AS last_seen "
        "  FROM node_neighbors WHERE node_id = '$nodeID'"
        ") "
        "SELECT t.direction, t.peer_id AS node_id, "
        "       COALESCE(NULLIF(nd.long_name,'Unknown'), nd.short_name, t.peer_id) AS name, "
        "       t.pkts, t.avg_snr, t.avg_rssi, t.last_seen "
        "FROM (SELECT * FROM traffic UNION ALL SELECT * FROM neighbors) t "
        "LEFT JOIN node_details nd ON nd.node_id = t.peer_id "
        "ORDER BY t.direction, t.pkts DESC NULLS LAST"
    )
    return table_panel(
        20,
        "Connections (table)",
        sql,
        grid(0, 63, 24, 10),
        {
            "description": (
                "Peers this node has talked to. "
                "Direction 'out' = unicast packets sent by $nodeID; "
                "'in' = unicast packets addressed to $nodeID; "
                "'neighbor' = NEIGHBORINFO_APP entries (rare on public mesh). "
                "Click any node_id to drill into that peer."
            ),
            "drill_field": "node_id",
            "drill_dashboard_uid": DASH_UIDS["node"],
            "color_thresholds": {
                "avg_snr": SNR_STEPS,
                "avg_rssi": RSSI_STEPS,
            },
        },
    )


def _node_var() -> dict:
    return query_var(
        "nodeID",
        "Node",
        "SELECT COALESCE(NULLIF(long_name,'Unknown'), short_name, node_id) "
        "       || ' (' || node_id || ')' AS __text, "
        "       node_id AS __value "
        "FROM node_details WHERE node_id NOT IN ('4294967295','1','0') "
        "ORDER BY long_name",
    )


def build_node_detail() -> dict[str, Any]:
    panels: list = [_node_header(), _node_map(), row(2, "Traffic", 8)]
    panels.extend(_node_traffic_stats())
    panels.append(row(8, "Device telemetry", 19))
    panels.extend(_node_telemetry())
    panels.append(row(12, "Environment", 34))
    panels.extend(_node_environment())
    panels.append(row(16, "Power", 42))
    panels.extend(_node_power())
    panels.append(row(19, "Connections", 50))
    panels.append(_node_topology())
    panels.append(_node_neighbors())
    return dashboard(
        DASH_UIDS["node"],
        "Mesh — Node Detail",
        panels,
        {
            "description": "Drill-down view for a single node.",
            "tags": ["meshtastic", "node"],
            "templating_vars": [_node_var()],
        },
    )


# ---------------------------------------------------------------------------
# 3. NETWORK MAP — geomap + topology
# ---------------------------------------------------------------------------


def _map_geomap() -> dict:
    sql = (
        "SELECT node_id, "
        "       COALESCE(NULLIF(long_name,'Unknown'), short_name, node_id) AS name, "
        "       hardware_model, role, mqtt_status, "
        "       longitude * 1e-7 AS longitude_norm, "
        "       latitude  * 1e-7 AS latitude_norm, altitude "
        "FROM node_details WHERE longitude IS NOT NULL AND longitude <> 0"
    )
    drill_url = (
        f"/d/{DASH_UIDS['node']}?var-nodeID="
        "${__data.fields.node_id}&${__url_time_range}"
    )
    return {
        "id": 2,
        "type": "geomap",
        "title": "Nodes on map",
        "description": "Last-known position of every node that broadcast Position or MapReport. Click a marker's tooltip link to drill into that node.",
        "datasource": dict(DS),
        "gridPos": grid(0, 1, 24, 12),
        "targets": [target(sql, refId="Nodes")],
        "fieldConfig": {
            "defaults": {},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "node_id"},
                    "properties": [
                        {
                            "id": "links",
                            "value": [{"title": "Open node detail", "url": drill_url}],
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "name"},
                    "properties": [
                        {
                            "id": "links",
                            "value": [{"title": "Open node detail", "url": drill_url}],
                        },
                    ],
                },
            ],
        },
        "options": {
            "basemap": {"config": {}, "name": "Basemap", "type": "default"},
            "controls": {
                "mouseWheelZoom": True,
                "showAttribution": True,
                "showDebug": False,
                "showMeasure": True,
                "showScale": True,
                "showZoom": True,
            },
            "layers": [
                {
                    "name": "Nodes",
                    "type": "markers",
                    "config": {
                        "showLegend": True,
                        "style": {
                            "color": {"fixed": "dark-green"},
                            "opacity": 0.8,
                            "size": {"fixed": 5, "min": 3, "max": 12},
                            "symbol": {
                                "fixed": "img/icons/marker/circle.svg",
                                "mode": "fixed",
                            },
                            "textConfig": {
                                "fontSize": 12,
                                "offsetX": 0,
                                "offsetY": 5,
                                "textAlign": "center",
                                "textBaseline": "middle",
                            },
                        },
                    },
                    "filterData": {"id": "byRefId", "options": "Nodes"},
                    "location": {
                        "latitude": "latitude_norm",
                        "longitude": "longitude_norm",
                        "mode": "coords",
                    },
                    "tooltip": True,
                }
            ],
            "tooltip": {"mode": "details"},
            "view": {"id": "fit", "allLayers": True, "lastOnly": False, "padding": 30},
        },
    }


_RANKED_CTE = (
    "WITH appearances AS ("
    "  SELECT source_id      AS node_id FROM mesh_packet_metrics "
    "  WHERE time > NOW() - INTERVAL '1 hour' "
    "    AND destination_id NOT IN ('4294967295','1','0') "
    "    AND source_id <> destination_id "
    "  UNION ALL "
    "  SELECT destination_id AS node_id FROM mesh_packet_metrics "
    "  WHERE time > NOW() - INTERVAL '1 hour' "
    "    AND destination_id NOT IN ('4294967295','1','0') "
    "    AND source_id <> destination_id "
    "  UNION ALL SELECT node_id     FROM node_neighbors "
    "  UNION ALL SELECT neighbor_id FROM node_neighbors"
    "), ranked AS ("
    "  SELECT node_id, COUNT(*) AS conns FROM appearances "
    "  GROUP BY node_id ORDER BY conns DESC LIMIT 200"
    ") "
)


def _map_nodegraph_nodes_sql() -> str:
    return (
        _RANKED_CTE + 'SELECT cd.node_id AS "id", cd.long_name AS "title", '
        '       cd.short_name AS "subtitle", '
        '       cd.hardware_model AS "detail__Hardware", '
        '       cd.role           AS "detail__Role", '
        '       cd.mqtt_status    AS "detail__MQTT status", '
        "       CASE WHEN cd.mqtt_status = 'online' THEN '#2ECC71' "
        "            WHEN cd.mqtt_status = 'offline' THEN '#E74C3C' "
        "            ELSE '#7F8C8D' END AS \"color\" "
        "FROM node_details cd JOIN ranked r ON r.node_id = cd.node_id"
    )


def _map_nodegraph_edges_sql() -> str:
    # Same `ranked` CTE as the nodes query — using a different ranking
    # produces different top-200 sets, which means edges referencing nodes
    # the nodes query didn't return, which crashes the panel with
    # "g.nodeRadius undefined".
    return (
        _RANKED_CTE + ", aggregated AS ("
        "  SELECT source_id, destination_id, COUNT(*) AS pkts, "
        "         AVG(NULLIF(rx_snr, 0)) AS avg_snr "
        "  FROM mesh_packet_metrics "
        "  WHERE time > NOW() - INTERVAL '1 hour' "
        "    AND destination_id NOT IN ('4294967295','1','0') "
        "    AND source_id <> destination_id "
        "    AND source_id      IN (SELECT node_id FROM ranked) "
        "    AND destination_id IN (SELECT node_id FROM ranked) "
        "  GROUP BY source_id, destination_id"
        ") "
        "SELECT source_id || '_' || destination_id AS id, "
        '       source_id      AS "source", destination_id AS "target", '
        '       ROUND(avg_snr::numeric, 1) AS "mainstat", pkts AS "secondarystat", '
        "       CASE WHEN avg_snr < -13 THEN '#E74C3C' "
        "            WHEN avg_snr <  -7 THEN '#F4D03F' "
        "            ELSE '#2ECC71' END AS \"color\", "
        '       GREATEST(0.5, LEAST(4, LOG(pkts + 1))) AS "thickness" '
        "FROM aggregated UNION ALL "
        "SELECT neighbor_id || '_' || node_id AS id, "
        '       neighbor_id AS "source", node_id AS "target", '
        '       snr AS "mainstat", NULL AS "secondarystat", '
        "       CASE WHEN snr < -13 THEN '#E74C3C' "
        "            WHEN snr <  -7 THEN '#F4D03F' "
        "            ELSE '#2ECC71' END AS \"color\", "
        '       GREATEST(0.5, LEAST(4, 1 + ((snr + 13) / 10))) AS "thickness" '
        "FROM node_neighbors "
        "WHERE node_id     IN (SELECT node_id FROM ranked) "
        "  AND neighbor_id IN (SELECT node_id FROM ranked)"
    )


def _map_nodegraph() -> dict:
    drill_url = (
        f"/d/{DASH_UIDS['node']}?var-nodeID=${{__data.fields.id}}&${{__url_time_range}}"
    )
    drill_links = [{"title": "Open node detail", "url": drill_url}]
    return {
        "id": 4,
        "type": "nodeGraph",
        "title": "Top-200 active senders",
        "description": (
            "Top 200 senders in the last hour plus NEIGHBORINFO peers. "
            "Edges = unicast traffic colored by SNR. "
            "Click a node and choose 'Open node detail' from the context menu."
        ),
        "datasource": dict(DS),
        "gridPos": grid(0, 14, 24, 14),
        "targets": [
            target(_map_nodegraph_nodes_sql(), refId="nodes"),
            target(_map_nodegraph_edges_sql(), refId="edges"),
        ],
        "fieldConfig": {
            "defaults": {"custom": {}},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "id"},
                    "properties": [{"id": "links", "value": drill_links}],
                },
                {
                    "matcher": {"id": "byName", "options": "title"},
                    "properties": [{"id": "links", "value": drill_links}],
                },
            ],
        },
        "options": {
            "nodes": {
                "mainStatUnit": "short",
                "secondaryStatUnit": "short",
                "arcs": [],
            },
            "edges": {"mainStatUnit": "short", "secondaryStatUnit": "short"},
            "nodeRadius": 40,
            "edgeRadius": 4,
            "zoomMode": "cooperative",
            "layoutAlgorithm": "force",
        },
    }


def build_map() -> dict[str, Any]:
    panels = [
        row(1, "Geographic map", 0),
        _map_geomap(),
        row(3, "Topology", 13),
        _map_nodegraph(),
    ]
    return dashboard(
        DASH_UIDS["map"],
        "Mesh — Network Map",
        panels,
        {
            "description": "Geographic positions plus radio topology.",
            "tags": ["meshtastic", "map"],
        },
    )


# ---------------------------------------------------------------------------
# 4. PAX — PAX-counter equipped nodes
# ---------------------------------------------------------------------------


def _pax_stats() -> list:
    return [
        stat_panel(
            1,
            "PAX nodes seen",
            "SELECT COUNT(DISTINCT node_id)::float AS value FROM pax_counter_metrics "
            "WHERE $__timeFilter(time)",
            grid(0, 0, 6, 4),
            {
                "description": "Distinct PAX nodes in the time range.",
                "thresholds": [{"color": "blue", "value": None}],
                "color_mode": "value",
            },
        ),
        stat_panel(
            2,
            "WiFi devices (latest)",
            "SELECT COALESCE(SUM(latest), 0)::float AS value FROM ("
            "  SELECT DISTINCT ON (node_id) node_id, wifi_stations AS latest "
            "  FROM pax_counter_metrics WHERE $__timeFilter(time) "
            "  ORDER BY node_id, time DESC) t",
            grid(6, 0, 6, 4),
            {
                "description": "Sum of latest WiFi station counts across PAX nodes.",
                "color_mode": "value",
            },
        ),
        stat_panel(
            3,
            "BLE devices (latest)",
            "SELECT COALESCE(SUM(latest), 0)::float AS value FROM ("
            "  SELECT DISTINCT ON (node_id) node_id, ble_beacons AS latest "
            "  FROM pax_counter_metrics WHERE $__timeFilter(time) "
            "  ORDER BY node_id, time DESC) t",
            grid(12, 0, 6, 4),
            {
                "description": "Sum of latest BLE beacon counts across PAX nodes.",
                "color_mode": "value",
            },
        ),
        stat_panel(
            4,
            "PAX uptime (max)",
            "SELECT COALESCE(MAX(uptime), 0)::float AS value FROM pax_counter_metrics "
            "WHERE $__timeFilter(time)",
            grid(18, 0, 6, 4),
            {
                "description": "Maximum PAX-counter uptime in the range.",
                "unit": "s",
                "thresholds": [{"color": "blue", "value": None}],
                "color_mode": "value",
            },
        ),
    ]


def build_pax() -> dict[str, Any]:
    trends_sql = (
        "SELECT $__timeGroupAlias(time, $__interval), "
        '       AVG(wifi_stations) AS "WiFi stations", '
        '       AVG(ble_beacons)   AS "BLE beacons" '
        "FROM pax_counter_metrics WHERE $__timeFilter(time) "
        "GROUP BY 1 ORDER BY 1"
    )
    table_sql = (
        "SELECT DISTINCT ON (p.node_id) p.node_id, "
        "       COALESCE(nd.long_name, nd.short_name, p.node_id) AS name, "
        "       p.wifi_stations, p.ble_beacons, p.uptime, p.time AS last_reading "
        "FROM pax_counter_metrics p "
        "LEFT JOIN node_details nd ON nd.node_id = p.node_id "
        "WHERE $__timeFilter(p.time) ORDER BY p.node_id, p.time DESC"
    )
    panels = _pax_stats() + [
        timeseries_panel(
            5,
            "WiFi & BLE counts over time",
            trends_sql,
            grid(0, 4, 24, 9),
            {"description": "Per-node trends from PAX_COUNTER packets."},
        ),
        table_panel(
            6,
            "PAX-equipped nodes",
            table_sql,
            grid(0, 13, 24, 8),
            {
                "description": "Most recent PAX reading per node. Click node_id for Node Detail.",
                "drill_field": "node_id",
                "drill_dashboard_uid": DASH_UIDS["node"],
            },
        ),
    ]
    return dashboard(
        DASH_UIDS["pax"],
        "Mesh — PAX Counters",
        panels,
        {
            "description": "People-counter (PAX) telemetry.",
            "tags": ["meshtastic", "pax"],
        },
    )


# ---------------------------------------------------------------------------
# 5. INVESTIGATION — raw debug tables
# ---------------------------------------------------------------------------


SNR_STEPS = [
    {"color": "red", "value": None},
    {"color": "yellow", "value": -13},
    {"color": "green", "value": -7},
]
RSSI_STEPS = [
    {"color": "red", "value": None},
    {"color": "yellow", "value": -110},
    {"color": "green", "value": -90},
]
HOP_STEPS = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 3},
    {"color": "red", "value": 6},
]
SIZE_STEPS = [
    {"color": "blue", "value": None},
    {"color": "green", "value": 64},
    {"color": "orange", "value": 200},
]


def _investigation_recent() -> dict:
    sql = (
        'SELECT m.time AS "time", '
        "       m.source_id AS node_id, "
        "       COALESCE(nd.long_name, nd.short_name, m.source_id) AS source_name, "
        "       CASE WHEN m.destination_id IN ('4294967295','1','0') THEN 'BROADCAST' "
        "            ELSE m.destination_id END AS destination_id, "
        "       m.portnum, m.channel, "
        "       ROUND(m.rx_snr::numeric,  1) AS rx_snr, "
        "       ROUND(m.rx_rssi::numeric, 0) AS rx_rssi, "
        "       m.hop_start, m.hop_limit, "
        "       m.message_size_bytes AS bytes, m.via_mqtt "
        "FROM mesh_packet_metrics m "
        "LEFT JOIN node_details nd ON nd.node_id = m.source_id "
        "WHERE $__timeFilter(m.time) "
        "ORDER BY m.time DESC LIMIT 200"
    )
    return table_panel(
        1,
        "Recent packets",
        sql,
        grid(0, 1, 24, 11),
        {
            "description": (
                "Last 200 raw mesh packets in the selected range. "
                "rx_snr / rx_rssi are color-coded — green = good signal, yellow = marginal, red = poor. "
                "destination_id 'BROADCAST' covers the all-nodes (0xFFFFFFFF) and all-routers (1) addresses; "
                "click any non-broadcast id (or any node_id) to drill into that node. "
                "hop_start = TTL the originator set; hop_limit = remaining hops at this gateway."
            ),
            "drill_fields": ["node_id", "destination_id"],
            "drill_dashboard_uid": DASH_UIDS["node"],
            "color_thresholds": {
                "rx_snr": SNR_STEPS,
                "rx_rssi": RSSI_STEPS,
                "hop_start": HOP_STEPS,
                "bytes": SIZE_STEPS,
            },
        },
    )


def _investigation_traffic_breakdown() -> list:
    portnum_ts_sql = (
        "SELECT $__timeGroupAlias(time, $__interval), "
        "       portnum AS metric, COUNT(*)::float AS value "
        "FROM mesh_packet_metrics WHERE $__timeFilter(time) "
        "GROUP BY 1, portnum ORDER BY 1"
    )
    totals_sql = (
        "SELECT m.source_id AS node_id, m.portnum, COUNT(*) AS packets "
        "FROM mesh_packet_metrics m "
        "WHERE $__timeFilter(m.time) "
        "GROUP BY m.source_id, m.portnum ORDER BY packets DESC LIMIT 200"
    )
    return [
        timeseries_panel(
            2,
            "Packets per minute by portnum",
            portnum_ts_sql,
            grid(0, 13, 12, 9),
            {
                "description": "Per-portnum packet rate. Sustained spikes can indicate a misbehaving node or a routing storm."
            },
        ),
        table_panel(
            3,
            "Per-source / per-portnum totals",
            totals_sql,
            grid(12, 13, 12, 9),
            {
                "description": (
                    "Packet counts grouped by originating node and portnum. "
                    "Click any node_id to drill into that node's detail page."
                ),
                "drill_field": "node_id",
                "drill_dashboard_uid": DASH_UIDS["node"],
            },
        ),
    ]


def _investigation_quality() -> list:
    snr_sql = (
        "SELECT m.source_id AS node_id, "
        "       COALESCE(nd.long_name, nd.short_name, m.source_id) AS name, "
        "       ROUND(AVG(m.rx_snr)::numeric,  1) AS avg_snr, "
        "       ROUND(AVG(m.rx_rssi)::numeric, 0) AS avg_rssi, "
        "       MIN(m.rx_snr) AS min_snr, MAX(m.rx_snr) AS max_snr, "
        "       COUNT(*)      AS packets "
        "FROM mesh_packet_metrics m "
        "LEFT JOIN node_details nd ON nd.node_id = m.source_id "
        "WHERE $__timeFilter(m.time) AND m.rx_snr IS NOT NULL AND m.rx_snr <> 0 "
        "  AND m.destination_id NOT IN ('4294967295','1','0') "
        "GROUP BY m.source_id, nd.long_name, nd.short_name "
        "HAVING COUNT(*) > 2 ORDER BY avg_snr ASC LIMIT 50"
    )
    hops_sql = (
        "SELECT m.source_id AS node_id, "
        "       COALESCE(nd.long_name, nd.short_name, m.source_id) AS name, "
        "       MAX(m.hop_start)               AS max_hop_start, "
        "       MAX(m.hop_start - m.hop_limit) AS max_hops_taken, "
        "       COUNT(*)                       AS packets "
        "FROM mesh_packet_metrics m "
        "LEFT JOIN node_details nd ON nd.node_id = m.source_id "
        "WHERE $__timeFilter(m.time) AND m.hop_start > 0 "
        "GROUP BY m.source_id, nd.long_name, nd.short_name "
        "ORDER BY max_hops_taken DESC LIMIT 50"
    )
    return [
        table_panel(
            4,
            "Worst SNR / RSSI senders",
            snr_sql,
            grid(0, 23, 12, 10),
            {
                "description": (
                    "Nodes whose unicast packets arrive with the worst signal-to-noise ratio. "
                    "Broadcast destinations are excluded so the SNR reflects directed-traffic quality."
                ),
                "drill_field": "node_id",
                "drill_dashboard_uid": DASH_UIDS["node"],
                "color_thresholds": {
                    "avg_snr": SNR_STEPS,
                    "avg_rssi": RSSI_STEPS,
                    "min_snr": SNR_STEPS,
                    "max_snr": SNR_STEPS,
                },
            },
        ),
        table_panel(
            5,
            "Hop usage",
            hops_sql,
            grid(12, 23, 12, 10),
            {
                "description": (
                    "How many hops each node's traffic actually traversed. "
                    "max_hop_start = TTL the originator set; max_hops_taken = (hop_start − hop_limit) at this gateway. "
                    "High values are normal for distant nodes; very high values from many sources can mean a routing storm."
                ),
                "drill_field": "node_id",
                "drill_dashboard_uid": DASH_UIDS["node"],
                "color_thresholds": {
                    "max_hop_start": HOP_STEPS,
                    "max_hops_taken": HOP_STEPS,
                },
            },
        ),
    ]


def _investigation_fleet() -> list:
    hw_sql = (
        "SELECT NOW() AS time, COALESCE(hardware_model,'unknown') AS metric, "
        "       COUNT(*)::float AS value "
        "FROM node_details WHERE node_id NOT IN ('4294967295','1','0') "
        "GROUP BY 2 ORDER BY value DESC"
    )
    role_sql = (
        "SELECT NOW() AS time, COALESCE(role,'unknown') AS metric, "
        "       COUNT(*)::float AS value "
        "FROM node_details WHERE node_id NOT IN ('4294967295','1','0') "
        "  AND role IS NOT NULL GROUP BY 2 ORDER BY value DESC"
    )
    return [
        piechart_panel(
            6,
            "Hardware models",
            hw_sql,
            grid(0, 34, 12, 8),
            {
                "description": "Distribution of hardware models reported via NodeInfo / MapReport."
            },
        ),
        piechart_panel(
            7,
            "Node roles",
            role_sql,
            grid(12, 34, 12, 8),
            {
                "description": "Roles describe what each node does (CLIENT, ROUTER, REPEATER, ROUTER_CLIENT, ...)."
            },
        ),
    ]


def _investigation_config() -> dict:
    sql = (
        "SELECT node_id, "
        "       NULLIF(to_char(device_update_interval,      'HH24:MI:SS'), '00:00:00') AS device_iv, "
        "       NULLIF(to_char(environment_update_interval, 'HH24:MI:SS'), '00:00:00') AS env_iv, "
        "       NULLIF(to_char(power_update_interval,       'HH24:MI:SS'), '00:00:00') AS power_iv, "
        "       NULLIF(to_char(pax_counter_interval,        'HH24:MI:SS'), '00:00:00') AS pax_iv, "
        "       NULLIF(to_char(neighbor_info_interval,      'HH24:MI:SS'), '00:00:00') AS neighbor_iv, "
        "       NULLIF(to_char(map_broadcast_interval,      'HH24:MI:SS'), '00:00:00') AS map_iv, "
        "       last_updated "
        "FROM node_configurations "
        "WHERE EXTRACT(EPOCH FROM device_update_interval)      > 1 "
        "   OR EXTRACT(EPOCH FROM environment_update_interval) > 1 "
        "   OR EXTRACT(EPOCH FROM power_update_interval)       > 1 "
        "   OR EXTRACT(EPOCH FROM pax_counter_interval)        > 1 "
        "   OR EXTRACT(EPOCH FROM neighbor_info_interval)      > 1 "
        "   OR EXTRACT(EPOCH FROM map_broadcast_interval)      > 1 "
        "ORDER BY ("
        "  (CASE WHEN EXTRACT(EPOCH FROM environment_update_interval) > 1 THEN 1 ELSE 0 END) +"
        "  (CASE WHEN EXTRACT(EPOCH FROM power_update_interval)       > 1 THEN 1 ELSE 0 END) +"
        "  (CASE WHEN EXTRACT(EPOCH FROM pax_counter_interval)        > 1 THEN 1 ELSE 0 END) +"
        "  (CASE WHEN EXTRACT(EPOCH FROM neighbor_info_interval)      > 1 THEN 1 ELSE 0 END) +"
        "  (CASE WHEN EXTRACT(EPOCH FROM map_broadcast_interval)      > 1 THEN 1 ELSE 0 END)"
        ") DESC, last_updated DESC LIMIT 200"
    )
    return table_panel(
        8,
        "Node configurations",
        sql,
        grid(0, 43, 24, 10),
        {
            "description": (
                "Inferred reporting cadence per metric family — how often each node sends each telemetry type. "
                "device_iv = device metrics interval (battery / voltage / ChUtil). "
                "env_iv = environment metrics (temperature / humidity / pressure). "
                "power_iv = power metrics (channel voltages / currents). "
                "pax_iv = PAX-counter interval. "
                "neighbor_iv = NEIGHBORINFO_APP interval. "
                "map_iv = MAP_REPORT_APP interval. "
                "Only nodes with at least one non-zero interval are shown; refreshed hourly by a TimescaleDB scheduled job."
            ),
            "drill_field": "node_id",
            "drill_dashboard_uid": DASH_UIDS["node"],
        },
    )


def build_investigation() -> dict[str, Any]:
    panels: list = [row(100, "Recent packets", 0), _investigation_recent()]
    panels.append(row(101, "Traffic breakdown", 12))
    panels.extend(_investigation_traffic_breakdown())
    panels.append(row(102, "Signal quality & routing", 22))
    panels.extend(_investigation_quality())
    panels.append(row(103, "Fleet composition", 33))
    panels.extend(_investigation_fleet())
    panels.append(row(104, "Reporting intervals", 42))
    panels.append(_investigation_config())
    return dashboard(
        DASH_UIDS["investigation"],
        "Mesh — Investigation",
        panels,
        {
            "description": (
                "Raw tables and breakdowns for debugging. "
                "Most node_id and destination_id cells link into the per-node Node Detail dashboard. "
                "Color-coded SNR / RSSI / hop columns highlight problematic packets at a glance."
            ),
            "tags": ["meshtastic", "debug"],
        },
    )


# ---------------------------------------------------------------------------
# write everything
# ---------------------------------------------------------------------------


BUILDERS = [
    ("Network Overview.json", build_overview),
    ("Node Detail.json", build_node_detail),
    ("Network Map.json", build_map),
    ("PAX Counters.json", build_pax),
    ("Investigation.json", build_investigation),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    for name, builder in BUILDERS:
        (OUT / name).write_text(json.dumps(builder(), indent=2) + "\n")
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
