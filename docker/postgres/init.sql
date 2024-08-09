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
--     Base Data
    short_name     VARCHAR,
    long_name      VARCHAR,
    hardware_model VARCHAR,
    role        VARCHAR,
    mqtt_status VARCHAR   default 'none',
--     Location Data
    longitude INT,
    latitude  INT,
    altitude  INT,
    precision INT,
--     SQL Data
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
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
    mqtt_configured_root_topic        TEXT      DEFAULT '',
    mqtt_info_last_timestamp          TIMESTAMP DEFAULT NOW(),

    -- Configuration (Map)
    map_broadcast_interval            INTERVAL  DEFAULT '0 seconds' NOT NULL,
    map_broadcast_last_timestamp      TIMESTAMP DEFAULT NOW(),

--     FOREIGN KEY (node_id) REFERENCES node_details (node_id),
    UNIQUE (node_id)
);

-- -- Function to update old values
-- CREATE OR REPLACE FUNCTION update_old_node_configurations()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     -- Update intervals to 0 if not updated in 24 hours
--     IF NEW.environment_update_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.environment_update_interval := '0 seconds';
--     END IF;
--
--     IF NEW.device_update_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.device_update_interval := '0 seconds';
--     END IF;
--
--     IF NEW.air_quality_update_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.air_quality_update_interval := '0 seconds';
--     END IF;
--
--     IF NEW.power_update_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.power_update_interval := '0 seconds';
--     END IF;
--
--     IF NEW.range_test_last_packet_timestamp < NOW() - INTERVAL '1 hours' THEN
--         NEW.range_test_interval := '0 seconds';
--         NEW.range_test_first_packet_timestamp := 0;
--         NEW.range_test_packets_total := 0;
--     END IF;
--
--     IF NEW.pax_counter_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.pax_counter_interval := '0 seconds';
--     END IF;
--
--     IF NEW.neighbor_info_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.neighbor_info_interval := '0 seconds';
--     END IF;
--
--     IF NEW.map_broadcast_last_timestamp < NOW() - INTERVAL '24 hours' THEN
--         NEW.map_broadcast_interval := '0 seconds';
--     END IF;
--
--     NEW.last_updated := CURRENT_TIMESTAMP;
--
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;
--
-- -- Create the trigger
-- CREATE TRIGGER update_node_configurations_trigger
-- BEFORE UPDATE ON node_configurations
-- FOR EACH ROW
-- EXECUTE FUNCTION update_old_node_configurations();