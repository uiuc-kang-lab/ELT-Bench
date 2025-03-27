# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="amplitude"    # Name of the new database
TABLE_NAME="event"
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
   device_id TEXT,
    id BIGINT,
    server_upload_time TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    _insert_id INTEGER,
    ad_id INTEGER,
    amplitude_event_type INTEGER,
    amplitude_id BIGINT,
    app BIGINT,
    city INTEGER,
    client_event_time TIMESTAMP WITHOUT TIME ZONE,
    client_upload_time TIMESTAMP WITHOUT TIME ZONE,
    country TEXT,
    data TEXT,
    device_brand INTEGER,
    device_carrier INTEGER,
    device_family INTEGER,
    device_manufacturer INTEGER,
    device_model INTEGER,
    device_type INTEGER,
    dma INTEGER,
    event_properties TEXT,
    event_time TIMESTAMP WITHOUT TIME ZONE,
    event_type TEXT,
    event_type_id BIGINT,
    group_properties TEXT,
    groups TEXT,
    idfa INTEGER,
    ip_address TEXT,
    is_attribution_event BOOLEAN,
    language INTEGER,
    library TEXT,
    location_lat INTEGER,
    location_lng INTEGER,
    os_name INTEGER,
    os_version INTEGER,
    paying INTEGER,
    platform INTEGER,
    processed_time TIMESTAMP WITHOUT TIME ZONE,
    project_name BIGINT,
    region INTEGER,
    sample_rate INTEGER,
    schema BIGINT,
    server_received_time TIMESTAMP WITHOUT TIME ZONE,
    session_id BIGINT,
    start_version INTEGER,
    user_creation_time TIMESTAMP WITHOUT TIME ZONE,
    user_id VARCHAR(100),
    user_properties TEXT,
    uuid TEXT,
    version_name INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

