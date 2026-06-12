-- Schema definitions for cookbook
-- Auto-extracted from sources/cookbook/postgres.sh

-- Table: quantity
CREATE TABLE IF NOT EXISTS quantity (
    quantity_id   INTEGER PRIMARY KEY,
    recipe_id     INTEGER,
    ingredient_id INTEGER,
    max_qty       REAL,
    min_qty       REAL,
    unit          TEXT,
    preparation   TEXT,
    optional      TEXT
);

