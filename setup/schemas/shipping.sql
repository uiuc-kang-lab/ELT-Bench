-- Schema definitions for shipping
-- Auto-extracted from sources/shipping/postgres.sh

-- Table: shipment
CREATE TABLE IF NOT EXISTS shipment (
    ship_id   SERIAL PRIMARY KEY,
    cust_id   INTEGER,
    weight    REAL,
    truck_id  INTEGER,
    driver_id INTEGER,
    city_id   INTEGER,
    ship_date DATE
);

