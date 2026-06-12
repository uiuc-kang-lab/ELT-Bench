-- Schema definitions for student_loan
-- Auto-extracted from sources/student_loan/postgres.sh

-- Table: longest_absense_from_school
CREATE TABLE IF NOT EXISTS longest_absense_from_school (
    name   TEXT PRIMARY KEY DEFAULT '' NOT NULL,
    month  INTEGER DEFAULT 0
);

