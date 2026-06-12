-- Schema definitions for college_completion
-- Auto-extracted from sources/college_completion/postgres.sh

-- Table: institution_grads
CREATE TABLE IF NOT EXISTS institution_grads (
    unitid        INTEGER,
    year          INTEGER,
    gender        TEXT,
    race          TEXT,
    cohort        TEXT,
    grad_cohort   REAL,
    grad_100      REAL,
    grad_150      REAL,
    grad_100_rate REAL,
    grad_150_rate REAL
);

