<div align="center">

# 📡 Meshtastic Metrics Exporter

**Drop-in observability for any Meshtastic mesh — MQTT → TimescaleDB → Grafana**

[![CodeQL](https://github.com/tcivie/meshtastic-metrics-exporter/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/tcivie/meshtastic-metrics-exporter/actions/workflows/github-code-scanning/codeql)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Grafana 13](https://img.shields.io/badge/Grafana-13.0-orange?logo=grafana&logoColor=white)](https://grafana.com/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-pg16-336791?logo=postgresql&logoColor=white)](https://www.timescale.com/)
[![Python 3](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)

Subscribes to a Meshtastic MQTT topic, decodes every packet type, stores time-series telemetry in TimescaleDB hypertables, and ships five linked Grafana dashboards out of the box.

</div>

---

## ✨ Highlights

- 📥 Ingests every Meshtastic packet type — telemetry, position, neighbor info, map reports, PAX, traceroute, …
- 🗜️ TimescaleDB hypertables with **14-day** columnstore compression and **30-day** retention
- 🧭 Five linked dashboards with click-through drill-downs from any `node_id` cell
- 🎨 Color-coded SNR / RSSI / hop columns — bad signals jump out at a glance
- 🔌 Single `docker compose up -d` — no extra wiring required
- 🧪 Pytest suite covering the dashboards, DB-handler SQL, and protobuf processors

---

## 📑 Table of contents

- [Quick start](#-quick-start)
- [Architecture](#-architecture)
- [Database schema](#-database-schema)
- [Dashboards](#-dashboards)
- [Configuration](#-configuration)
- [Community showcases](#-community-showcases)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Quick start

```bash
git clone https://github.com/tcivie/meshtastic-metrics-exporter.git
cd meshtastic-metrics-exporter
cp .env.example .env       # adjust MQTT credentials, etc.
docker compose up -d
```

Open Grafana at http://localhost:3000 (login `admin` / `admin`). The home page is **Mesh — Network Overview**.

> **Recommendation:** allow 24 hours of data collection before expecting meaningful insights — many panels become populated only once telemetry, neighbor info, and map reports start arriving.

---

## 🏗️ Architecture

```
                   ┌────────────┐
                   │   MQTT     │
                   │  Broker    │
                   └─────┬──────┘
                         │ envelopes
                         ▼
   ┌──────────────────────────────────────────────┐
   │  Exporter (Python)                           │
   │  ─ subscribes to mesh topics                 │
   │  ─ decrypts default-key packets              │
   │  ─ parses protobufs                          │
   │  ─ writes hypertable rows                    │
   └─────┬─────────────────────────────────┬──────┘
         │                                 │
         ▼                                 ▼
   ┌────────────┐                    ┌──────────┐
   │ TimescaleDB │ ◀───── reads ──── │ Grafana  │
   │ (Postgres) │                    │ (5 dash) │
   └────────────┘                    └──────────┘
```

Three containers (`exporter`, `timescaledb`, `grafana`) are orchestrated by a single `docker-compose.yml`.

For affordable hosting I personally use [Hetzner Cloud](https://hetzner.cloud/?ref=iMFSvXv8FFMJ) — VPS plans suit TimescaleDB + Grafana well. *(Referral link: supports the project at no extra cost; gets you €20 to start.)*

---

## 🗄️ Database schema

### Regular tables

| Table | Purpose |
|-------|---------|
| `messages` | Dedup TTL, cleared by a TimescaleDB scheduled job |
| `node_details` | Latest known state per node (names, hardware, role, last position, MQTT status, firmware/region/preset) |
| `node_neighbors` | Topology edges from `NEIGHBORINFO_APP` (rare on the public mesh) |
| `node_configurations` | Inferred reporting cadence per metric family — refreshed every 10 minutes |

### Hypertables (1-day chunks · 14-day compression · 30-day retention)

| Hypertable | What's in it |
|------------|--------------|
| `device_metrics` | Battery, voltage, channel utilization, airtime, uptime |
| `environment_metrics` | Temperature, humidity, pressure, gas, IAQ, light, wind, weight |
| `air_quality_metrics` | Particulate matter (PM1.0/2.5/10) standard + environmental |
| `power_metrics` | Per-channel voltage / current (3 channels) |
| `pax_counter_metrics` | WiFi station + BLE beacon counts, PAX uptime |
| `mesh_packet_metrics` | Per-packet metadata (portnum, channel, SNR, RSSI, hop start/limit, priority, size) |
| `local_stats` | Node-side packet counters (TX/RX/bad/dupe/relay) and observed mesh size |
| `node_position_metrics` | Position history with GPS quality (sats, HDOP, ground speed) |

All hypertables are columnstore-compressed (`segmentby = node_id` / `source_id`, `orderby = time DESC`).

---

## 📊 Dashboards

Five linked dashboards. Click the **Mesh dashboards** dropdown in the top-left of any page to switch, or click any `node_id` cell, map marker, or topology node to drill in.

| Dashboard | UID | Purpose |
|-----------|-----|---------|
| **Mesh — Network Overview** | `mesh-overview` | Landing page; mesh health tiles + global activity (Grafana home) |
| **Mesh — Node Detail** | `mesh-node-detail` | Per-node deep dive — pick a node from the dropdown or land here from a drill-down |
| **Mesh — Network Map** | `mesh-network-map` | Geographic positions + topology graph |
| **Mesh — PAX Counters** | `mesh-pax` | PAX-counter telemetry (WiFi / BLE device counts) |
| **Mesh — Investigation** | `mesh-investigation` | Raw tables, color-coded SNR / RSSI / hops, fleet composition |

> Dashboard links target `localhost:3000`. Update panel link configurations to match your Grafana server address if hosting elsewhere.

<details>
<summary><b>🌐 Mesh — Network Overview</b> · click to expand screenshots</summary>

The lobby of the dashboard set: mesh health tiles up top (each clickable to drill into a detail dashboard), global activity, top channel utilizers, then a directory of the most active nodes.

<p align="center">
  <img src="docs/screenshots/network-overview-top.png" alt="Network Overview — health tiles, activity, mesh quality" width="100%" />
</p>

Scroll down: most active nodes table (every `node_id` is a drill-down link) and fleet composition pies (hardware models, roles, modem preset).

<p align="center">
  <img src="docs/screenshots/network-overview-bottom.png" alt="Network Overview — most active nodes & fleet composition" width="100%" />
</p>

</details>

<details>
<summary><b>📍 Mesh — Node Detail</b> · click to expand screenshots</summary>

Header + location map up top, then traffic / telemetry / environment / power sections, finishing with a per-node topology graph and a Connections table.

<p align="center">
  <img src="docs/screenshots/node-detail-top.png" alt="Node Detail — header, location, traffic, telemetry" width="100%" />
</p>

Per-node topology graph (this node in blue, peers in gray, edges colored by SNR) plus a sortable Connections table — every peer `node_id` links to its own Node Detail page.

<p align="center">
  <img src="docs/screenshots/node-detail-topology.png" alt="Node Detail — topology + connections" width="100%" />
</p>

</details>

<details>
<summary><b>🗺️ Mesh — Network Map</b> · click to expand screenshots</summary>

Geographic markers for every node that has broadcast a Position or MapReport. Below: the full mesh topology derived from the last hour of unicast traffic. Markers and topology nodes both carry a click-through link to the per-node detail page.

<p align="center">
  <img src="docs/screenshots/network-map.png" alt="Network Map — geomap + topology graph" width="100%" />
</p>

- **Marker color** — green = node has been seen recently
- **Topology edge color** — green ≥ -7 dB · yellow -13 to -7 dB · red < -13 dB
- **Topology edge thickness** — log-scaled packet count

</details>

<details>
<summary><b>🔬 Mesh — Investigation</b> · click to expand screenshots</summary>

Raw debugging surface. Recent packets table color-codes `rx_snr` / `rx_rssi` / `hop_start` / `bytes` so problems jump out; both `node_id` and `destination_id` cells link into Node Detail.

<p align="center">
  <img src="docs/screenshots/investigation-recent.png" alt="Investigation — recent packets & traffic breakdown" width="100%" />
</p>

Below: signal quality + hop usage tables, fleet composition pies, and inferred reporting intervals per metric family (refreshed every 10 minutes by a TimescaleDB scheduled job).

<p align="center">
  <img src="docs/screenshots/investigation-quality.png" alt="Investigation — signal quality, fleet, reporting intervals" width="100%" />
</p>

</details>

---

## ⚙️ Configuration

Configure the exporter via `.env` at the repo root:

```dotenv
# TimescaleDB connection
DATABASE_URL=postgres://postgres:postgres@timescaledb:5432/meshtastic

# MQTT connection (defaults are the public Meshtastic broker)
MQTT_HOST=mqtt.meshtastic.org
MQTT_PORT=1883
MQTT_USERNAME=meshdev
MQTT_PASSWORD=large4cats
MQTT_KEEPALIVE=60
MQTT_TOPIC='msh/US/#'
MQTT_IS_TLS=false

# MQTT protocol version (MQTTv311 for the public broker)
# Options: MQTTv311, MQTTv31, MQTTv5
MQTT_PROTOCOL=MQTTv311

# MQTT callback API version
# Options: VERSION1, VERSION2
MQTT_CALLBACK_API_VERSION=VERSION2

# Privacy
MESH_HIDE_SOURCE_DATA=false
MESH_HIDE_DESTINATION_DATA=false

# Default channel key — only packets sent on the default channel are decryptable
MQTT_SERVER_KEY=1PG7OiApB1nwvP+rz05pAQ==

# Comma-separated list of portnums whose payload should be skipped
# (mesh_packet_metrics still records the envelope, only the payload processor is filtered)
# Full list: https://buf.build/meshtastic/protobufs/docs/main:meshtastic#meshtastic.PortNum
EXPORTER_MESSAGE_TYPES_TO_FILTER=TEXT_MESSAGE_APP

# Logging
ENABLE_STREAM_HANDLER=true
LOG_LEVEL=INFO
LOG_FILE_MAX_SIZE=10MB
LOG_FILE_BACKUP_COUNT=5
```

Run:

```bash
docker compose up -d
```

starts:

- **exporter** — the Python service consuming MQTT and writing to TimescaleDB
- **timescaledb** — Postgres 16 + TimescaleDB extension; schema is created idempotently on first init
- **grafana** — Grafana 13 with the five dashboards provisioned and Network Overview pinned as home

---

## 🌍 Community showcases

Running this exporter for your local mesh community? We'd love to hear about it.

If you have a public dashboard or an interesting deployment, open a [discussion](https://github.com/tcivie/meshtastic-metrics-exporter/discussions) or submit a PR adding your instance to the table below. Share what you're monitoring, how you've customized things, or what features you wish existed — it all helps shape where this project goes next.

| Community | Dashboard | Maintainer | Notes |
|-----------|-----------|------------|-------|
| Canadaverse | [dash.mt.gt](https://dash.mt.gt) (guest/guest) | [@tb0hdan](https://github.com/tb0hdan) | Production deployment |
| *Your community here* | — | — | [Add yours →](https://github.com/tcivie/meshtastic-metrics-exporter/pulls) |

### Feature requests & ideas

Got ideas for new metrics, dashboards, or integrations? Open an [issue](https://github.com/tcivie/meshtastic-metrics-exporter/issues) tagged `enhancement`. Seeing what different communities actually need is the best way to prioritise development.

---

## 🤝 Contributing

Contributions are welcome — open an issue or submit a pull request. The dashboard JSON is generated by `scripts/build_dashboards.py`, so panel changes should land there rather than as hand edits to the generated files.

Run the test suite locally:

```bash
pip install -r requirements.txt pytest
python scripts/build_dashboards.py
pytest tests/
```

---

## 📜 License

GPL v3 — see [LICENSE](LICENSE).
