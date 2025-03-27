# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="talkingdata"    # Name of the new database
TABLE_NAME="app_all"
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
    app_id BIGINT NOT NULL PRIMARY KEY
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE app_events (
    event_id INTEGER NOT NULL,
    app_id BIGINT NOT NULL,
    is_installed INTEGER NOT NULL,
    is_active INTEGER NOT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY app_events FROM '$1/data/$DB_NAME/app_events.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE app_events_relevant
(
    event_id INTEGER NOT NULL,
    app_id BIGINT NOT NULL,
    is_installed INTEGER DEFAULT NULL,
    is_active INTEGER DEFAULT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY app_events_relevant FROM '$1/data/$DB_NAME/app_events_relevant.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE events
(
    event_id INTEGER NOT NULL,
    device_id BIGINT DEFAULT NULL,
    timestamp timestamp DEFAULT NULL,
    longitude REAL DEFAULT NULL,
    latitude REAL DEFAULT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY events FROM '$1/data/$DB_NAME/events.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE events_relevant
(
    event_id INTEGER NOT NULL,
    device_id BIGINT DEFAULT NULL,
    timestamp BIGINT NOT NULL,
    longitude REAL NOT NULL,
    latitude REAL NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY events_relevant FROM '$1/data/$DB_NAME/events_relevant.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE sample_submission
(
    device_id BIGINT NOT NULL PRIMARY KEY,
    F23_ REAL DEFAULT NULL,
    F24_26 REAL DEFAULT NULL,
    F27_28 REAL DEFAULT NULL,
    F29_32 REAL DEFAULT NULL,
    F33_42 REAL DEFAULT NULL,
    F43_ REAL DEFAULT NULL,
    M22_ REAL DEFAULT NULL,
    M23_26 REAL DEFAULT NULL,
    M27_28 REAL DEFAULT NULL,
    M29_31 REAL DEFAULT NULL,
    M32_38 REAL DEFAULT NULL,
    M39_ REAL DEFAULT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY sample_submission FROM '$1/data/$DB_NAME/sample_submission.csv' DELIMITER ',' CSV HEADER;"
