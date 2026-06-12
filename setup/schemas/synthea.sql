-- Schema definitions for synthea
-- Auto-extracted from sources/synthea/postgres.sh

-- Table: allergies
CREATE TABLE IF NOT EXISTS allergies (
    START       DATE,
    STOP        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        INTEGER,
    DESCRIPTION TEXT,
    PRIMARY KEY (PATIENT, ENCOUNTER, CODE)
);

-- Table: careplans
CREATE TABLE IF NOT EXISTS careplans (
    ID                TEXT,
    START             DATE,
    STOP              DATE,
    PATIENT           TEXT,
    ENCOUNTER         TEXT,
    CODE              REAL,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT
);

-- Table: claims
CREATE TABLE IF NOT EXISTS claims (
    ID             TEXT PRIMARY KEY,
    PATIENT        TEXT,
    BILLABLEPERIOD DATE,
    ORGANIZATION   TEXT,
    ENCOUNTER      TEXT,
    DIAGNOSIS      TEXT,
    TOTAL          INTEGER
);

-- Table: conditions
CREATE TABLE IF NOT EXISTS conditions (
    START       DATE,
    STOP        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        BIGINT,
    DESCRIPTION TEXT
);

-- Table: encounters
CREATE TABLE IF NOT EXISTS encounters (
    ID                TEXT PRIMARY KEY,
    DATE              DATE,
    PATIENT           TEXT,
    CODE              INTEGER,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT
);

-- Table: immunizations
CREATE TABLE IF NOT EXISTS immunizations (
    DATE        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        INTEGER,
    DESCRIPTION TEXT,
    PRIMARY KEY (DATE, PATIENT, ENCOUNTER, CODE)
);

-- Table: medications
CREATE TABLE IF NOT EXISTS medications (
    START             DATE,
    STOP              DATE,
    PATIENT           TEXT,
    ENCOUNTER         TEXT,
    CODE              INTEGER,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT,
    PRIMARY KEY (START, PATIENT, ENCOUNTER, CODE)
);

