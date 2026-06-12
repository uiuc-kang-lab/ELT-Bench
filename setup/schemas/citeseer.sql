-- Schema definitions for citeseer
-- Auto-extracted from sources/citeseer/postgres.sh

-- Table: content
CREATE TABLE IF NOT EXISTS content (
    paper_id      TEXT NOT NULL,
    word_cited_id TEXT NOT NULL,
    PRIMARY KEY (paper_id, word_cited_id)
);

