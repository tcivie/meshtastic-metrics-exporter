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
    role           VARCHAR
);
