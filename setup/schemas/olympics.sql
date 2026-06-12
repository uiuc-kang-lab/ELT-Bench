-- Schema definitions for olympics
-- Auto-extracted from sources/olympics/postgres.sh

-- Table: competitor_event
CREATE TABLE IF NOT EXISTS competitor_event (
    event_id      INTEGER DEFAULT NULL,
    competitor_id INTEGER DEFAULT NULL,
    medal_id      INTEGER DEFAULT NULL
);

-- Table: games_competitor
CREATE TABLE IF NOT EXISTS games_competitor (
    id        SERIAL PRIMARY KEY,
    games_id  INTEGER DEFAULT NULL,
    person_id INTEGER DEFAULT NULL,
    age       INTEGER DEFAULT NULL
);

