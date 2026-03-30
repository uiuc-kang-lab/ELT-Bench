-- Schema definitions for car_retails
-- Auto-extracted from sources/car_retails/postgres.sh

-- Table: orderdetails
CREATE TABLE IF NOT EXISTS orderdetails (
    orderNumber     INTEGER NOT NULL,
    productCode     TEXT NOT NULL,
    quantityOrdered INTEGER NOT NULL,
    priceEach       REAL NOT NULL,
    orderLineNumber INTEGER NOT NULL
);

-- Table: orders
CREATE TABLE IF NOT EXISTS orders (
    orderNumber    INTEGER NOT NULL PRIMARY KEY,
    orderDate      DATE NOT NULL,
    requiredDate   DATE NOT NULL,
    shippedDate    DATE,
    status         TEXT NOT NULL,
    comments       TEXT,
    customerNumber INTEGER NOT NULL
);

-- Table: payments
CREATE TABLE IF NOT EXISTS payments (
    customerNumber INTEGER NOT NULL,
    checkNumber    TEXT NOT NULL,
    paymentDate    DATE NOT NULL,
    amount         REAL NOT NULL,
    PRIMARY KEY (customerNumber, checkNumber)
);

