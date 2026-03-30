-- Schema definitions for ice_hockey_draft
-- Auto-extracted from sources/ice_hockey_draft/postgres.sh

-- Table: seasonstatus
CREATE TABLE IF NOT EXISTS seasonstatus (
    ELITEID   INTEGER,
    SEASON    TEXT,  -- You could change this to VARCHAR if there's a length limit
    TEAM      TEXT,  -- You could change this to VARCHAR if there's a length limit
    LEAGUE    TEXT,  -- You could change this to VARCHAR if there's a length limit
    GAMETYPE  TEXT,  -- You could change this to VARCHAR if there's a length limit
    GP        INTEGER,
    G         INTEGER,
    A         INTEGER,
    P         INTEGER,
    PIM       INTEGER,
    PLUSMINUS INTEGER
);

