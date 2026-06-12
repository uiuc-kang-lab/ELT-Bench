-- Schema definitions for chicago_crime
-- Auto-extracted from sources/chicago_crime/postgres.sh

-- Table: crime
CREATE TABLE IF NOT EXISTS crime (
    report_no            SERIAL PRIMARY KEY,
    case_number          TEXT NOT NULL,
    date                 TEXT NOT NULL,
    block                TEXT,
    iucr_no              TEXT NOT NULL,
    location_description TEXT,
    arrest               TEXT,
    domestic             TEXT,
    beat                 INTEGER,
    district_no          INTEGER,
    ward_no              INTEGER,
    community_area_no    INTEGER,
    fbi_code_no          TEXT,
    latitude             TEXT,
    longitude            TEXT
);

-- Table: iucr
CREATE TABLE IF NOT EXISTS iucr (
    iucr_no               TEXT PRIMARY KEY,
    primary_description   TEXT NOT NULL,
    secondary_description TEXT,
    index_code            TEXT
);

