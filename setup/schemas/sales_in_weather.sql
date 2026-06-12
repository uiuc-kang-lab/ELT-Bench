-- Schema definitions for sales_in_weather
-- Auto-extracted from sources/sales_in_weather/postgres.sh

-- Table: sales
CREATE TABLE IF NOT EXISTS sales (
    date DATE,
    store_nbr INTEGER,
    item_nbr INTEGER,
    units INTEGER,
    PRIMARY KEY (store_nbr, date, item_nbr)
);

