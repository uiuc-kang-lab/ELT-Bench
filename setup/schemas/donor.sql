-- Schema definitions for donor
-- Auto-extracted from sources/donor/postgres.sh

-- Table: resources
CREATE TABLE IF NOT EXISTS resources (
    resourceid            TEXT PRIMARY KEY,
    projectid             TEXT,
    vendorid              INTEGER,
    vendor_name           TEXT,
    project_resource_type TEXT,
    item_name             TEXT,
    item_number           TEXT,
    item_unit_price       REAL,
    item_quantity         INTEGER
);

