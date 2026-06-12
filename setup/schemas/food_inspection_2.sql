-- Schema definitions for food_inspection_2
-- Auto-extracted from sources/food_inspection_2/postgres.sh

-- Table: inspection
CREATE TABLE IF NOT EXISTS inspection (
    inspection_id   SERIAL PRIMARY KEY,
    inspection_date DATE,
    inspection_type TEXT,
    results         TEXT,
    employee_id     INTEGER,
    license_no      INTEGER,
    followup_to     INTEGER
);

