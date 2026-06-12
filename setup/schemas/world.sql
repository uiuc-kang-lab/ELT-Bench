-- Schema definitions for world
-- Auto-extracted from sources/world/postgres.sh

-- Table: country
CREATE TABLE IF NOT EXISTS country (
    Code VARCHAR NOT NULL DEFAULT '',
  Name VARCHAR NOT NULL DEFAULT '',
  Continent VARCHAR NOT NULL DEFAULT 'Asia',
  Region VARCHAR NOT NULL DEFAULT '',
  SurfaceArea REAL NOT NULL DEFAULT 0.00,
  IndepYear INTEGER DEFAULT NULL,
  Population INTEGER NOT NULL DEFAULT 0,
  LifeExpectancy REAL DEFAULT NULL,
  GNP REAL DEFAULT NULL,
  GNPOld REAL DEFAULT NULL,
  LocalName VARCHAR NOT NULL DEFAULT '',
  GovernmentForm VARCHAR NOT NULL DEFAULT '',
  HeadOfState VARCHAR DEFAULT NULL,
  Capital INTEGER DEFAULT NULL,
  Code2 VARCHAR NOT NULL DEFAULT '',
  PRIMARY KEY (Code)
);

