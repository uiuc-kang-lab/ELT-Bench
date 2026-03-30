-- Schema definitions for retail_world
-- Auto-extracted from sources/retail_world/postgres.sh

-- Table: order_details
CREATE TABLE IF NOT EXISTS order_details (
    OrderDetailID SERIAL PRIMARY KEY,
  OrderID INTEGER,
  ProductID INTEGER,
  Quantity INTEGER
);

-- Table: orders
CREATE TABLE IF NOT EXISTS orders (
    OrderID SERIAL PRIMARY KEY,
  CustomerID INTEGER,
  EmployeeID INTEGER,
  OrderDate TIMESTAMP,
  ShipperID INTEGER
);

