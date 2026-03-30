-- Schema definitions for movielens
-- Auto-extracted from sources/movielens/postgres.sh

-- Table: movies
CREATE TABLE IF NOT EXISTS movies (
    movieid     SERIAL PRIMARY KEY,
    year        INTEGER NOT NULL,
    isEnglish   BOOLEAN NOT NULL,
    country     TEXT NOT NULL,
    runningtime INTEGER NOT NULL
);

-- Table: u2base
CREATE TABLE IF NOT EXISTS u2base (
    userid  INTEGER NOT NULL,
    movieid INTEGER NOT NULL,
    rating  TEXT NOT NULL,
    PRIMARY KEY (userid, movieid)
);

