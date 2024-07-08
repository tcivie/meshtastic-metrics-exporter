# Meshtastic Metrics Exporter

The `meshtastic-metrics-exporter` is a tool designed to export nearly all available data from an MQTT server to a
Prometheus server. It comes with a pre-configured Grafana dashboard connected to both data sources, allowing users to
start creating dashboards immediately.

## Features

- Exports a comprehensive set of metrics from an MQTT server to Prometheus.
- Comes with a Grafana dashboard configured to connect to both Prometheus and Postgres data sources.
  - Comes with some basic dashboards, see the section below for general view of the dashboards
- Stores node details (ID, short/long name, hardware details, and client type) in a Postgres server, which is also part of
  the package.
- Configuration via a `.env` file.

### Grafana Dashboards
The project comes wtih 2 dashboards.
#### Main Dashboard
<img width="1514" alt="SCR-20240707-qgnn" src="https://github.com/tcivie/meshtastic-metrics-exporter/assets/87943721/9679c140-c5f7-4ea5-bfc6-0173b52fb28c">

> The dashboard has some basic data about the mesh network and it's data is temporarely updated (With new data coming in it would fill out the missing pieces automatically)

#### User Panel
<img width="1470" alt="SCR-20240707-qhth" src="https://github.com/tcivie/meshtastic-metrics-exporter/assets/87943721/58f15190-127d-4481-b896-1c3e2121dea5">

> This panel can be reached from the "Node ID" link on the main dashboard (The table in the center) or you can go to it from the dashbaords tab in grafana and select the node you want to spectate. This board includes some telemetry data and basic information about the node.

#### The Node Graph
<img width="585" alt="SCR-20240707-qjaj" src="https://github.com/tcivie/meshtastic-metrics-exporter/assets/87943721/d29b2ac4-6291-4095-9938-e6e63df15098">

> Both boards also include node graph which allows you to view nodes which are sending [Neighbour Info packets](https://meshtastic.org/docs/configuration/module/neighbor-info)
> As long as we have some node which is connected to our MQTT server the data would be read buy the exporter and parsed as node graph. The line colors indicate the SNR value and the arrow is the direction of the flow captured (It can be two way). And the node circle color indicates which node is connected to MQTT (Green) which one is disconnected from MQTT (Red) and unknown (Gray - Never connected to the MQTT server)

**I highly recomend giving the system to stabilize over 24 hours before seeking any useful information from it.**

## Exported Metrics

🏷️ Common Labels: `node_id, short_name, long_name, hardware_model, role`

Label Notation:
- 🏷️: Indicates that all common labels are used.
- 🏷️ (source): Indicates that all common labels are used, prefixed with "source_" (e.g., source_node_id, source_short_name, etc.).
- 🏷️ (destination): Indicates that all common labels are used, prefixed with "destination_" (e.g., destination_node_id, destination_short_name, etc.).

The following is a list of metrics exported by the `meshtastic-metrics-exporter`:

| Metric Name                       | Description                                                                  | Type      | Labels                               |
|-----------------------------------|------------------------------------------------------------------------------|-----------|--------------------------------------|
| text_message_app_length           | Length of text messages processed by the app                                 | Histogram | 🏷️                                   |
| device_latitude                   | Device latitude                                                              | Gauge     | 🏷️                                   |
| device_longitude                  | Device longitude                                                             | Gauge     | 🏷️                                   |
| device_altitude                   | Device altitude                                                              | Gauge     | 🏷️                                   |
| device_position_precision         | Device position precision                                                    | Gauge     | 🏷️                                   |
| telemetry_app_ch1_voltage         | Voltage measured by the device on channel 1                                  | Gauge     | 🏷️                                   |
| telemetry_app_ch1_current         | Current measured by the device on channel 1                                  | Gauge     | 🏷️                                   |
| telemetry_app_ch2_voltage         | Voltage measured by the device on channel 2                                  | Gauge     | 🏷️                                   |
| telemetry_app_ch2_current         | Current measured by the device on channel 2                                  | Gauge     | 🏷️                                   |
| telemetry_app_ch3_voltage         | Voltage measured by the device on channel 3                                  | Gauge     | 🏷️                                   |
| telemetry_app_ch3_current         | Current measured by the device on channel 3                                  | Gauge     | 🏷️                                   |
| telemetry_app_pm10_standard       | Concentration Units Standard PM1.0                                           | Gauge     | 🏷️                                   |
| telemetry_app_pm25_standard       | Concentration Units Standard PM2.5                                           | Gauge     | 🏷️                                   |
| telemetry_app_pm100_standard      | Concentration Units Standard PM10.0                                          | Gauge     | 🏷️                                   |
| telemetry_app_pm10_environmental  | Concentration Units Environmental PM1.0                                      | Gauge     | 🏷️                                   |
| telemetry_app_pm25_environmental  | Concentration Units Environmental PM2.5                                      | Gauge     | 🏷️                                   |
| telemetry_app_pm100_environmental | Concentration Units Environmental PM10.0                                     | Gauge     | 🏷️                                   |
| telemetry_app_particles_03um      | 0.3um Particle Count                                                         | Gauge     | 🏷️                                   |
| telemetry_app_particles_05um      | 0.5um Particle Count                                                         | Gauge     | 🏷️                                   |
| telemetry_app_particles_10um      | 1.0um Particle Count                                                         | Gauge     | 🏷️                                   |
| telemetry_app_particles_25um      | 2.5um Particle Count                                                         | Gauge     | 🏷️                                   |
| telemetry_app_particles_50um      | 5.0um Particle Count                                                         | Gauge     | 🏷️                                   |
| telemetry_app_particles_100um     | 10.0um Particle Count                                                        | Gauge     | 🏷️                                   |
| telemetry_app_temperature         | Temperature measured by the device                                           | Gauge     | 🏷️                                   |
| telemetry_app_relative_humidity   | Relative humidity percent measured by the device                             | Gauge     | 🏷️                                   |
| telemetry_app_barometric_pressure | Barometric pressure in hPA measured by the device                            | Gauge     | 🏷️                                   |
| telemetry_app_gas_resistance      | Gas resistance in MOhm measured by the device                                | Gauge     | 🏷️                                   |
| telemetry_app_iaq                 | IAQ value measured by the device (0-500)                                     | Gauge     | 🏷️                                   |
| telemetry_app_distance            | Distance measured by the device in mm                                        | Gauge     | 🏷️                                   |
| telemetry_app_lux                 | Ambient light measured by the device in Lux                                  | Gauge     | 🏷️                                   |
| telemetry_app_white_lux           | White light measured by the device in Lux                                    | Gauge     | 🏷️                                   |
| telemetry_app_ir_lux              | Infrared light measured by the device in Lux                                 | Gauge     | 🏷️                                   |
| telemetry_app_uv_lux              | Ultraviolet light measured by the device in Lux                              | Gauge     | 🏷️                                   |
| telemetry_app_wind_direction      | Wind direction in degrees measured by the device                             | Gauge     | 🏷️                                   |
| telemetry_app_wind_speed          | Wind speed in m/s measured by the device                                     | Gauge     | 🏷️                                   |
| telemetry_app_weight              | Weight in KG measured by the device                                          | Gauge     | 🏷️                                   |
| telemetry_app_battery_level       | Battery level of the device (0-100, >100 means powered)                      | Gauge     | 🏷️                                   |
| telemetry_app_voltage             | Voltage measured by the device                                               | Gauge     | 🏷️                                   |
| telemetry_app_channel_utilization | Utilization for the current channel, including well-formed TX, RX, and noise | Gauge     | 🏷️                                   |
| telemetry_app_air_util_tx         | Percent of airtime for transmission used within the last hour                | Gauge     | 🏷️                                   |
| telemetry_app_uptime_seconds      | How long the device has been running since the last reboot (in seconds)      | Counter   | 🏷️                                   |
| route_length                      | Number of nodes in the route                                                 | Counter   | 🏷️                                   |
| route_response                    | Number of responses to route discovery                                       | Counter   | 🏷️, response_type                    |
| mesh_packet_source_types          | Types of mesh packets processed by source                                    | Counter   | 🏷️ (source), portnum                 |
| mesh_packet_destination_types     | Types of mesh packets processed by destination                               | Counter   | 🏷️ (destination), portnum            |
| mesh_packet_total                 | Total number of mesh packets processed                                       | Counter   | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_rx_time               | Receive time of mesh packets (seconds since 1970)                            | Histogram | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_rx_snr                | Receive SNR of mesh packets                                                  | Gauge     | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_hop_limit             | Hop limit of mesh packets                                                    | Counter   | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_want_ack              | Occurrences of want ACK for mesh packets                                     | Counter   | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_via_mqtt              | Occurrences of mesh packets sent via MQTT                                    | Counter   | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_hop_start             | Hop start of mesh packets                                                    | Gauge     | 🏷️ (source), 🏷️ (destination)        |
| mesh_packet_ids                   | Unique IDs for mesh packets                                                  | Counter   | 🏷️ (source), 🏷️ (destination), packet_id |
| mesh_packet_channel               | Channel used for mesh packets                                                | Counter   | 🏷️ (source), 🏷️ (destination), channel |
| mesh_packet_rx_rssi               | Receive RSSI of mesh packets                                                 | Gauge     | 🏷️ (source), 🏷️ (destination)        |

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
docker-compose up --build
```

This command will build and start all the necessary services, including the exporter, Prometheus server, Postgres
server, and Grafana.

## Grafana Dashboard

The project includes a Grafana dashboard pre-configured to connect to both the Prometheus and Postgres data sources.
This
allows you to start creating and customizing your dashboards right away.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.
