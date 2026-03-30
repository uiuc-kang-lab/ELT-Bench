-- Schema definitions for language_corpus
-- Auto-extracted from sources/language_corpus/postgres.sh

-- Table: biwords
CREATE TABLE IF NOT EXISTS biwords (
    lid          INTEGER ,
    w1st         INTEGER ,
    w2nd         INTEGER,
    occurrences  INTEGER DEFAULT 0, 
    PRIMARY KEY (lid, w1st, w2nd)
);

-- Table: pages_words
CREATE TABLE IF NOT EXISTS pages_words (
    pid          INTEGER,
    wid          INTEGER,
    occurrences  INTEGER DEFAULT 0,
    PRIMARY KEY (pid, wid)
);

