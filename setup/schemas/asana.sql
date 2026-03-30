-- Schema definitions for asana
-- Auto-extracted from sources/asana/postgres.sh

-- Table: tag
CREATE TABLE IF NOT EXISTS tag (
    id BIGINT PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    color INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    message INTEGER,
    name TEXT,
    notes INTEGER,
    workspace_id BIGINT
);

-- Table: task
CREATE TABLE IF NOT EXISTS task (
    id BIGINT PRIMARY KEY,
    assignee_id BIGINT,
    completed BOOLEAN,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    completed_by_id BIGINT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    due_on TIMESTAMP WITHOUT TIME ZONE,
    due_at TIMESTAMP WITHOUT TIME ZONE,
    modified_at TIMESTAMP WITHOUT TIME ZONE,
    name TEXT,
    parent_id BIGINT,
    start_on TIMESTAMP WITHOUT TIME ZONE,
    notes TEXT,
    workspace_id BIGINT
);

