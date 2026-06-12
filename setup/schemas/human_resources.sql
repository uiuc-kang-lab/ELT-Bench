-- Schema definitions for human_resources
-- Auto-extracted from sources/human_resources/postgres.sh

-- Table: employee
CREATE TABLE IF NOT EXISTS employee (
    ssn         TEXT PRIMARY KEY,
    lastname    TEXT,
    firstname   TEXT,
    hiredate    DATE, 
    salary      TEXT,
    gender      TEXT,
    performance TEXT,
    positionID  INTEGER,
    locationID  INTEGER
);

