# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="mailchimp"    # Name of the new database
TABLE_NAME="campaign_recipient_activity"
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
    action TEXT,
    campaign_id TEXT,
    member_id TEXT,
    timestamp TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    bounce_type INTEGER,
    combination_id INTEGER,
    ip TEXT,
    list_id TEXT,
    url TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE member
(
   id TEXT,
    list_id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    country_code TEXT,
    dstoff DOUBLE PRECISION,
    email_address TEXT,
    email_client TEXT,
    email_type TEXT,
    gmtoff DOUBLE PRECISION,
    ip_opt TEXT,
    ip_signup TEXT,
    language TEXT,
    last_changed TIMESTAMP WITHOUT TIME ZONE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    member_rating INTEGER,
    merge_fname TEXT,
    merge_lname TEXT,
    status TEXT,
    timestamp_opt TIMESTAMP WITHOUT TIME ZONE,
    timestamp_signup TIMESTAMP WITHOUT TIME ZONE,
    timezone TEXT,
    unique_email_id TEXT,
    vip BOOLEAN
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY member FROM '$1/data/$DB_NAME/member.csv' DELIMITER ',' CSV HEADER;"
