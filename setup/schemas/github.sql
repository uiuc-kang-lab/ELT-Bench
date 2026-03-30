-- Schema definitions for github
-- Auto-extracted from sources/github/postgres.sh

-- Table: issue
CREATE TABLE IF NOT EXISTS issue (
    id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    body TEXT,
    closed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    locked BOOLEAN,
    milestone_id INTEGER,
    number INTEGER,
    pull_request BOOLEAN,
    repository_id INTEGER,
    state TEXT,
    title TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    user_id INTEGER
);

-- Table: issue_closed_history
CREATE TABLE IF NOT EXISTS issue_closed_history (
    issue_id INTEGER PRIMARY KEY,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    actor_id INTEGER,
    closed BOOLEAN,
    commit_sha INTEGER
);

-- Table: pull_request
CREATE TABLE IF NOT EXISTS pull_request (
    id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    base_label TEXT,
    base_ref TEXT,
    base_repo_id INTEGER,
    base_sha TEXT,
    base_user_id INTEGER,
    head_label TEXT,
    head_ref TEXT,
    head_repo_id INTEGER,
    head_sha TEXT,
    head_user_id INTEGER,
    issue_id INTEGER,
    merge_commit_sha TEXT
);

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    bio TEXT,
    blog TEXT,
    company TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    hireable BOOLEAN,
    location TEXT,
    login TEXT,
    name TEXT,
    site_admin BOOLEAN,
    type TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);

