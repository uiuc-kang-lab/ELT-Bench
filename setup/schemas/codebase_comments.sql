-- Schema definitions for codebase_comments
-- Auto-extracted from sources/codebase_comments/postgres.sh

-- Table: method_parameter
CREATE TABLE IF NOT EXISTS method_parameter (
    Id SERIAL PRIMARY KEY,
    MethodId TEXT NOT NULL,
    Type TEXT,
    Name TEXT
);

-- Table: solution
CREATE TABLE IF NOT EXISTS solution (
    Id SERIAL PRIMARY KEY,
    RepoId INTEGER,
    Path TEXT,
    ProcessedTime BIGINT,
    WasCompiled INTEGER
);

