-- Schema definitions for twitter_organic
-- Auto-extracted from sources/twitter_organic/postgres.sh

-- Table: tweet
CREATE TABLE IF NOT EXISTS tweet (
    id BIGINT PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    account_id TEXT,
    card_uri TEXT,
    coordinates_coordinates INTEGER,
    coordinates_type INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    favorite_count INTEGER,
    favorited BOOLEAN,
    followers INTEGER,
    geo_coordinates INTEGER,
    geo_type INTEGER,
    in_reply_to_screen_name TEXT,
    in_reply_to_status_id INTEGER,
    in_reply_to_user_id float,
    lang TEXT,
    media_key INTEGER,
    retweet_count INTEGER,
    retweeted BOOLEAN,
    truncated BOOLEAN,
    tweet_type TEXT,
    user_id INTEGER,
    source TEXT,
    full_test TEXT
);

