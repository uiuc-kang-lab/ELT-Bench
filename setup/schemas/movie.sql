-- Schema definitions for movie
-- Auto-extracted from sources/movie/postgres.sh

-- Table: movies
CREATE TABLE IF NOT EXISTS movies (
    MovieID        SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing primary key
    Title          TEXT,
    MPAA_Rating  TEXT,
    Budget         INTEGER,
    Gross          BIGINT,
    Release_Date DATE,  -- Changed from TEXT to DATE for date fields
    Genre          TEXT,
    Runtime        INTEGER,
    Rating         REAL,
    Rating_Count INTEGER,
    Summary        TEXT
);

