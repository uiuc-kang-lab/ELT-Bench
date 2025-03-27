# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="pardot"    # Name of the new database
TABLE_NAME="list"
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
   id BIGINT PRIMARY KEY,
    _fivetran_synced VARCHAR,
    created_at VARCHAR,
    is_crm_visible BOOLEAN,
    is_dynamic BOOLEAN,
    is_public BOOLEAN,
    updated_at VARCHAR,
    name VARCHAR,
    title VARCHAR,
    description VARCHAR
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE visitor
(
   id BIGINT PRIMARY KEY,
    _fivetran_synced VARCHAR,
    campaign_parameter BIGINT,
    content_parameter BIGINT,
    created_at VARCHAR,
    medium_parameter BIGINT,
    page_view_count BIGINT,
    prospect_id BIGINT,
    source_parameter BIGINT,
    term_parameter BIGINT,
    updated_at VARCHAR,
    hostname VARCHAR,
    ip_address VARCHAR
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY visitor FROM '$1/data/$DB_NAME/visitor.csv' DELIMITER ',' CSV HEADER;"
