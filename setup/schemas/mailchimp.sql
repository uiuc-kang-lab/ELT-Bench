-- Schema definitions for mailchimp
-- Auto-extracted from sources/mailchimp/postgres.sh

-- Table: campaign_recipient_activity
CREATE TABLE IF NOT EXISTS campaign_recipient_activity (
    action TEXT,
    campaign_id TEXT,
    member_id TEXT,
    timestamp TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    bounce_type INTEGER,
    combination_id INTEGER,
    ip TEXT,
    list_id TEXT,
    url TEXT
);

-- Table: member
CREATE TABLE IF NOT EXISTS member (
    id TEXT,
    list_id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    country_code TEXT,
    dstoff DOUBLE PRECISION,
    email_address TEXT,
    email_client TEXT,
    email_type TEXT,
    gmtoff DOUBLE PRECISION,
    ip_opt TEXT,
    ip_signup TEXT,
    language TEXT,
    last_changed TIMESTAMP WITHOUT TIME ZONE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    member_rating INTEGER,
    merge_fname TEXT,
    merge_lname TEXT,
    status TEXT,
    timestamp_opt TIMESTAMP WITHOUT TIME ZONE,
    timestamp_signup TIMESTAMP WITHOUT TIME ZONE,
    timezone TEXT,
    unique_email_id TEXT,
    vip BOOLEAN
);

