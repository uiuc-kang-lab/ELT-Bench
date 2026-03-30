-- Schema definitions for movie_platform
-- Auto-extracted from sources/movie_platform/postgres.sh

-- Table: ratings
CREATE TABLE IF NOT EXISTS ratings (
    movie_id                INTEGER,
    rating_id               SERIAL,
    rating_url              TEXT,
    rating_score            INTEGER,
    rating_timestamp_utc    TEXT,
    critic                  TEXT,
    critic_likes            INTEGER,
    critic_comments         INTEGER,
    user_id                 INTEGER,
    user_trialist           INTEGER,
    user_subscriber         INTEGER,
    user_eligible_for_trial INTEGER,
    user_has_payment_method INTEGER
);

-- Table: ratings_users
CREATE TABLE IF NOT EXISTS ratings_users (
    user_id                 INTEGER,
    rating_date_utc         TEXT,
    user_trialist           INTEGER,
    user_subscriber         INTEGER,
    user_avatar_image_url   TEXT,
    user_cover_image_url    TEXT,
    user_eligible_for_trial INTEGER,
    user_has_payment_method INTEGER
);

