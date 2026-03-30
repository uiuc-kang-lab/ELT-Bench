-- Schema definitions for disney
-- Auto-extracted from sources/disney/postgres.sh

-- Table: revenue
CREATE TABLE IF NOT EXISTS revenue (
    Year INTEGER PRIMARY KEY,
    Studio_Entertainment_NI_1 REAL,
    Disney_Consumer_Products_NI_2 REAL,
    disney_interactive_ni_3__rev_1 REAL,
    Walt_Disney_Parks_and_Resorts REAL,
    Disney_Media_Networks TEXT,
    Total INTEGER
);

