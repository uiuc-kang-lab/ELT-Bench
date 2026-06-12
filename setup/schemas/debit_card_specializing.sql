-- Schema definitions for debit_card_specializing
-- Auto-extracted from sources/debit_card_specializing/postgres.sh

-- Table: transactions_1k
CREATE TABLE IF NOT EXISTS transactions_1k (
    TransactionID SERIAL PRIMARY KEY,
    Date          DATE,
    Time          TEXT,
    CustomerID    INTEGER,
    CardID        INTEGER,
    GasStationID  INTEGER,
    ProductID     INTEGER,
    Amount        INTEGER,
    Price         REAL
);

-- Table: yearmonth
CREATE TABLE IF NOT EXISTS yearmonth (
    CustomerID  INTEGER NOT NULL,
    Date        CHAR(6) NOT NULL,
    Consumption REAL,
    PRIMARY KEY (Date, CustomerID)
);

