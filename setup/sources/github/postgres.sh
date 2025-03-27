# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="github"    # Name of the new database
TABLE_NAME="issue"
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
   id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    body TEXT,
    closed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    locked BOOLEAN,
    milestone_id INTEGER,
    number INTEGER,
    pull_request BOOLEAN,
    repository_id INTEGER,
    state TEXT,
    title TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    user_id INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE issue_closed_history
(
   issue_id INTEGER PRIMARY KEY,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    actor_id INTEGER,
    closed BOOLEAN,
    commit_sha INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY issue_closed_history FROM '$1/data/$DB_NAME/issue_closed_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE pull_request
(
   id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    base_label TEXT,
    base_ref TEXT,
    base_repo_id INTEGER,
    base_sha TEXT,
    base_user_id INTEGER,
    head_label TEXT,
    head_ref TEXT,
    head_repo_id INTEGER,
    head_sha TEXT,
    head_user_id INTEGER,
    issue_id INTEGER,
    merge_commit_sha TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY pull_request FROM '$1/data/$DB_NAME/pull_request.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE users
(
   id INTEGER PRIMARY KEY,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    bio TEXT,
    blog TEXT,
    company TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    hireable BOOLEAN,
    location TEXT,
    login TEXT,
    name TEXT,
    site_admin BOOLEAN,
    type TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY users FROM '$1/data/$DB_NAME/users.csv' DELIMITER ',' CSV HEADER;"
