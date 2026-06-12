-- Schema definitions for card_games
-- Auto-extracted from sources/card_games/postgres.sh

-- Table: legalities
CREATE TABLE IF NOT EXISTS legalities (
    id     SERIAL PRIMARY KEY,
    format TEXT,
    status TEXT,
    uuid   TEXT
);

