-- Schema definitions for books
-- Auto-extracted from sources/books/postgres.sh

-- Table: address
CREATE TABLE IF NOT EXISTS address (
    address_id SERIAL PRIMARY KEY,
    street_number TEXT,
    street_name TEXT,
    city TEXT,
    country_id INTEGER
);

-- Table: cust_order
CREATE TABLE IF NOT EXISTS cust_order (
    order_id SERIAL PRIMARY KEY,
    order_date TIMESTAMP,
    customer_id INTEGER,
    shipping_method_id INTEGER,
    dest_address_id INTEGER
);

-- Table: customer_address
CREATE TABLE IF NOT EXISTS customer_address (
    customer_id INTEGER,
    address_id INTEGER,
    status_id INTEGER,
    PRIMARY KEY (customer_id, address_id)
);

-- Table: order_history
CREATE TABLE IF NOT EXISTS order_history (
    history_id SERIAL PRIMARY KEY,
    order_id INTEGER,
    status_id INTEGER,
    status_date TIMESTAMP
);

-- Table: order_line
CREATE TABLE IF NOT EXISTS order_line (
    line_id SERIAL PRIMARY KEY,
    order_id INTEGER,
    book_id INTEGER,
    price REAL
);

