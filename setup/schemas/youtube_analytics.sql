-- Schema definitions for youtube_analytics
-- Auto-extracted from sources/youtube_analytics/postgres.sh

-- Table: channel_basic
CREATE TABLE IF NOT EXISTS channel_basic (
    _fivetran_id VARCHAR(255) PRIMARY KEY,
    date DATE,
    _fivetran_synced TIMESTAMP,
    annotation_click_through_rate FLOAT,
    annotation_clickable_impressions INT,
    annotation_clicks INT,
    annotation_closable_impressions INT,
    annotation_close_rate FLOAT,
    annotation_closes INT,
    annotation_impressions INT,
    average_view_duration_percentage FLOAT,
    average_view_duration_seconds FLOAT,
    card_click_rate FLOAT,
    card_clicks INT,
    card_impressions INT,
    card_teaser_click_rate FLOAT,
    card_teaser_clicks INT,
    card_teaser_impressions INT,
    channel_id VARCHAR(255),
    comments INT,
    country_code VARCHAR(10),
    dislikes INT,
    likes INT,
    live_or_on_demand VARCHAR(50),
    red_views INT,
    red_watch_time_minutes FLOAT,
    shares INT,
    subscribed_status VARCHAR(50),
    subscribers_gained INT,
    subscribers_lost INT,
    video_id VARCHAR(255),
    videos_added_to_playlists INT,
    videos_removed_from_playlists INT,
    views INT,
    watch_time_minutes FLOAT
);

