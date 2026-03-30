-- Schema definitions for public_review_platform
-- Auto-extracted from sources/public_review_platform/postgres.sh

-- Table: business_categories
CREATE TABLE IF NOT EXISTS business_categories (
    business_id INTEGER,
  category_id INTEGER,
  PRIMARY KEY (business_id, category_id)
);

-- Table: elite
CREATE TABLE IF NOT EXISTS elite (
    user_id INTEGER,
  year_id INTEGER,
  PRIMARY KEY (user_id, year_id)
);

-- Table: tips
CREATE TABLE IF NOT EXISTS tips (
    business_id INTEGER,
  user_id INTEGER,
  likes INTEGER,
  tip_length TEXT,
  PRIMARY KEY (business_id, user_id)
);

