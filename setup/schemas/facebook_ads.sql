-- Schema definitions for facebook_ads
-- Auto-extracted from sources/facebook_ads/postgres.sh

-- Table: ad_history
CREATE TABLE IF NOT EXISTS ad_history (
    id BIGINT,
    account_id BIGINT,
    ad_set_id BIGINT,
    campaign_id BIGINT,
    creative_id BIGINT,
    name VARCHAR(255),
    _fivetran_synced TIMESTAMP,
    updated_time TIMESTAMP
);

-- Table: basic_ad_action_values
CREATE TABLE IF NOT EXISTS basic_ad_action_values (
    ad_id BIGINT,
    date DATE,
    _fivetran_id VARCHAR(255),
    index INT,
    action_type VARCHAR(255),
    value DECIMAL(15, 2),
    _fivetran_synced TIMESTAMP,
    _7_d_click DECIMAL(15, 2)
);

