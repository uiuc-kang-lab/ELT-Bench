-- Schema definitions for beer_factory
-- Auto-extracted from sources/beer_factory/postgres.sh

-- Table: rootbeer
CREATE TABLE IF NOT EXISTS rootbeer (
    RootBeerID    SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing integer IDs
    BrandID       INTEGER NOT NULL,
    ContainerType TEXT NOT NULL,
    LocationID    INTEGER NOT NULL,
    PurchaseDate  DATE NOT NULL
);

-- Table: transaction
CREATE TABLE IF NOT EXISTS transaction (
    TransactionID    SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing ID
    CreditCardNumber BIGINT NOT NULL,     -- Use BIGINT for credit card numbers
    CustomerID       INTEGER NOT NULL,
    TransactionDate  DATE NOT NULL,
    CreditCardType   TEXT NOT NULL,
    LocationID       INTEGER NOT NULL,
    RootBeerID       INTEGER NOT NULL,
    PurchasePrice    REAL NOT NULL
);

