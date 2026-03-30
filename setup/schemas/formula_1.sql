-- Schema definitions for formula_1
-- Auto-extracted from sources/formula_1/postgres.sh

-- Table: constructor_results
CREATE TABLE IF NOT EXISTS constructor_results (
    constructorResultsId SERIAL PRIMARY KEY,
    raceId               INTEGER DEFAULT 0 NOT NULL,
    constructorId        INTEGER DEFAULT 0 NOT NULL,
    points               REAL,
    status               TEXT
);

-- Table: constructor_standings
CREATE TABLE IF NOT EXISTS constructor_standings (
    constructorStandingsId SERIAL PRIMARY KEY,
    raceId                 INTEGER DEFAULT 0 NOT NULL,
    constructorId          INTEGER DEFAULT 0 NOT NULL,
    points                 REAL DEFAULT 0 NOT NULL,
    position               INTEGER,
    positionText           TEXT,
    wins                   INTEGER DEFAULT 0 NOT NULL
);

-- Table: qualifying
CREATE TABLE IF NOT EXISTS qualifying (
    qualifyId     SERIAL PRIMARY KEY,
    raceId        INTEGER DEFAULT 0 NOT NULL,
    driverId      INTEGER DEFAULT 0 NOT NULL,
    constructorId INTEGER DEFAULT 0 NOT NULL,
    number        INTEGER DEFAULT 0 NOT NULL,
    position      INTEGER,
    q1            TEXT,
    q2            TEXT,
    q3            TEXT
);

-- Table: results
CREATE TABLE IF NOT EXISTS results (
    resultId        SERIAL PRIMARY KEY,
    raceId          INTEGER DEFAULT 0 NOT NULL,
    driverId        INTEGER DEFAULT 0 NOT NULL,
    constructorId   INTEGER DEFAULT 0 NOT NULL,
    number          INTEGER,
    grid            INTEGER DEFAULT 0 NOT NULL,
    position        INTEGER,
    positionText    TEXT DEFAULT '' NOT NULL,
    positionOrder   INTEGER DEFAULT 0 NOT NULL,
    points          REAL DEFAULT 0 NOT NULL,
    laps            INTEGER DEFAULT 0 NOT NULL,
    time            TEXT,
    milliseconds    INTEGER,
    fastestLap      INTEGER,
    rank            INTEGER DEFAULT 0,
    fastestLapTime  TEXT,
    fastestLapSpeed TEXT,
    statusId        INTEGER DEFAULT 0 NOT NULL
);

-- Table: lap_times
CREATE TABLE IF NOT EXISTS lap_times (
    raceId       INTEGER NOT NULL,
  driverId     INTEGER NOT NULL,
  lap           INTEGER NOT NULL,
  position      INTEGER,
  time          TEXT,
  milliseconds  INTEGER
);

