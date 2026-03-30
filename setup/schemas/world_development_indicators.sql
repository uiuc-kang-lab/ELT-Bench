-- Schema definitions for world_development_indicators
-- Auto-extracted from sources/world_development_indicators/postgres.sh

-- Table: indicators
CREATE TABLE IF NOT EXISTS indicators (
    CountryName   TEXT,
    CountryCode   TEXT NOT NULL,
    IndicatorName TEXT,
    IndicatorCode TEXT NOT NULL,
    Year          INTEGER NOT NULL,
    Value         BIGINT,
    PRIMARY KEY (CountryCode, IndicatorCode, Year)
);

