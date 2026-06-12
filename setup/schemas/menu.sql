-- Schema definitions for menu
-- Auto-extracted from sources/menu/postgres.sh

-- Table: menuitem
CREATE TABLE IF NOT EXISTS menuitem (
    id           SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing integers
    menu_page_id INTEGER,
    price        REAL,
    high_price   REAL,
    dish_id      INTEGER,
    created_at   TIMESTAMP,  -- Use TIMESTAMP for date/time fields
    updated_at   TIMESTAMP,  -- Use TIMESTAMP for date/time fields
    xpos         REAL,
    ypos         REAL
);

