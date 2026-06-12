-- Schema definitions for legislator
-- Auto-extracted from sources/legislator/postgres.sh

-- Table: legislator_current
CREATE TABLE IF NOT EXISTS legislator_current (
    ballotpedia_id      TEXT,
    bioguide_id         TEXT,
    birthday_bio        DATE,
    cspan_id            REAL,
    fec_id              TEXT,
    first_name          TEXT,
    gender_bio          TEXT,
    google_entity_id_id TEXT,
    govtrack_id         INTEGER,
    house_history_id    REAL,
    icpsr_id            REAL,
    last_name           TEXT,
    lis_id              TEXT,
    maplight_id         REAL,
    middle_name         TEXT,
    nickname_name       TEXT,
    official_full_name  TEXT,
    opensecrets_id      TEXT,
    religion_bio        TEXT,
    suffix_name         TEXT,
    thomas_id           TEXT,
    votesmart_id        REAL,
    wikidata_id         TEXT,
    wikipedia_id        TEXT
);

