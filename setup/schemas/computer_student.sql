-- Schema definitions for computer_student
-- Auto-extracted from sources/computer_student/postgres.sh

-- Table: taught_by
CREATE TABLE IF NOT EXISTS taught_by (
    course_id INTEGER NOT NULL,
    p_id      INTEGER NOT NULL,
    PRIMARY KEY (course_id, p_id)
);

