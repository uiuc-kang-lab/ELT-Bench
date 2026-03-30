-- Schema definitions for bike_share_1
-- Auto-extracted from sources/bike_share_1/postgres.sh

-- Table: status
CREATE TABLE IF NOT EXISTS status (
    station_id      INTEGER NOT NULL,
    bikes_available INTEGER NOT NULL,
    docks_available INTEGER NOT NULL,
    time            TEXT NOT NULL
);

