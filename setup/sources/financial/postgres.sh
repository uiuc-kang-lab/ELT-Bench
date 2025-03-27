# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="financial"    # Name of the new database
TABLE_NAME="account"
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
    account_id  INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    district_id INTEGER DEFAULT 0 NOT NULL,
    frequency   TEXT NOT NULL,
    date        DATE NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE loan (
    loan_id    INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    date       DATE NOT NULL,
    amount     INTEGER NOT NULL,
    duration   INTEGER NOT NULL,
    payments   REAL NOT NULL,
    status     TEXT NOT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY loan FROM '$1/data/$DB_NAME/loan.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE orders
(
    order_id   INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    bank_to    TEXT NOT NULL,
    account_to INTEGER NOT NULL,
    amount     REAL NOT NULL,
    k_symbol   TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY orders FROM '$1/data/$DB_NAME/orders.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE trans (
   trans_id   INTEGER DEFAULT 0 NOT NULL PRIMARY KEY,
    account_id INTEGER DEFAULT 0 NOT NULL,
    date       DATE NOT NULL,
    type       TEXT NOT NULL,
    operation  TEXT,
    amount     INTEGER NOT NULL,
    balance    INTEGER NOT NULL,
    k_symbol   TEXT,
    bank       TEXT,
    account    INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY trans FROM '$1/data/$DB_NAME/trans.csv' DELIMITER ',' CSV HEADER;"
