# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="airline"    # Name of the new database
TABLE_NAME="airlines"
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
    FL_DATE               TEXT,
    OP_CARRIER_AIRLINE_ID INTEGER,
    TAIL_NUM              TEXT,
    OP_CARRIER_FL_NUM     INTEGER,
    ORIGIN_AIRPORT_ID     INTEGER,
    ORIGIN_AIRPORT_SEQ_ID INTEGER,
    ORIGIN_CITY_MARKET_ID INTEGER,
    ORIGIN                TEXT,
    DEST_AIRPORT_ID       INTEGER,
    DEST_AIRPORT_SEQ_ID   INTEGER,
    DEST_CITY_MARKET_ID   INTEGER,
    DEST                  TEXT,
    CRS_DEP_TIME          INTEGER,
    DEP_TIME              INTEGER,
    DEP_DELAY             INTEGER,
    DEP_DELAY_NEW         INTEGER,
    ARR_TIME              INTEGER,
    ARR_DELAY             INTEGER,
    ARR_DELAY_NEW         INTEGER,
    CANCELLED             INTEGER,
    CANCELLATION_CODE     TEXT,
    CRS_ELAPSED_TIME      INTEGER,
    ACTUAL_ELAPSED_TIME   INTEGER,
    CARRIER_DELAY         INTEGER,
    WEATHER_DELAY         INTEGER,
    NAS_DELAY             INTEGER,
    SECURITY_DELAY        INTEGER,
    LATE_AIRCRAFT_DELAY   INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"
