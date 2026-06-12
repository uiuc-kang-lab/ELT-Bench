-- Schema definitions for simpson_episodes
-- Auto-extracted from sources/simpson_episodes/postgres.sh

-- Table: credit
CREATE TABLE IF NOT EXISTS credit (
    episode_id TEXT,
    category   TEXT,
    person     TEXT,
    role       TEXT,
    credited   TEXT
);

-- Table: vote
CREATE TABLE IF NOT EXISTS vote (
    episode_id TEXT,
    stars      INTEGER,
    votes      INTEGER,
    percent    REAL
);

