-- Schema definitions for music_tracker
-- Auto-extracted from sources/music_tracker/postgres.sh

-- Table: tags
CREATE TABLE IF NOT EXISTS tags (
    tag_index SERIAL PRIMARY KEY,  
    id        INTEGER,  
    tag       TEXT
);

