-- Initialize TimescaleDB for Meshtastic Metrics Exporter

-- Create extension if it doesn't exist
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create tables that were previously in PostgreSQL
CREATE TABLE IF NOT EXISTS messages
(
    id          TEXT PRIMARY KEY,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION expire_old_messages()
    RETURNS TRIGGER AS
$$
BEGIN
    DELETE FROM messages WHERE received_at < NOW() - INTERVAL '1 minute';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_expire_old_messages
    AFTER INSERT
    ON messages
    FOR EACH ROW
EXECUTE FUNCTION expire_old_messages();

CREATE TABLE IF NOT EXISTS node_details
(
    node_id        VARCHAR PRIMARY KEY,
    -- Base Data
    short_name     VARCHAR,
    long_name      VARCHAR,
    hardware_model VARCHAR,
    role           VARCHAR,
    mqtt_status    VARCHAR   default 'none',
    -- Location Data
    longitude      INT,
    latitude       INT,
    altitude       INT,
    precision      INT,
    -- SQL Data
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS node_neighbors
(
    id          SERIAL PRIMARY KEY,
    node_id     VARCHAR,
    neighbor_id VARCHAR,
    snr         FLOAT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id),
    FOREIGN KEY (neighbor_id) REFERENCES node_details (node_id),
    UNIQUE (node_id, neighbor_id)
);

CREATE UNIQUE INDEX idx_unique_node_neighbor ON node_neighbors (node_id, neighbor_id);

-- Create a table for node_configurations
CREATE TABLE IF NOT EXISTS node_configurations
(
    node_id                           VARCHAR PRIMARY KEY,
    last_updated                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Configuration (Telemetry)
    environment_update_interval       INTERVAL  DEFAULT '0 seconds' NOT NULL,
    environment_update_last_timestamp TIMESTAMP DEFAULT NOW(),

    device_update_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    device_update_last_timestamp      TIMESTAMP DEFAULT NOW(),

    air_quality_update_interval       INTERVAL  DEFAULT '0 seconds' NOT NULL,
    air_quality_update_last_timestamp TIMESTAMP DEFAULT NOW(),

    power_update_interval             INTERVAL  DEFAULT '0 seconds' NOT NULL,
    power_update_last_timestamp       TIMESTAMP DEFAULT NOW(),

    -- Configuration (Range Test)
    range_test_interval               INTERVAL  DEFAULT '0 seconds' NOT NULL,
    range_test_packets_total          INT       DEFAULT 0, -- in packets
    range_test_first_packet_timestamp TIMESTAMP DEFAULT NOW(),
    range_test_last_packet_timestamp  TIMESTAMP DEFAULT NOW(),

    -- Configuration (PAX Counter)
    pax_counter_interval              INTERVAL  DEFAULT '0 seconds' NOT NULL,
    pax_counter_last_timestamp        TIMESTAMP DEFAULT NOW(),

    -- Configuration (Neighbor Info)
    neighbor_info_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    neighbor_info_last_timestamp      TIMESTAMP DEFAULT NOW(),

    -- Configuration (MQTT)
    mqtt_encryption_enabled           BOOLEAN   DEFAULT FALSE,
    mqtt_json_enabled                 BOOLEAN   DEFAULT FALSE,
    mqtt_json_message_timestamp       TIMESTAMP DEFAULT NOW(),

    mqtt_configured_root_topic        TEXT      DEFAULT '',
    mqtt_info_last_timestamp          TIMESTAMP DEFAULT NOW(),

    -- Configuration (Map)
    map_broadcast_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    map_broadcast_last_timestamp      TIMESTAMP DEFAULT NOW(),

    UNIQUE (node_id)
);

-- Create hypertables for time-series data

-- Device metrics
CREATE TABLE device_metrics
(
    time                TIMESTAMPTZ NOT NULL,
    node_id             VARCHAR     NOT NULL,
    battery_level       FLOAT,
    voltage             FLOAT,
    channel_utilization FLOAT,
    air_util_tx         FLOAT,
    uptime_seconds      BIGINT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('device_metrics', 'time');
CREATE INDEX idx_device_metrics_node_id ON device_metrics (node_id, time DESC);

-- Environment metrics
CREATE TABLE environment_metrics
(
    time                TIMESTAMPTZ NOT NULL,
    node_id             VARCHAR     NOT NULL,
    temperature         FLOAT,
    relative_humidity   FLOAT,
    barometric_pressure FLOAT,
    gas_resistance      FLOAT,
    iaq                 FLOAT,
    distance            FLOAT,
    lux                 FLOAT,
    white_lux           FLOAT,
    ir_lux              FLOAT,
    uv_lux              FLOAT,
    wind_direction      FLOAT,
    wind_speed          FLOAT,
    weight              FLOAT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('environment_metrics', 'time');
CREATE INDEX idx_environment_metrics_node_id ON environment_metrics (node_id, time DESC);

-- Air quality metrics
CREATE TABLE air_quality_metrics
(
    time                TIMESTAMPTZ NOT NULL,
    node_id             VARCHAR     NOT NULL,
    pm10_standard       FLOAT,
    pm25_standard       FLOAT,
    pm100_standard      FLOAT,
    pm10_environmental  FLOAT,
    pm25_environmental  FLOAT,
    pm100_environmental FLOAT,
    particles_03um      FLOAT,
    particles_05um      FLOAT,
    particles_10um      FLOAT,
    particles_25um      FLOAT,
    particles_50um      FLOAT,
    particles_100um     FLOAT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('air_quality_metrics', 'time');
CREATE INDEX idx_air_quality_metrics_node_id ON air_quality_metrics (node_id, time DESC);

-- Power metrics
CREATE TABLE power_metrics
(
    time        TIMESTAMPTZ NOT NULL,
    node_id     VARCHAR     NOT NULL,
    ch1_voltage FLOAT,
    ch1_current FLOAT,
    ch2_voltage FLOAT,
    ch2_current FLOAT,
    ch3_voltage FLOAT,
    ch3_current FLOAT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('power_metrics', 'time');
CREATE INDEX idx_power_metrics_node_id ON power_metrics (node_id, time DESC);

-- PAX counter metrics
CREATE TABLE pax_counter_metrics
(
    time          TIMESTAMPTZ NOT NULL,
    node_id       VARCHAR     NOT NULL,
    wifi_stations BIGINT,
    ble_beacons   BIGINT,
    FOREIGN KEY (node_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('pax_counter_metrics', 'time');
CREATE INDEX idx_pax_counter_metrics_node_id ON pax_counter_metrics (node_id, time DESC);

-- Mesh packet metrics
CREATE TABLE mesh_packet_metrics
(
    time               TIMESTAMPTZ NOT NULL,
    source_id          VARCHAR     NOT NULL,
    destination_id     VARCHAR     NOT NULL,
    portnum            VARCHAR,
    packet_id          BIGINT,
    channel            INT,
    rx_time            BIGINT,
    rx_snr             FLOAT,
    rx_rssi            FLOAT,
    hop_limit          INT,
    hop_start          INT,
    want_ack           BOOLEAN,
    via_mqtt           BOOLEAN,
    message_size_bytes INT,
    FOREIGN KEY (source_id) REFERENCES node_details (node_id),
    FOREIGN KEY (destination_id) REFERENCES node_details (node_id)
);

SELECT create_hypertable('mesh_packet_metrics', 'time');
CREATE INDEX idx_mesh_packet_metrics_source ON mesh_packet_metrics (source_id, time DESC);
CREATE INDEX idx_mesh_packet_metrics_dest ON mesh_packet_metrics (destination_id, time DESC);

-- Create a function to update node_configurations from metrics tables
CREATE OR REPLACE FUNCTION update_node_configurations()
    RETURNS TRIGGER AS
$$
BEGIN
    -- Insert node_id into node_configurations if it doesn't exist
    INSERT INTO node_configurations (node_id)
    VALUES (NEW.node_id)
    ON CONFLICT (node_id) DO NOTHING;

    -- Update the last_updated timestamp
    UPDATE node_configurations
    SET last_updated = NOW()
    WHERE node_id = NEW.node_id;

    -- Update the specific metric timestamp based on the table that triggered this function
    IF TG_TABLE_NAME = 'device_metrics' THEN
        UPDATE node_configurations
        SET device_update_last_timestamp = NEW.time
        WHERE node_id = NEW.node_id;
    ELSIF TG_TABLE_NAME = 'environment_metrics' THEN
        UPDATE node_configurations
        SET environment_update_last_timestamp = NEW.time
        WHERE node_id = NEW.node_id;
    ELSIF TG_TABLE_NAME = 'air_quality_metrics' THEN
        UPDATE node_configurations
        SET air_quality_update_last_timestamp = NEW.time
        WHERE node_id = NEW.node_id;
    ELSIF TG_TABLE_NAME = 'power_metrics' THEN
        UPDATE node_configurations
        SET power_update_last_timestamp = NEW.time
        WHERE node_id = NEW.node_id;
    ELSIF TG_TABLE_NAME = 'pax_counter_metrics' THEN
        UPDATE node_configurations
        SET pax_counter_last_timestamp = NEW.time
        WHERE node_id = NEW.node_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a function to calculate update intervals
CREATE OR REPLACE FUNCTION calculate_update_intervals()
    RETURNS VOID AS
$$
BEGIN
    -- Update device_update_interval
    UPDATE node_configurations nc
    SET device_update_interval =
            COALESCE(
                    (SELECT CASE
                                WHEN COUNT(time) > 1 THEN
                                    (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                                ELSE
                                    INTERVAL '0 seconds'
                                END
                     FROM device_metrics
                     WHERE node_id = nc.node_id),
                    INTERVAL '0 seconds'
            );

    -- Update environment_update_interval
    UPDATE node_configurations nc
    SET environment_update_interval =
            COALESCE(
                    (SELECT CASE
                                WHEN COUNT(time) > 1 THEN
                                    (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                                ELSE
                                    INTERVAL '0 seconds'
                                END
                     FROM environment_metrics
                     WHERE node_id = nc.node_id),
                    INTERVAL '0 seconds'
            );

    -- Update air_quality_update_interval
    UPDATE node_configurations nc
    SET air_quality_update_interval =
            COALESCE(
                    (SELECT CASE
                                WHEN COUNT(time) > 1 THEN
                                    (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                                ELSE
                                    INTERVAL '0 seconds'
                                END
                     FROM air_quality_metrics
                     WHERE node_id = nc.node_id),
                    INTERVAL '0 seconds'
            );

    -- Update power_update_interval
    UPDATE node_configurations nc
    SET power_update_interval =
            COALESCE(
                    (SELECT CASE
                                WHEN COUNT(time) > 1 THEN
                                    (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                                ELSE
                                    INTERVAL '0 seconds'
                                END
                     FROM power_metrics
                     WHERE node_id = nc.node_id),
                    INTERVAL '0 seconds'
            );

    -- Update pax_counter_interval
    UPDATE node_configurations nc
    SET pax_counter_interval =
            COALESCE(
                    (SELECT CASE
                                WHEN COUNT(time) > 1 THEN
                                    (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                                ELSE
                                    INTERVAL '0 seconds'
                                END
                     FROM pax_counter_metrics
                     WHERE node_id = nc.node_id),
                    INTERVAL '0 seconds'
            );
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to calculate update intervals every hour
-- Note: This requires the pg_cron extension, which may not be available in all PostgreSQL installations
-- If pg_cron is not available, you can manually run the calculate_update_intervals() function periodically
DO
$$
    BEGIN
        IF EXISTS (SELECT 1
                   FROM pg_available_extensions
                   WHERE name = 'pg_cron') THEN
            EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_cron';
            EXECUTE 'SELECT cron.schedule(''0 * * * *'', ''SELECT calculate_update_intervals()'')';
        ELSE
            RAISE NOTICE 'pg_cron extension is not available. You will need to run the calculate_update_intervals() function manually or set up an external scheduler.';
        END IF;
    END
$$;

-- Create triggers to update node_configurations when metrics are inserted
CREATE TRIGGER trigger_device_metrics_insert
    AFTER INSERT
    ON device_metrics
    FOR EACH ROW
EXECUTE FUNCTION update_node_configurations();

CREATE TRIGGER trigger_environment_metrics_insert
    AFTER INSERT
    ON environment_metrics
    FOR EACH ROW
EXECUTE FUNCTION update_node_configurations();

CREATE TRIGGER trigger_air_quality_metrics_insert
    AFTER INSERT
    ON air_quality_metrics
    FOR EACH ROW
EXECUTE FUNCTION update_node_configurations();

CREATE TRIGGER trigger_power_metrics_insert
    AFTER INSERT
    ON power_metrics
    FOR EACH ROW
EXECUTE FUNCTION update_node_configurations();

CREATE TRIGGER trigger_pax_counter_metrics_insert
    AFTER INSERT
    ON pax_counter_metrics
    FOR EACH ROW
EXECUTE FUNCTION update_node_configurations();

-- Set up retention policies (default: 30 days)
SELECT add_retention_policy('device_metrics', INTERVAL '30 days');
SELECT add_retention_policy('environment_metrics', INTERVAL '30 days');
SELECT add_retention_policy('air_quality_metrics', INTERVAL '30 days');
SELECT add_retention_policy('power_metrics', INTERVAL '30 days');
SELECT add_retention_policy('pax_counter_metrics', INTERVAL '30 days');
SELECT add_retention_policy('mesh_packet_metrics', INTERVAL '30 days');

-- Create views for easier querying
CREATE OR REPLACE VIEW node_telemetry AS
SELECT d.node_id,
       d.short_name,
       d.long_name,
       d.hardware_model,
       d.role,
       dm.time as device_time,
       dm.battery_level,
       dm.voltage,
       dm.channel_utilization,
       dm.air_util_tx,
       dm.uptime_seconds,
       em.time as environment_time,
       em.temperature,
       em.relative_humidity,
       em.barometric_pressure,
       em.gas_resistance,
       em.iaq,
       em.distance,
       em.lux,
       em.white_lux,
       em.ir_lux,
       em.uv_lux,
       em.wind_direction,
       em.wind_speed,
       em.weight,
       aq.time as air_quality_time,
       aq.pm10_standard,
       aq.pm25_standard,
       aq.pm100_standard,
       aq.pm10_environmental,
       aq.pm25_environmental,
       aq.pm100_environmental,
       aq.particles_03um,
       aq.particles_05um,
       aq.particles_10um,
       aq.particles_25um,
       aq.particles_50um,
       aq.particles_100um,
       pm.time as power_time,
       pm.ch1_voltage,
       pm.ch1_current,
       pm.ch2_voltage,
       pm.ch2_current,
       pm.ch3_voltage,
       pm.ch3_current
FROM node_details d
         LEFT JOIN LATERAL (
    SELECT *
    FROM device_metrics
    WHERE node_id = d.node_id
    ORDER BY time DESC
    LIMIT 1
    ) dm ON true
         LEFT JOIN LATERAL (
    SELECT *
    FROM environment_metrics
    WHERE node_id = d.node_id
    ORDER BY time DESC
    LIMIT 1
    ) em ON true
         LEFT JOIN LATERAL (
    SELECT *
    FROM air_quality_metrics
    WHERE node_id = d.node_id
    ORDER BY time DESC
    LIMIT 1
    ) aq ON true
         LEFT JOIN LATERAL (
    SELECT *
    FROM power_metrics
    WHERE node_id = d.node_id
    ORDER BY time DESC
    LIMIT 1
    ) pm ON true;

-- Initialize node_configurations table with existing node_ids from node_details
INSERT INTO node_configurations (node_id)
SELECT node_id
FROM node_details
ON CONFLICT (node_id) DO NOTHING;

-- Calculate initial update intervals
SELECT calculate_update_intervals();
