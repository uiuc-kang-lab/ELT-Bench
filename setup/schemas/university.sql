-- Schema definitions for university
-- Auto-extracted from sources/university/postgres.sh

-- Table: university_year
CREATE TABLE IF NOT EXISTS university_year (
    university_id              INTEGER NOT NULL,
    year                       INTEGER NOT NULL,
    num_students               INTEGER DEFAULT NULL,
    student_staff_ratio        REAL DEFAULT NULL,
    pct_international_students INTEGER DEFAULT NULL,
    pct_female_students        INTEGER DEFAULT NULL,
    PRIMARY KEY (university_id, year)
);

