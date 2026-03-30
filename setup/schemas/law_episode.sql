-- Schema definitions for law_episode
-- Auto-extracted from sources/law_episode/postgres.sh

-- Table: credit
CREATE TABLE IF NOT EXISTS credit (
    episode_id TEXT NOT NULL,
    person_id  TEXT NOT NULL,
    category   TEXT,
    role       TEXT,
    credited   TEXT,
    PRIMARY KEY (episode_id, person_id)
);

