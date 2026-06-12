-- Schema definitions for video_games
-- Auto-extracted from sources/video_games/postgres.sh

-- Table: game_platform
CREATE TABLE IF NOT EXISTS game_platform (
    id                SERIAL PRIMARY KEY,
    game_publisher_id INTEGER,
    platform_id       INTEGER,
    release_year      INTEGER
);

-- Table: region_sales
CREATE TABLE IF NOT EXISTS region_sales (
    region_id        INTEGER,
    game_platform_id INTEGER,
    num_sales        REAL
);

