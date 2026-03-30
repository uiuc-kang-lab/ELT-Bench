-- Schema definitions for professional_basketball
-- Auto-extracted from sources/professional_basketball/postgres.sh

-- Table: coaches
CREATE TABLE IF NOT EXISTS coaches (
    coachID     TEXT NOT NULL,
    year        INTEGER NOT NULL,
    tmID        TEXT NOT NULL,
    lgID        TEXT,
    stint       INTEGER NOT NULL,
    won         INTEGER,
    lost        INTEGER,
    post_wins   INTEGER,
    post_losses INTEGER,
    PRIMARY KEY (coachID, year, tmID, stint)
);

-- Table: players_teams
CREATE TABLE IF NOT EXISTS players_teams (
    id                 SERIAL PRIMARY KEY,
    playerID           TEXT NOT NULL,
    year               INTEGER,
    stint              INTEGER,
    tmID               TEXT,
    lgID               TEXT,
    GP                 INTEGER,
    GS                 INTEGER,
    minutes            INTEGER,
    points             INTEGER,
    oRebounds          INTEGER,
    dRebounds          INTEGER,
    rebounds           INTEGER,
    assists            INTEGER,
    steals             INTEGER,
    blocks             INTEGER,
    turnovers          INTEGER,
    PF                 INTEGER,
    fgAttempted        INTEGER,
    fgMade             INTEGER,
    ftAttempted        INTEGER,
    ftMade             INTEGER,
    threeAttempted     INTEGER,
    threeMade          INTEGER,
    PostGP             INTEGER,
    PostGS             INTEGER,
    PostMinutes        INTEGER,
    PostPoints         INTEGER,
    PostoRebounds      INTEGER,
    PostdRebounds      INTEGER,
    PostRebounds       INTEGER,
    PostAssists        INTEGER,
    PostSteals         INTEGER,
    PostBlocks         INTEGER,
    PostTurnovers      INTEGER,
    PostPF             INTEGER,
    PostfgAttempted    INTEGER,
    PostfgMade         INTEGER,
    PostftAttempted    INTEGER,
    PostftMade         INTEGER,
    PostthreeAttempted INTEGER,
    PostthreeMade      INTEGER,
    note               TEXT
);

