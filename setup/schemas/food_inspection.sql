-- Schema definitions for food_inspection
-- Auto-extracted from sources/food_inspection/postgres.sh

-- Table: violations
CREATE TABLE IF NOT EXISTS violations (
    business_id INTEGER NOT NULL,
  date DATE NOT NULL,
  violation_type_id TEXT NOT NULL,
  risk_category TEXT NOT NULL,
  description TEXT NOT NULL
);

