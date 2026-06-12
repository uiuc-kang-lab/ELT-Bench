-- Schema definitions for superstore
-- Auto-extracted from sources/superstore/postgres.sh

-- Table: central_superstore
CREATE TABLE IF NOT EXISTS central_superstore (
    Row_ID INTEGER PRIMARY KEY,
  Order_ID TEXT,
  Order_Date DATE,
  Ship_Date DATE,
  Ship_Mode TEXT,
  Customer_ID TEXT,
  Region TEXT,
  Product_ID TEXT,
  Sales REAL,
  Quantity INTEGER,
  Discount REAL,
  Profit REAL
);

-- Table: east_superstore
CREATE TABLE IF NOT EXISTS east_superstore (
    Row_ID INTEGER PRIMARY KEY,
  Order_ID TEXT,
  Order_Date DATE,
  Ship_Date DATE,
  Ship_Mode TEXT,
  Customer_ID TEXT,
  Region TEXT,
  Product_ID TEXT,
  Sales REAL,
  Quantity INTEGER,
  Discount REAL,
  Profit REAL
);

-- Table: south_superstore
CREATE TABLE IF NOT EXISTS south_superstore (
    Row_ID INTEGER PRIMARY KEY,
  Order_ID TEXT,
  Order_Date DATE,
  Ship_Date DATE,
  Ship_Mode TEXT,
  Customer_ID TEXT,
  Region TEXT,
  Product_ID TEXT,
  Sales REAL,
  Quantity INTEGER,
  Discount REAL,
  Profit REAL
);

-- Table: west_superstore
CREATE TABLE IF NOT EXISTS west_superstore (
    Row_ID INTEGER PRIMARY KEY,
  Order_ID TEXT,
  Order_Date DATE,
  Ship_Date DATE,
  Ship_Mode TEXT,
  Customer_ID TEXT,
  Region TEXT,
  Product_ID TEXT,
  Sales REAL,
  Quantity INTEGER,
  Discount REAL,
  Profit REAL
);

