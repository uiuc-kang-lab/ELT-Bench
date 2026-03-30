-- Schema definitions for coinmarketcap
-- Auto-extracted from sources/coinmarketcap/postgres.sh

-- Table: historical
CREATE TABLE IF NOT EXISTS historical (
    date               DATE NOT NULL,
    coin_id            INTEGER NOT NULL,
    cmc_rank           INTEGER,
    market_cap         REAL,
    price              REAL,
    open               REAL,
    high               REAL,
    low                REAL,
    close              REAL,
    time_high          TEXT,
    time_low           TEXT,
    volume_24h         REAL,
    percent_change_1h  REAL,
    percent_change_24h REAL,
    percent_change_7d  REAL,
    circulating_supply REAL,
    total_supply       REAL,
    max_supply         REAL,
    num_market_pairs   INTEGER
);

