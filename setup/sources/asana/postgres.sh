# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="asana"    # Name of the new database
TABLE_NAME="tag"
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
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    color INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    message INTEGER,
    name TEXT,
    notes INTEGER,
    workspace_id BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE task
(
   id BIGINT PRIMARY KEY,
    assignee_id BIGINT,
    completed BOOLEAN,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    completed_by_id BIGINT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    due_on TIMESTAMP WITHOUT TIME ZONE,
    due_at TIMESTAMP WITHOUT TIME ZONE,
    modified_at TIMESTAMP WITHOUT TIME ZONE,
    name TEXT,
    parent_id BIGINT,
    start_on TIMESTAMP WITHOUT TIME ZONE,
    notes TEXT,
    workspace_id BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY task FROM '$1/data/$DB_NAME/task.csv' DELIMITER ',' CSV HEADER;"
