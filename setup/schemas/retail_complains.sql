-- Schema definitions for retail_complains
-- Auto-extracted from sources/retail_complains/postgres.sh

-- Table: callcenterlogs
CREATE TABLE IF NOT EXISTS callcenterlogs (
    date_received DATE,
    complaint_id TEXT,
    rand_client TEXT,
    phonefinal TEXT,
    vru_line TEXT,
    call_id INTEGER,
    priority INTEGER,
    type TEXT,
    outcome TEXT,
    server TEXT,
    ser_start TEXT,
    ser_exit TEXT,
    ser_time TEXT
);

