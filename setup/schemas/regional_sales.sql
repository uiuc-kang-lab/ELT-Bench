-- Schema definitions for regional_sales
-- Auto-extracted from sources/regional_sales/postgres.sh

-- Table: sales_orders
CREATE TABLE IF NOT EXISTS sales_orders (
    ordernumber TEXT PRIMARY KEY,
  sales_channel TEXT,
  warehousecode TEXT,
  procureddate DATE,
  orderdate DATE,
  shipdate DATE,
  deliverydate DATE,
  currencycode TEXT,
  salesteamid INTEGER,
  customerid INTEGER,
  storeid INTEGER,
  productid INTEGER,
  order_quantity INTEGER,
  discount_applied REAL,
  unit_price TEXT,
  unit_cost TEXT
);

