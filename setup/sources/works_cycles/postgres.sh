# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="works_cycles"    # Name of the new database
TABLE_NAME="bill_of_materials"
DB_PORT=5433            # Port to connect to PostgreSQL
HOST="localhost"        # Hostname of PostgreSQL server

# Create the database
echo "Creating database '$DB_NAME'..."
PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -c "DROP DATABASE IF EXISTS $DB_NAME;"
PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -c "CREATE DATABASE $DB_NAME;"

# Check if the database was created successfully
if [ $? -eq 0 ]; then
  echo "Database '$DB_NAME' created successfully!"
else
  echo "Failed to create database '$DB_NAME'."
fi

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE $TABLE_NAME
(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE credit_card
(
   CreditCardID INTEGER,
    CardType TEXT,
    CardNumber TEXT,
    ExpMonth INTEGER,
    ExpYear INTEGER,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY credit_card FROM '$1/data/$DB_NAME/credit_card.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE email_address
(
   BusinessEntityID INTEGER,
    EmailAddressID INTEGER,
    EmailAddress TEXT,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY email_address FROM '$1/data/$DB_NAME/email_address.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE password
(
  BusinessEntityID INTEGER,
  PasswordHash TEXT,
  PasswordSalt TEXT,
  rowguid TEXT,
  ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY password FROM '$1/data/$DB_NAME/password.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE person_credit_card
(
  BusinessEntityID INTEGER,
  CreditCardID INTEGER,
  ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY person_credit_card FROM '$1/data/$DB_NAME/person_credit_card.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE product_cost_history
(
  ProductID INTEGER,
  StartDate DATE,
  EndDate DATE,
  StandardCost REAL,
  ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY product_cost_history FROM '$1/data/$DB_NAME/product_cost_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE product_inventory
(
    ProductID INTEGER,
    LocationID INTEGER,
    Shelf TEXT,
    Bin INTEGER,
    Quantity INTEGER,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY product_inventory FROM '$1/data/$DB_NAME/product_inventory.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE product_list_price_history
(
    ProductID INTEGER,
    StartDate DATE,
    EndDate DATE,
    ListPrice REAL,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY product_list_price_history FROM '$1/data/$DB_NAME/product_list_price_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE product_model_product_description_culture
(
    ProductModelID INTEGER,
    ProductDescriptionID INTEGER,
    CultureID TEXT,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY product_model_product_description_culture FROM '$1/data/$DB_NAME/product_model_product_description_culture.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE product_vendor
(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY product_vendor FROM '$1/data/$DB_NAME/product_vendor.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE purchase_order_detail
(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY purchase_order_detail FROM '$1/data/$DB_NAME/purchase_order_detail.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE purchase_order_header
(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY purchase_order_header FROM '$1/data/$DB_NAME/purchase_order_header.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE sales_person_quota_history
(
    BusinessEntityID INTEGER,
    QuotaDate TIMESTAMP,
    SalesQuota REAL,
    rowguid TEXT,
    ModifiedDate TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY sales_person_quota_history FROM '$1/data/$DB_NAME/sales_person_quota_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE transaction_history
(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY transaction_history FROM '$1/data/$DB_NAME/transaction_history.csv' DELIMITER ',' CSV HEADER;"
