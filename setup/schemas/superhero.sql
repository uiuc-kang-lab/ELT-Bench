-- Schema definitions for superhero
-- Auto-extracted from sources/superhero/postgres.sh

-- Table: hero_power
CREATE TABLE IF NOT EXISTS hero_power (
    hero_id  INTEGER,
    power_id INTEGER
);

