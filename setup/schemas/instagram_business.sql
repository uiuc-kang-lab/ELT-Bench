-- Schema definitions for instagram_business
-- Auto-extracted from sources/instagram_business/postgres.sh

-- Table: media_insights
CREATE TABLE IF NOT EXISTS media_insights (
    _fivetran_id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    carousel_album_engagement FLOAT,
    carousel_album_impressions FLOAT,
    carousel_album_reach FLOAT,
    carousel_album_saved FLOAT,
    carousel_album_video_views FLOAT,
    comment_count FLOAT,
    id BIGINT,
    like_count INTEGER,
    story_exits INTEGER,
    story_impressions INTEGER,
    story_reach INTEGER,
    story_replies INTEGER,
    story_taps_back INTEGER,
    story_taps_forward INTEGER,
    video_photo_engagement FLOAT,
    video_photo_impressions FLOAT,
    video_photo_reach FLOAT,
    video_photo_saved FLOAT,
    video_views FLOAT,
    reel_comments FLOAT,
    reel_likes FLOAT,
    reel_plays FLOAT,
    reel_reach FLOAT,
    reel_shares FLOAT,
    reel_total_interactions FLOAT
);

