-- Schema definitions for works_cycles
-- Auto-extracted from sources/works_cycles/postgres.sh

-- Table: bill_of_materials
CREATE TABLE IF NOT EXISTS bill_of_materials (
    BillOfMaterialsID INTEGER,
  ProductAssemblyID INTEGER,
  ComponentID INTEGER,
  StartDate TIMESTAMP,
  EndDate TIMESTAMP,
  UnitMeasureCode TEXT,
  BOMLevel INTEGER,
  PerAssemblyQty REAL,
  ModifiedDate TIMESTAMP
);

-- Table: credit_card
CREATE TABLE IF NOT EXISTS credit_card (
    CreditCardID INTEGER,
    CardType TEXT,
    CardNumber TEXT,
    ExpMonth INTEGER,
    ExpYear INTEGER,
    ModifiedDate TIMESTAMP
);

-- Table: email_address
CREATE TABLE IF NOT EXISTS email_address (
    BusinessEntityID INTEGER,
    EmailAddressID INTEGER,
    EmailAddress TEXT,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);

-- Table: password
CREATE TABLE IF NOT EXISTS password (
    BusinessEntityID INTEGER,
  PasswordHash TEXT,
  PasswordSalt TEXT,
  rowguid TEXT,
  ModifiedDate TIMESTAMP
);

-- Table: person_credit_card
CREATE TABLE IF NOT EXISTS person_credit_card (
    BusinessEntityID INTEGER,
  CreditCardID INTEGER,
  ModifiedDate TIMESTAMP
);

-- Table: product_cost_history
CREATE TABLE IF NOT EXISTS product_cost_history (
    ProductID INTEGER,
  StartDate DATE,
  EndDate DATE,
  StandardCost REAL,
  ModifiedDate TIMESTAMP
);

-- Table: product_inventory
CREATE TABLE IF NOT EXISTS product_inventory (
    ProductID INTEGER,
    LocationID INTEGER,
    Shelf TEXT,
    Bin INTEGER,
    Quantity INTEGER,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);

-- Table: product_list_price_history
CREATE TABLE IF NOT EXISTS product_list_price_history (
    ProductID INTEGER,
    StartDate DATE,
    EndDate DATE,
    ListPrice REAL,
    ModifiedDate TIMESTAMP
);

-- Table: product_model_product_description_culture
CREATE TABLE IF NOT EXISTS product_model_product_description_culture (
    ProductModelID INTEGER,
    ProductDescriptionID INTEGER,
    CultureID TEXT,
    ModifiedDate TIMESTAMP
);

-- Table: product_vendor
CREATE TABLE IF NOT EXISTS product_vendor (
    ProductID INTEGER,
  BusinessEntityID INTEGER,
  AverageLeadTime INTEGER,
  StandardPrice REAL,
  LastReceiptCost REAL,
  LastReceiptDate TIMESTAMP,
  MinOrderQty INTEGER,
  MaxOrderQty INTEGER,
  OnOrderQty INTEGER,
  UnitMeasureCode TEXT,
  ModifiedDate TIMESTAMP
);

-- Table: purchase_order_detail
CREATE TABLE IF NOT EXISTS purchase_order_detail (
    PurchaseOrderID INTEGER,
    PurchaseOrderDetailID SERIAL,
    DueDate TIMESTAMP,
    OrderQty INTEGER,
    ProductID INTEGER,
    UnitPrice REAL,
    LineTotal REAL,
    ReceivedQty REAL,
    RejectedQty REAL,
    StockedQty REAL,
    ModifiedDate TIMESTAMP
);

-- Table: purchase_order_header
CREATE TABLE IF NOT EXISTS purchase_order_header (
    PurchaseOrderID SERIAL,
    RevisionNumber INTEGER,
    Status INTEGER,
    EmployeeID INTEGER,
    VendorID INTEGER,
    ShipMethodID INTEGER,
    OrderDate TIMESTAMP,
    ShipDate TIMESTAMP,
    SubTotal REAL,
    TaxAmt REAL,
    Freight REAL,
    TotalDue REAL,
    ModifiedDate TIMESTAMP
);

-- Table: sales_person_quota_history
CREATE TABLE IF NOT EXISTS sales_person_quota_history (
    BusinessEntityID INTEGER,
    QuotaDate TIMESTAMP,
    SalesQuota REAL,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);

-- Table: transaction_history
CREATE TABLE IF NOT EXISTS transaction_history (
    TransactionID SERIAL,
    ProductID INTEGER,
    ReferenceOrderID INTEGER,
    ReferenceOrderLineID INTEGER,
    TransactionDate TIMESTAMP,
    TransactionType TEXT,
    Quantity INTEGER,
    ActualCost REAL,
    ModifiedDate TIMESTAMP
);

