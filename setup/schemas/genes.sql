-- Schema definitions for genes
-- Auto-extracted from sources/genes/postgres.sh

-- Table: interactions
CREATE TABLE IF NOT EXISTS interactions (
    GeneID1         TEXT    NOT NULL,
    GeneID2         TEXT    NOT NULL,
    Type            TEXT    NOT NULL,
    Expression_Corr REAL    NOT NULL,
    PRIMARY KEY (GeneID1, GeneID2)
);

