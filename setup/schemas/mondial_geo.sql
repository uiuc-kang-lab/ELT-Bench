-- Schema definitions for mondial_geo
-- Auto-extracted from sources/mondial_geo/postgres.sh

-- Table: is_member
CREATE TABLE IF NOT EXISTS is_member (
    Country      TEXT NOT NULL,
    Organization TEXT NOT NULL,
    Type         TEXT DEFAULT 'member',
    PRIMARY KEY (Country, Organization)
);

-- Table: located
CREATE TABLE IF NOT EXISTS located (
    City     TEXT,
    Province TEXT,
    Country  TEXT,
    River    TEXT,
    Lake     TEXT,
    Sea      TEXT
);

-- Table: located_on
CREATE TABLE IF NOT EXISTS located_on (
    City     TEXT DEFAULT '' NOT NULL,
    Province TEXT DEFAULT '' NOT NULL,
    Country  TEXT DEFAULT '' NOT NULL,
    Island   TEXT DEFAULT '' NOT NULL
);

-- Table: politics
CREATE TABLE IF NOT EXISTS politics (
    Country      TEXT DEFAULT '' NOT NULL,
    Independence DATE,
    Dependent    TEXT,
    Government   TEXT
);

