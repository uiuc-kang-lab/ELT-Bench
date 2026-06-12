-- Schema definitions for financial
-- Auto-extracted from sources/financial/postgres.sh

-- Table: account
CREATE TABLE IF NOT EXISTS account (
    account_id  INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    district_id INTEGER DEFAULT 0 NOT NULL,
    frequency   TEXT NOT NULL,
    date        DATE NOT NULL
);

-- Table: loan
CREATE TABLE IF NOT EXISTS loan (
    loan_id    INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    date       DATE NOT NULL,
    amount     INTEGER NOT NULL,
    duration   INTEGER NOT NULL,
    payments   REAL NOT NULL,
    status     TEXT NOT NULL
);

-- Table: orders
CREATE TABLE IF NOT EXISTS orders (
    order_id   INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    bank_to    TEXT NOT NULL,
    account_to INTEGER NOT NULL,
    amount     REAL NOT NULL,
    k_symbol   TEXT
);

-- Table: trans
CREATE TABLE IF NOT EXISTS trans (
    trans_id   INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER DEFAULT 0 NOT NULL,
    date       DATE NOT NULL,
    type       TEXT NOT NULL,
    operation  TEXT,
    amount     INTEGER NOT NULL,
    balance    INTEGER NOT NULL,
    k_symbol   TEXT,
    bank       TEXT,
    account    INTEGER
);

