-- Schema definitions for authors
-- Auto-extracted from sources/authors/postgres.sh

-- Table: paper
CREATE TABLE IF NOT EXISTS paper (
    Id SERIAL PRIMARY KEY,
    Title TEXT,
    Year INTEGER,
    ConferenceId INTEGER,
    JournalId INTEGER,
    Keyword TEXT
);

