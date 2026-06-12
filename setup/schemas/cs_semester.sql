-- Schema definitions for cs_semester
-- Auto-extracted from sources/cs_semester/postgres.sh

-- Table: registration
CREATE TABLE IF NOT EXISTS registration (
    course_id  INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    grade      TEXT,
    sat        INTEGER,
    PRIMARY KEY (course_id, student_id)
);

