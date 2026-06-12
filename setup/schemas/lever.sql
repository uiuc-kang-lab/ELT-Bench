-- Schema definitions for lever
-- Auto-extracted from sources/lever/postgres.sh

-- Table: application
CREATE TABLE IF NOT EXISTS application (
    id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    archived_at TIMESTAMP WITHOUT TIME ZONE,
    archived_reason_id INTEGER,
    candidate_id INTEGER,
    comments INTEGER,
    company INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    posting_hiring_manager_id TEXT,
    posting_id TEXT,
    posting_owner_id TEXT,
    referrer_id TEXT,
    requisition_for_hire_id INTEGER,
    type TEXT,
    opportunity_id TEXT
);

-- Table: feedback_form_field
CREATE TABLE IF NOT EXISTS feedback_form_field (
    feedback_form_id TEXT,
    field_index BIGINT,
    value_index BIGINT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    code_language INTEGER,
    currency INTEGER,
    value_date TIMESTAMP WITHOUT TIME ZONE,
    value_decimal NUMERIC,
    value_file_id INTEGER,
    value_number INTEGER,
    value_text TEXT
);

-- Table: offer
CREATE TABLE IF NOT EXISTS offer (
    id TEXT,  
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE, 
    candidate_id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE,  
    creator_id TEXT,  
    status TEXT
);

-- Table: requisition
CREATE TABLE IF NOT EXISTS requisition (
    id TEXT,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    backfill BOOLEAN,
    compensation_band_currency TEXT,
    compensation_band_interval TEXT,
    compensation_band_max INTEGER,
    compensation_band_min INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    creator_id TEXT,
    employment_status TEXT,
    headcount_hired INTEGER,
    headcount_infinite INTEGER,
    headcount_total INTEGER,
    hiring_manager_id TEXT,
    internal_notes TEXT,
    location TEXT,
    name TEXT,
    owner_id TEXT,
    requisition_code INTEGER,
    status TEXT,
    team TEXT
);

-- Table: posting
CREATE TABLE IF NOT EXISTS posting (
    id TEXT,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    categories_commitment TEXT,
    categories_department INTEGER,
    categories_level INTEGER,
    categories_location TEXT,
    categories_team TEXT,
    content_closing TEXT,
    content_closing_html TEXT,
    content_description TEXT,
    content_description_html TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    creator_id TEXT,
    owner_id TEXT,
    requisition_code INTEGER,
    state TEXT,
    text TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);

