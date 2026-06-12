-- Schema definitions for software_company
-- Auto-extracted from sources/software_company/postgres.sh

-- Table: sales
CREATE TABLE IF NOT EXISTS sales (
    eventid    SERIAL PRIMARY KEY,
  refid      INTEGER,  -- Assuming 'id' is the primary key of Customers table
  event_date TIMESTAMP,
  amount     REAL
);

