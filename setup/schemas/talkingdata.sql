-- Schema definitions for talkingdata
-- Auto-extracted from sources/talkingdata/postgres.sh

-- Table: app_all
CREATE TABLE IF NOT EXISTS app_all (
    app_id BIGINT NOT NULL PRIMARY KEY
);

-- Table: app_events
CREATE TABLE IF NOT EXISTS app_events (
    event_id INTEGER NOT NULL,
    app_id BIGINT NOT NULL,
    is_installed INTEGER NOT NULL,
    is_active INTEGER NOT NULL
);

-- Table: app_events_relevant
CREATE TABLE IF NOT EXISTS app_events_relevant (
    event_id INTEGER NOT NULL,
    app_id BIGINT NOT NULL,
    is_installed INTEGER DEFAULT NULL,
    is_active INTEGER DEFAULT NULL
);

-- Table: events
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER NOT NULL,
    device_id BIGINT DEFAULT NULL,
    timestamp timestamp DEFAULT NULL,
    longitude REAL DEFAULT NULL,
    latitude REAL DEFAULT NULL
);

-- Table: events_relevant
CREATE TABLE IF NOT EXISTS events_relevant (
    event_id INTEGER NOT NULL,
    device_id BIGINT DEFAULT NULL,
    timestamp BIGINT NOT NULL,
    longitude REAL NOT NULL,
    latitude REAL NOT NULL
);

-- Table: sample_submission
CREATE TABLE IF NOT EXISTS sample_submission (
    device_id BIGINT NOT NULL PRIMARY KEY,
    F23_ REAL DEFAULT NULL,
    F24_26 REAL DEFAULT NULL,
    F27_28 REAL DEFAULT NULL,
    F29_32 REAL DEFAULT NULL,
    F33_42 REAL DEFAULT NULL,
    F43_ REAL DEFAULT NULL,
    M22_ REAL DEFAULT NULL,
    M23_26 REAL DEFAULT NULL,
    M27_28 REAL DEFAULT NULL,
    M29_31 REAL DEFAULT NULL,
    M32_38 REAL DEFAULT NULL,
    M39_ REAL DEFAULT NULL
);

