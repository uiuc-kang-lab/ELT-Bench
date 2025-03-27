# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="superstore"    # Name of the new database
TABLE_NAME="central_superstore"
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
CREATE TABLE $TABLE_NAME(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE east_superstore(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY east_superstore FROM '$1/data/$DB_NAME/east_superstore.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE south_superstore(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY south_superstore FROM '$1/data/$DB_NAME/south_superstore.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE west_superstore(
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
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY west_superstore FROM '$1/data/$DB_NAME/west_superstore.csv' DELIMITER ',' CSV HEADER;"
