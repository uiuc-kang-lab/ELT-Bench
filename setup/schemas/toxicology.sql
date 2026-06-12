-- Schema definitions for toxicology
-- Auto-extracted from sources/toxicology/postgres.sh

-- Table: connected
CREATE TABLE IF NOT EXISTS connected (
    atom_id   TEXT NOT NULL,
    atom_id2  TEXT NOT NULL,
    bond_id   TEXT DEFAULT NULL,
    PRIMARY KEY (atom_id, atom_id2)
);

