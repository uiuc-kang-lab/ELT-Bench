-- Schema definitions for sales
-- Auto-extracted from sources/sales/postgres.sh

-- Table: sale
CREATE TABLE IF NOT EXISTS sale (
    SalesID       SERIAL PRIMARY KEY,
    SalesPersonID INTEGER NOT NULL,
    CustomerID    INTEGER NOT NULL,
    ProductID     INTEGER NOT NULL,
    Quantity      INTEGER NOT NULL
);

