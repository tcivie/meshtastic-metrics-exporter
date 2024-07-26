CREATE EXTENSION IF NOT EXISTS moddatetime;

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

CREATE OR REPLACE TRIGGER client_details_updated_at
    BEFORE UPDATE
    ON node_details
    FOR EACH ROW
EXECUTE PROCEDURE moddatetime(updated_at);
