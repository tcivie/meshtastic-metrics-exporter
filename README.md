# Meshtastic Metrics Exporter
[![CodeQL](https://github.com/tcivie/meshtastic-metrics-exporter/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/tcivie/meshtastic-metrics-exporter/actions/workflows/github-code-scanning/codeql)

The `meshtastic-metrics-exporter` is a tool designed to export nearly all available data from an MQTT server
to a Prometheus server. It comes with a pre-configured Grafana dashboard connected to both data sources,
allowing users to start creating dashboards immediately.

## Features

- Exports a comprehensive set of metrics from an MQTT server to Prometheus.
- Comes with a Grafana dashboard configured to connect to both Prometheus and Postgres data sources.
  - Comes with some basic dashboards, see the section below for general view of the dashboards
- Stores node details (ID, short/long name, hardware details, and client type) in a Postgres server, which is also part
  of the package.
- Configuration via a `.env` file.

### Database Structure

The system uses PostgreSQL with the following tables:

#### 1. messages

- Stores message IDs and timestamps
- Auto-expires messages older than 1 minute using a trigger

```sql
Columns:
- id (TEXT, PRIMARY KEY)
- received_at (TIMESTAMP)
```

#### 2. node_details

- Stores basic information about mesh nodes

```sql
Columns:
- node_id (VARCHAR, PRIMARY KEY)
- short_name (VARCHAR)
- long_name (VARCHAR)
- hardware_model (VARCHAR)
- role (VARCHAR)
- mqtt_status (VARCHAR, default 'none')
- longitude (INT)
- latitude (INT)
- altitude (INT)
- precision (INT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### 3. node_neighbors

- Tracks connections between nodes

```sql
Columns:
- id (SERIAL, PRIMARY KEY)
- node_id (VARCHAR, FOREIGN KEY)
- neighbor_id (VARCHAR, FOREIGN KEY)
- snr (FLOAT)
```

#### 4. node_configurations

- Stores detailed configuration and timing information for nodes

```sql
Columns:
- node_id (VARCHAR, PRIMARY KEY)
- last_updated (TIMESTAMP)
- environment_update_interval (INTERVAL)
- environment_update_last_timestamp (TIMESTAMP)
- device_update_interval (INTERVAL)
- device_update_last_timestamp (TIMESTAMP)
- air_quality_update_interval (INTERVAL)
- air_quality_update_last_timestamp (TIMESTAMP)
- power_update_interval (INTERVAL)
- power_update_last_timestamp (TIMESTAMP)
- range_test_interval (INTERVAL)
- range_test_packets_total (INT)
- range_test_first_packet_timestamp (TIMESTAMP)
- range_test_last_packet_timestamp (TIMESTAMP)
- pax_counter_interval (INTERVAL)
- pax_counter_last_timestamp (TIMESTAMP)
- neighbor_info_interval (INTERVAL)
- neighbor_info_last_timestamp (TIMESTAMP)
- mqtt_encryption_enabled (BOOLEAN)
- mqtt_json_enabled (BOOLEAN)
- mqtt_json_message_timestamp (TIMESTAMP)
- mqtt_configured_root_topic (TEXT)
- mqtt_info_last_timestamp (TIMESTAMP)
- map_broadcast_interval (INTERVAL)
- map_broadcast_last_timestamp (TIMESTAMP)
```

### Grafana Dashboards

The project comes with 2 dashboards.

#### Main Dashboard

<img width="1470" alt="image" src="https://github.com/user-attachments/assets/09fe72e5-23eb-4516-9f34-19e2cc38b7dc">

> The dashboard has some basic data about the mesh network and its data is temporarily updated
> (With new data coming in it would fill out the missing pieces automatically)

**Note:** The dashboard contains links to nodes that target `localhost:3000`.
If you're accessing Grafana from a different host, you'll need to modify these links in the panel configuration
to match your Grafana server's address.

#### User Panel

![image](https://github.com/user-attachments/assets/d344b7dd-dadc-4cbe-84cc-44333ea6e0c4)


> This panel can be reached from the "Node ID" link on the main dashboard (The table in the center)
> or you can go to it from the dashboards tab in Grafana and select the node you want to spectate.
> This board includes some telemetry data and basic information about the node.

#### The Node Graph

<img width="585" alt="SCR-20240707-qjaj" src="https://github.com/tcivie/meshtastic-metrics-exporter/assets/87943721/d29b2ac4-6291-4095-9938-e6e63df15098">

> Both boards also include node graph which allows you to view nodes which are sending [Neighbour Info packets](https://meshtastic.org/docs/configuration/module/neighbor-info)
> As long as we have some node which is connected to our MQTT server the data would be read by the exporter
> and parsed as node graph. The line colors indicate the SNR value and the arrow is the direction of the flow captured
> (It can be two way). And the node circle color indicates which node is connected to MQTT (Green)
> which one is disconnected from MQTT (Red) and unknown (Gray - Never connected to the MQTT server)

**It is highly recommended to give the system 24 hours to stabilize before seeking any useful information from it.**

## Exported Metrics

🏷️ Common Labels: `node_id, short_name, long_name, hardware_model, role`

Label Notation:
- 🏷️: Indicates that all common labels are used.
- 🏷️ (source): Indicates that all common labels are used, prefixed with "source_" (e.g., source_node_id, source_short_name, etc.).
- 🏷️ (destination): Indicates that all common labels are used, prefixed with "destination_" (e.g., destination_node_id, destination_short_name, etc.).

### Available Metrics

| Metric Name                                    | Description                                      | Type      | Labels                                     |
|------------------------------------------------|--------------------------------------------------|-----------|--------------------------------------------|
| text_message_app_length                        | Length of text messages processed by the app     | Histogram | 🏷️                                        |
| device_latitude                                | Device latitude                                  | Gauge     | 🏷️                                        |
| device_longitude                               | Device longitude                                 | Gauge     | 🏷️                                        |
| device_altitude                                | Device altitude                                  | Gauge     | 🏷️                                        |
| device_position_precision                      | Device position precision                        | Gauge     | 🏷️                                        |
| telemetry_app_ch[1-3]_voltage                  | Voltage measured by the device on channels 1-3   | Gauge     | 🏷️                                        |
| telemetry_app_ch[1-3]_current                  | Current measured by the device on channels 1-3   | Gauge     | 🏷️                                        |
| telemetry_app_pm[10/25/100]_standard           | Concentration Units Standard PM1.0/2.5/10.0      | Gauge     | 🏷️                                        |
| telemetry_app_pm[10/25/100]_environmental      | Concentration Units Environmental PM1.0/2.5/10.0 | Gauge     | 🏷️                                        |
| telemetry_app_particles_[03/05/10/25/50/100]um | Particle Count for different sizes               | Gauge     | 🏷️                                        |
| telemetry_app_temperature                      | Temperature measured by the device               | Gauge     | 🏷️                                        |
| telemetry_app_relative_humidity                | Relative humidity percent                        | Gauge     | 🏷️                                        |
| telemetry_app_barometric_pressure              | Barometric pressure in hPA                       | Gauge     | 🏷️                                        |
| telemetry_app_gas_resistance                   | Gas resistance in MOhm                           | Gauge     | 🏷️                                        |
| telemetry_app_iaq                              | IAQ value (0-500)                                | Gauge     | 🏷️                                        |
| telemetry_app_distance                         | Distance in mm                                   | Gauge     | 🏷️                                        |
| telemetry_app_lux                              | Ambient light in Lux                             | Gauge     | 🏷️                                        |
| telemetry_app_white_lux                        | White light in Lux                               | Gauge     | 🏷️                                        |
| telemetry_app_ir_lux                           | Infrared light in Lux                            | Gauge     | 🏷️                                        |
| telemetry_app_uv_lux                           | Ultraviolet light in Lux                         | Gauge     | 🏷️                                        |
| telemetry_app_wind_direction                   | Wind direction in degrees                        | Gauge     | 🏷️                                        |
| telemetry_app_wind_speed                       | Wind speed in m/s                                | Gauge     | 🏷️                                        |
| telemetry_app_weight                           | Weight in KG                                     | Gauge     | 🏷️                                        |
| telemetry_app_battery_level                    | Battery level (0-100, >100 means powered)        | Gauge     | 🏷️                                        |
| telemetry_app_voltage                          | Voltage                                          | Gauge     | 🏷️                                        |
| telemetry_app_channel_utilization              | Channel utilization including TX, RX, and noise  | Gauge     | 🏷️                                        |
| telemetry_app_air_util_tx                      | Airtime utilization for TX in last hour          | Gauge     | 🏷️                                        |
| telemetry_app_uptime_seconds                   | Device uptime in seconds                         | Counter   | 🏷️                                        |
| route_length                                   | Number of nodes in route                         | Counter   | 🏷️                                        |
| route_response                                 | Number of route discovery responses              | Counter   | 🏷️, response_type                         |
| mesh_packet_source_types                       | Mesh packet types by source                      | Counter   | 🏷️ (source), portnum                      |
| mesh_packet_destination_types                  | Mesh packet types by destination                 | Counter   | 🏷️ (destination), portnum                 |
| mesh_packet_total                              | Total mesh packets processed                     | Counter   | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_rx_time                            | Packet receive time (seconds since 1970)         | Histogram | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_rx_snr                             | Packet receive SNR                               | Gauge     | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_hop_limit                          | Packet hop limit                                 | Counter   | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_want_ack                           | Want ACK occurrences                             | Counter   | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_via_mqtt                           | MQTT transmission occurrences                    | Counter   | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_hop_start                          | Packet hop start                                 | Gauge     | 🏷️ (source), 🏷️ (destination)            |
| mesh_packet_ids                                | Unique packet IDs                                | Counter   | 🏷️ (source), 🏷️ (destination), packet_id |
| mesh_packet_channel                            | Packet channel                                   | Counter   | 🏷️ (source), 🏷️ (destination), channel   |
| mesh_packet_rx_rssi                            | Packet receive RSSI                              | Gauge     | 🏷️ (source), 🏷️ (destination)            |

## Configuration

The project uses a `.env` file for configuration. Here is an example of the configuration options available:

```dotenv
# Description: Environment variables for the application

# Postgres connection details
DATABASE_URL=postgres://postgres:postgres@postgres:5432/meshtastic

# Prometheus connection details
PROMETHEUS_COLLECTOR_PORT=9464
PROMETHEUS_JOB=example

# MQTT connection details
MQTT_HOST=
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_KEEPALIVE=60
MQTT_TOPIC='msh/israel/#'
MQTT_IS_TLS=false

# Exporter configuration
## Hide source data in the exporter (default: false)
MESH_HIDE_SOURCE_DATA=false
## Hide destination data in the exporter (default: false)
MESH_HIDE_DESTINATION_DATA=false
## Filtered ports in the exporter (default: 1, can be a comma-separated list of ports)
FILTERED_PORTS=0
## Hide message content in the TEXT_MESSAGE_APP packets (default: true) (Currently we only log message length, if we hide then all messages would have the same length)
HIDE_MESSAGE=false
## MQTT server Key for decoding messages
MQTT_SERVER_KEY=1PG7OiApB1nwvP+rz05pAQ==

# MQTT protocol version (default: MQTTv5) the public MQTT server supports MQTTv311
# Options: MQTTv311, MQTTv31, MQTTv5
MQTT_PROTOCOL=MQTTv311

# MQTT callback API version (default: VERSION2) the public MQTT server supports VERSION2
# Options: VERSION1, VERSION2
MQTT_CALLBACK_API_VERSION=VERSION2

```

## Running the Project

To run the project, simply use Docker Compose:

```bash
docker compose up -d
```

This command will build and start all the necessary services, including the exporter, Prometheus server, Postgres
server, and Grafana.

## Grafana Dashboard

The project includes a Grafana dashboard pre-configured to connect to both the Prometheus and Postgres data sources.
This
allows you to start creating and customizing your dashboards right away.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.
