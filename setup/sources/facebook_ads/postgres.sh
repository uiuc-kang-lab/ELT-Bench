# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="facebook_ads"    # Name of the new database
TABLE_NAME="ad_history"
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
    id BIGINT,
    account_id BIGINT,
    ad_set_id BIGINT,
    campaign_id BIGINT,
    creative_id BIGINT,
    name VARCHAR(255),
    _fivetran_synced TIMESTAMP,
    updated_time TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE basic_ad_action_values
(
    ad_id BIGINT,
    date DATE,
    _fivetran_id VARCHAR(255),
    index INT,
    action_type VARCHAR(255),
    value DECIMAL(15, 2),
    _fivetran_synced TIMESTAMP,
    _7_d_click DECIMAL(15, 2)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY basic_ad_action_values FROM '$1/data/$DB_NAME/basic_ad_action_values.csv' DELIMITER ',' CSV HEADER;"

