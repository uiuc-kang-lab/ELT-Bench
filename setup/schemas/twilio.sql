-- Schema definitions for twilio
-- Auto-extracted from sources/twilio/postgres.sh

-- Table: message
CREATE TABLE IF NOT EXISTS message (
    id TEXT PRIMARY KEY,
    _fivetran_synced TEXT,
    account_id TEXT,
    body TEXT,
    created_at TEXT,
    date_sent TEXT,
    direction TEXT,
    error_code INTEGER,
    error_message INTEGER,
    message_from VARCHAR,
    messaging_service_sid INTEGER,
    num_media INTEGER,
    num_segments INTEGER,
    price DOUBLE PRECISION,
    price_unit TEXT,
    status TEXT,
    message_to VARCHAR,
    updated_at TEXT
);

