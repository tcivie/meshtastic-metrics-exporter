-- Meshtastic Metrics Exporter — TimescaleDB schema
--
-- Design notes:
--   * One hypertable per metric family (device / environment / air_quality /
--     power / pax_counter / mesh_packet).  All partition on `time`.
--   * `node_details`, `node_neighbors`, `node_configurations`, `messages` stay
--     plain tables — they are slowly-changing state, not time-series.
--   * No per-row triggers on hypertables. Anything that needs to react to new
--     rows runs as a TimescaleDB scheduled job (`add_job`) instead.
--   * Idempotent: every CREATE/ALTER uses IF NOT EXISTS / if_not_exists, so
--     re-running the file on an existing volume is safe.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- State tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS node_details
(
    node_id        VARCHAR PRIMARY KEY,
    short_name     VARCHAR,
    long_name      VARCHAR,
    hardware_model VARCHAR,
    role           VARCHAR,
    mqtt_status    VARCHAR   DEFAULT 'none',
    longitude      INT,
    latitude       INT,
    altitude       INT,
    precision      INT,
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_node_neighbor
    ON node_neighbors (node_id, neighbor_id);

CREATE TABLE IF NOT EXISTS node_configurations
(
    node_id                           VARCHAR PRIMARY KEY,
    last_updated                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    environment_update_interval       INTERVAL  DEFAULT '0 seconds' NOT NULL,
    environment_update_last_timestamp TIMESTAMP DEFAULT NOW(),

    device_update_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    device_update_last_timestamp      TIMESTAMP DEFAULT NOW(),

    air_quality_update_interval       INTERVAL  DEFAULT '0 seconds' NOT NULL,
    air_quality_update_last_timestamp TIMESTAMP DEFAULT NOW(),

    power_update_interval             INTERVAL  DEFAULT '0 seconds' NOT NULL,
    power_update_last_timestamp       TIMESTAMP DEFAULT NOW(),

    range_test_interval               INTERVAL  DEFAULT '0 seconds' NOT NULL,
    range_test_packets_total          INT       DEFAULT 0,
    range_test_first_packet_timestamp TIMESTAMP DEFAULT NOW(),
    range_test_last_packet_timestamp  TIMESTAMP DEFAULT NOW(),

    pax_counter_interval              INTERVAL  DEFAULT '0 seconds' NOT NULL,
    pax_counter_last_timestamp        TIMESTAMP DEFAULT NOW(),

    neighbor_info_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    neighbor_info_last_timestamp      TIMESTAMP DEFAULT NOW(),

    mqtt_encryption_enabled           BOOLEAN   DEFAULT FALSE,
    mqtt_json_enabled                 BOOLEAN   DEFAULT FALSE,
    mqtt_json_message_timestamp       TIMESTAMP DEFAULT NOW(),

    mqtt_configured_root_topic        TEXT      DEFAULT '',
    mqtt_info_last_timestamp          TIMESTAMP DEFAULT NOW(),

    map_broadcast_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    map_broadcast_last_timestamp      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages
(
    id          TEXT PRIMARY KEY,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_received_at ON messages (received_at);

-- ---------------------------------------------------------------------------
-- Hypertables (time-series)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS device_metrics
(
    time                TIMESTAMPTZ NOT NULL,
    node_id             VARCHAR     NOT NULL,
    battery_level       FLOAT,
    voltage             FLOAT,
    channel_utilization FLOAT,
    air_util_tx         FLOAT,
    uptime_seconds      BIGINT
);

CREATE TABLE IF NOT EXISTS environment_metrics
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
    weight              FLOAT
);

CREATE TABLE IF NOT EXISTS air_quality_metrics
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
    particles_100um     FLOAT
);

CREATE TABLE IF NOT EXISTS power_metrics
(
    time        TIMESTAMPTZ NOT NULL,
    node_id     VARCHAR     NOT NULL,
    ch1_voltage FLOAT,
    ch1_current FLOAT,
    ch2_voltage FLOAT,
    ch2_current FLOAT,
    ch3_voltage FLOAT,
    ch3_current FLOAT
);

CREATE TABLE IF NOT EXISTS pax_counter_metrics
(
    time          TIMESTAMPTZ NOT NULL,
    node_id       VARCHAR     NOT NULL,
    wifi_stations BIGINT,
    ble_beacons   BIGINT,
    uptime        BIGINT
);

-- For older volumes that already have pax_counter_metrics without uptime.
ALTER TABLE pax_counter_metrics ADD COLUMN IF NOT EXISTS uptime BIGINT;

CREATE TABLE IF NOT EXISTS mesh_packet_metrics
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
    message_size_bytes INT
);

-- Convert each metric table to a hypertable. `if_not_exists => true` makes
-- this a no-op when re-run.  Chunk interval is 1 day — mesh-radio data is
-- low volume; bigger chunks would waste memory on indexes.
SELECT create_hypertable('device_metrics',     'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);
SELECT create_hypertable('environment_metrics','time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);
SELECT create_hypertable('air_quality_metrics','time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);
SELECT create_hypertable('power_metrics',      'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);
SELECT create_hypertable('pax_counter_metrics','time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);
SELECT create_hypertable('mesh_packet_metrics','time', chunk_time_interval => INTERVAL '1 day', if_not_exists => true);

CREATE INDEX IF NOT EXISTS idx_device_metrics_node_id      ON device_metrics      (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_environment_metrics_node_id ON environment_metrics (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_air_quality_metrics_node_id ON air_quality_metrics (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_power_metrics_node_id       ON power_metrics       (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_pax_counter_metrics_node_id ON pax_counter_metrics (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_mesh_packet_metrics_source  ON mesh_packet_metrics (source_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_mesh_packet_metrics_dest    ON mesh_packet_metrics (destination_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_mesh_packet_metrics_portnum ON mesh_packet_metrics (portnum, time DESC);

-- ---------------------------------------------------------------------------
-- Columnstore (compression).  Segment by the entity each query filters on
-- and order by time DESC — the standard time-series shape.
-- Chunks older than 14 days get compressed (~10x size reduction); chunks
-- older than 30 days get dropped by the retention policy below.
-- ---------------------------------------------------------------------------

ALTER TABLE device_metrics      SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'node_id',     timescaledb.orderby = 'time DESC');
ALTER TABLE environment_metrics SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'node_id',     timescaledb.orderby = 'time DESC');
ALTER TABLE air_quality_metrics SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'node_id',     timescaledb.orderby = 'time DESC');
ALTER TABLE power_metrics       SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'node_id',     timescaledb.orderby = 'time DESC');
ALTER TABLE pax_counter_metrics SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'node_id',     timescaledb.orderby = 'time DESC');
ALTER TABLE mesh_packet_metrics SET (timescaledb.enable_columnstore = true, timescaledb.segmentby = 'source_id',   timescaledb.orderby = 'time DESC');

-- Columnstore (compression) policies. `add_columnstore_policy` is a
-- procedure, so it must be CALLed at the top level — table name has to be
-- a literal regclass, hence the unrolled list.  `if_not_exists => true`
-- makes re-runs a no-op.
CALL add_columnstore_policy('device_metrics',      after => INTERVAL '14 days', if_not_exists => true);
CALL add_columnstore_policy('environment_metrics', after => INTERVAL '14 days', if_not_exists => true);
CALL add_columnstore_policy('air_quality_metrics', after => INTERVAL '14 days', if_not_exists => true);
CALL add_columnstore_policy('power_metrics',       after => INTERVAL '14 days', if_not_exists => true);
CALL add_columnstore_policy('pax_counter_metrics', after => INTERVAL '14 days', if_not_exists => true);
CALL add_columnstore_policy('mesh_packet_metrics', after => INTERVAL '14 days', if_not_exists => true);

-- Retention policies (drop chunks older than 30 days).  Function form
-- supports `if_not_exists => true` for idempotent re-runs.
SELECT add_retention_policy('device_metrics',      INTERVAL '30 days', if_not_exists => true);
SELECT add_retention_policy('environment_metrics', INTERVAL '30 days', if_not_exists => true);
SELECT add_retention_policy('air_quality_metrics', INTERVAL '30 days', if_not_exists => true);
SELECT add_retention_policy('power_metrics',       INTERVAL '30 days', if_not_exists => true);
SELECT add_retention_policy('pax_counter_metrics', INTERVAL '30 days', if_not_exists => true);
SELECT add_retention_policy('mesh_packet_metrics', INTERVAL '30 days', if_not_exists => true);

-- ---------------------------------------------------------------------------
-- node_configurations maintenance
--
-- Old design used per-row AFTER INSERT triggers on every hypertable to keep
-- node_configurations.<x>_update_last_timestamp current.  Triggers on
-- hypertables defeat batched inserts, so we replace them with a single
-- periodic job that recomputes both the timestamps and the intervals.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION refresh_node_configurations()
    RETURNS VOID AS
$$
BEGIN
    -- Make sure every observed node has a configurations row.
    INSERT INTO node_configurations (node_id)
    SELECT node_id FROM node_details
    ON CONFLICT (node_id) DO NOTHING;

    -- Latest-seen timestamps per metric family.
    UPDATE node_configurations nc
    SET device_update_last_timestamp = sub.max_time
    FROM (SELECT node_id, MAX(time) AS max_time FROM device_metrics GROUP BY node_id) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET environment_update_last_timestamp = sub.max_time
    FROM (SELECT node_id, MAX(time) AS max_time FROM environment_metrics GROUP BY node_id) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET air_quality_update_last_timestamp = sub.max_time
    FROM (SELECT node_id, MAX(time) AS max_time FROM air_quality_metrics GROUP BY node_id) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET power_update_last_timestamp = sub.max_time
    FROM (SELECT node_id, MAX(time) AS max_time FROM power_metrics GROUP BY node_id) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET pax_counter_last_timestamp = sub.max_time
    FROM (SELECT node_id, MAX(time) AS max_time FROM pax_counter_metrics GROUP BY node_id) sub
    WHERE nc.node_id = sub.node_id;

    -- Average inter-arrival interval per node, family.
    UPDATE node_configurations nc
    SET device_update_interval = sub.avg_interval
    FROM (
        SELECT node_id,
               CASE WHEN COUNT(time) > 1 THEN (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                    ELSE INTERVAL '0 seconds' END AS avg_interval
        FROM device_metrics GROUP BY node_id
    ) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET environment_update_interval = sub.avg_interval
    FROM (
        SELECT node_id,
               CASE WHEN COUNT(time) > 1 THEN (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                    ELSE INTERVAL '0 seconds' END AS avg_interval
        FROM environment_metrics GROUP BY node_id
    ) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET air_quality_update_interval = sub.avg_interval
    FROM (
        SELECT node_id,
               CASE WHEN COUNT(time) > 1 THEN (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                    ELSE INTERVAL '0 seconds' END AS avg_interval
        FROM air_quality_metrics GROUP BY node_id
    ) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET power_update_interval = sub.avg_interval
    FROM (
        SELECT node_id,
               CASE WHEN COUNT(time) > 1 THEN (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                    ELSE INTERVAL '0 seconds' END AS avg_interval
        FROM power_metrics GROUP BY node_id
    ) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations nc
    SET pax_counter_interval = sub.avg_interval
    FROM (
        SELECT node_id,
               CASE WHEN COUNT(time) > 1 THEN (MAX(time) - MIN(time)) / (COUNT(time) - 1)
                    ELSE INTERVAL '0 seconds' END AS avg_interval
        FROM pax_counter_metrics GROUP BY node_id
    ) sub
    WHERE nc.node_id = sub.node_id;

    UPDATE node_configurations
    SET last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE PROCEDURE refresh_node_configurations_job(job_id int, config jsonb)
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM refresh_node_configurations();
END;
$$;

-- Drop the old per-row triggers if a previous schema is being upgraded.
DROP TRIGGER IF EXISTS trigger_device_metrics_insert      ON device_metrics;
DROP TRIGGER IF EXISTS trigger_environment_metrics_insert ON environment_metrics;
DROP TRIGGER IF EXISTS trigger_air_quality_metrics_insert ON air_quality_metrics;
DROP TRIGGER IF EXISTS trigger_power_metrics_insert       ON power_metrics;
DROP TRIGGER IF EXISTS trigger_pax_counter_metrics_insert ON pax_counter_metrics;
DROP TRIGGER IF EXISTS trigger_expire_old_messages        ON messages;
DROP FUNCTION IF EXISTS update_node_configurations();
DROP FUNCTION IF EXISTS expire_old_messages();
DROP FUNCTION IF EXISTS calculate_update_intervals();
DROP PROCEDURE IF EXISTS calculate_update_intervals_job(int, jsonb);

-- Schedule the refresh job hourly.  Idempotent: add_job throws if the same
-- name already exists.
DO $$
BEGIN
    PERFORM add_job(
        proc => 'refresh_node_configurations_job',
        schedule_interval => INTERVAL '1 hour',
        job_name => 'refresh_node_configurations_hourly'
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'refresh_node_configurations job: %', SQLERRM;
END $$;

-- Also schedule cleanup of the dedup `messages` table.  Replaces the
-- per-row trigger that DELETEd on every INSERT.
CREATE OR REPLACE PROCEDURE messages_cleanup_job(job_id int, config jsonb)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM messages WHERE received_at < NOW() - INTERVAL '5 minutes';
END;
$$;

DO $$
BEGIN
    PERFORM add_job(
        proc => 'messages_cleanup_job',
        schedule_interval => INTERVAL '1 minute',
        job_name => 'messages_cleanup_minutely'
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'messages_cleanup job: %', SQLERRM;
END $$;

-- ---------------------------------------------------------------------------
-- Convenience view used by db_handler.get_latest_metrics().
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW node_telemetry AS
SELECT d.node_id,
       d.short_name,
       d.long_name,
       d.hardware_model,
       d.role,
       dm.time AS device_time,
       dm.battery_level,
       dm.voltage,
       dm.channel_utilization,
       dm.air_util_tx,
       dm.uptime_seconds,
       em.time AS environment_time,
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
       aq.time AS air_quality_time,
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
       pm.time AS power_time,
       pm.ch1_voltage,
       pm.ch1_current,
       pm.ch2_voltage,
       pm.ch2_current,
       pm.ch3_voltage,
       pm.ch3_current
FROM node_details d
LEFT JOIN LATERAL (SELECT * FROM device_metrics      WHERE node_id = d.node_id ORDER BY time DESC LIMIT 1) dm ON true
LEFT JOIN LATERAL (SELECT * FROM environment_metrics WHERE node_id = d.node_id ORDER BY time DESC LIMIT 1) em ON true
LEFT JOIN LATERAL (SELECT * FROM air_quality_metrics WHERE node_id = d.node_id ORDER BY time DESC LIMIT 1) aq ON true
LEFT JOIN LATERAL (SELECT * FROM power_metrics       WHERE node_id = d.node_id ORDER BY time DESC LIMIT 1) pm ON true;

-- Run once at init so the configurations side-table reflects any data that
-- may already be present.
SELECT refresh_node_configurations();
