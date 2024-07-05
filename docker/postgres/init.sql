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

CREATE TABLE IF NOT EXISTS client_details
(
    node_id        VARCHAR PRIMARY KEY,
    short_name     VARCHAR,
    long_name      VARCHAR,
    hardware_model VARCHAR,
    role        VARCHAR,
    mqtt_status VARCHAR default 'none'
);

CREATE TABLE IF NOT EXISTS node_graph
(
    node_id                 VARCHAR PRIMARY KEY,
    last_sent_by_node_id    VARCHAR,
    last_sent_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    broadcast_interval_secs INTEGER,
    FOREIGN KEY (node_id) REFERENCES client_details (node_id)
);

CREATE TABLE IF NOT EXISTS node_neighbors
(
    id          SERIAL PRIMARY KEY,
    node_id     VARCHAR,
    neighbor_id VARCHAR,
    snr         FLOAT,
    FOREIGN KEY (node_id) REFERENCES client_details (node_id),
    FOREIGN KEY (neighbor_id) REFERENCES node_graph (node_id),
    UNIQUE (node_id, neighbor_id)
);

CREATE UNIQUE INDEX idx_unique_node_neighbor ON node_neighbors (node_id, neighbor_id);
