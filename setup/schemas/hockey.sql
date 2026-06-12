-- Schema definitions for hockey
-- Auto-extracted from sources/hockey/postgres.sh

-- Table: goalies_shootout
CREATE TABLE IF NOT EXISTS goalies_shootout (
    playerID TEXT,
  year INTEGER,
  stint INTEGER,
  tmID TEXT,
  W INTEGER,
  L INTEGER,
  SA INTEGER,
  GA INTEGER
);

-- Table: master
CREATE TABLE IF NOT EXISTS master (
    playerID TEXT,
  coachID TEXT,
  hofID TEXT,
  firstName TEXT,
  lastName TEXT NOT NULL,
  nameNote TEXT,
  nameGiven TEXT,
  nameNick TEXT,
  height TEXT,
  weight TEXT,
  shootCatch TEXT,
  legendsID TEXT,
  ihdbID TEXT,
  hrefID TEXT,
  firstNHL TEXT,
  lastNHL TEXT,
  firstWHA TEXT,
  lastWHA TEXT,
  pos TEXT,
  birthYear TEXT,
  birthMon TEXT,
  birthDay TEXT,
  birthCountry TEXT,
  birthState TEXT,
  birthCity TEXT,
  deathYear TEXT,
  deathMon TEXT,
  deathDay TEXT,
  deathCountry TEXT,
  deathState TEXT,
  deathCity TEXT
);

-- Table: scoring
CREATE TABLE IF NOT EXISTS scoring (
    playerID TEXT,
  year INTEGER,
  stint INTEGER,
  tmID TEXT,
  lgID TEXT,
  pos TEXT,
  GP DECIMAL,
  G DECIMAL,
  A DECIMAL,
  Pts DECIMAL,
  PIM DECIMAL,
  p_n TEXT,
  PPG TEXT,
  PPA TEXT,
  SHG TEXT,
  SHA TEXT,
  GWG TEXT,
  GTG TEXT,
  SOG TEXT,
  PostGP TEXT,
  PostG TEXT,
  PostA TEXT,
  PostPts TEXT,
  PostPIM TEXT,
  Post_p_n TEXT,
  PostPPG TEXT,
  PostPPA TEXT,
  PostSHG TEXT,
  PostSHA TEXT,
  PostGWG TEXT,
  PostSOG TEXT
);

-- Table: team_half
CREATE TABLE IF NOT EXISTS team_half (
    year INTEGER NOT NULL,
  lgID TEXT,
  tmID TEXT NOT NULL,
  half INTEGER NOT NULL,
  rank INTEGER,
  G INTEGER,
  W INTEGER,
  L INTEGER,
  T INTEGER,
  GF INTEGER,
  GA INTEGER
);

