# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="coinmarketcap"    # Name of the new database
TABLE_NAME="historical"
DB_PORT=5433            # Port to connect to PostgreSQL
HOST="localhost"        # Hostname of PostgreSQL server

# Create the database
echo "Creating database '$DB_NAME'..."
PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -c "DROP DATABASE if exists $DB_NAME;"
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
    date               DATE NOT NULL,
    coin_id            INTEGER NOT NULL,
    cmc_rank           INTEGER,
    market_cap         REAL,
    price              REAL,
    open               REAL,
    high               REAL,
    low                REAL,
    close              REAL,
    time_high          TEXT,
    time_low           TEXT,
    volume_24h         REAL,
    percent_change_1h  REAL,
    percent_change_24h REAL,
    percent_change_7d  REAL,
    circulating_supply REAL,
    total_supply       REAL,
    max_supply         REAL,
    num_market_pairs   INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"
