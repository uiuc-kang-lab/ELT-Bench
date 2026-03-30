-- Schema definitions for airline
-- Auto-extracted from sources/airline/postgres.sh

-- Table: airlines
CREATE TABLE IF NOT EXISTS airlines (
    FL_DATE               TEXT,
    OP_CARRIER_AIRLINE_ID INTEGER,
    TAIL_NUM              TEXT,
    OP_CARRIER_FL_NUM     INTEGER,
    ORIGIN_AIRPORT_ID     INTEGER,
    ORIGIN_AIRPORT_SEQ_ID INTEGER,
    ORIGIN_CITY_MARKET_ID INTEGER,
    ORIGIN                TEXT,
    DEST_AIRPORT_ID       INTEGER,
    DEST_AIRPORT_SEQ_ID   INTEGER,
    DEST_CITY_MARKET_ID   INTEGER,
    DEST                  TEXT,
    CRS_DEP_TIME          INTEGER,
    DEP_TIME              INTEGER,
    DEP_DELAY             INTEGER,
    DEP_DELAY_NEW         INTEGER,
    ARR_TIME              INTEGER,
    ARR_DELAY             INTEGER,
    ARR_DELAY_NEW         INTEGER,
    CANCELLED             INTEGER,
    CANCELLATION_CODE     TEXT,
    CRS_ELAPSED_TIME      INTEGER,
    ACTUAL_ELAPSED_TIME   INTEGER,
    CARRIER_DELAY         INTEGER,
    WEATHER_DELAY         INTEGER,
    NAS_DELAY             INTEGER,
    SECURITY_DELAY        INTEGER,
    LATE_AIRCRAFT_DELAY   INTEGER
);

