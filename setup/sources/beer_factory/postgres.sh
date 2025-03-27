# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="beer_factory"    # Name of the new database
TABLE_NAME="rootbeer"
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
    RootBeerID    SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing integer IDs
    BrandID       INTEGER NOT NULL,
    ContainerType TEXT NOT NULL,
    LocationID    INTEGER NOT NULL,
    PurchaseDate  DATE NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE transaction
(
    TransactionID    SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing ID
    CreditCardNumber BIGINT NOT NULL,     -- Use BIGINT for credit card numbers
    CustomerID       INTEGER NOT NULL,
    TransactionDate  DATE NOT NULL,
    CreditCardType   TEXT NOT NULL,
    LocationID       INTEGER NOT NULL,
    RootBeerID       INTEGER NOT NULL,
    PurchasePrice    REAL NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY transaction FROM '$1/data/$DB_NAME/transaction.csv' DELIMITER ',' CSV HEADER;"
