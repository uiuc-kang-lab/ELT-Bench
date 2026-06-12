-- Schema definitions for pardot
-- Auto-extracted from sources/pardot/postgres.sh

-- Table: list
CREATE TABLE IF NOT EXISTS list (
    id BIGINT PRIMARY KEY,
    _fivetran_synced VARCHAR,
    created_at VARCHAR,
    is_crm_visible BOOLEAN,
    is_dynamic BOOLEAN,
    is_public BOOLEAN,
    updated_at VARCHAR,
    name VARCHAR,
    title VARCHAR,
    description VARCHAR
);

-- Table: visitor
CREATE TABLE IF NOT EXISTS visitor (
    id BIGINT PRIMARY KEY,
    _fivetran_synced VARCHAR,
    campaign_parameter BIGINT,
    content_parameter BIGINT,
    created_at VARCHAR,
    medium_parameter BIGINT,
    page_view_count BIGINT,
    prospect_id BIGINT,
    source_parameter BIGINT,
    term_parameter BIGINT,
    updated_at VARCHAR,
    hostname VARCHAR,
    ip_address VARCHAR
);

