-- Schema definitions for music_platform_2
-- Auto-extracted from sources/music_platform_2/postgres.sh

-- Table: reviews
CREATE TABLE IF NOT EXISTS reviews (
    podcast_id TEXT,
    title TEXT,
    content TEXT ,
    rating INTEGER,
    author_id TEXT,
    created_at TEXT
);

