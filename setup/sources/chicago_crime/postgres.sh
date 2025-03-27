# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="chicago_crime"    # Name of the new database
TABLE_NAME="crime"
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
    report_no            SERIAL PRIMARY KEY,
    case_number          TEXT NOT NULL,
    date                 TEXT NOT NULL,
    block                TEXT,
    iucr_no              TEXT NOT NULL,
    location_description TEXT,
    arrest               TEXT,
    domestic             TEXT,
    beat                 INTEGER,
    district_no          INTEGER,
    ward_no              INTEGER,
    community_area_no    INTEGER,
    fbi_code_no          TEXT,
    latitude             TEXT,
    longitude            TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE iucr (
    iucr_no               TEXT PRIMARY KEY,
    primary_description   TEXT NOT NULL,
    secondary_description TEXT,
    index_code            TEXT
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY iucr FROM '$1/data/$DB_NAME/iucr.csv' DELIMITER ',' CSV HEADER;"
