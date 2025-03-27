# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="marketo"    # Name of the new database
TABLE_NAME="activity_change_data_value"
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
    activity_date TEXT,
    activity_type_id INTEGER,
    api_method_name INTEGER,
    campaign_id INTEGER,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    modifying_user INTEGER,
    new_value TEXT,
    old_value TEXT,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    reason TEXT,
    request_id INTEGER,
    source TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE activity_open_email
(
   activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    choice_number INTEGER,
    device TEXT,
    email_template_id INTEGER,
    id INTEGER PRIMARY KEY,
    is_mobile_device BOOLEAN,
    lead_id INTEGER,
    platform TEXT,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    step_id INTEGER,
    user_agent TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY activity_open_email FROM '$1/data/$DB_NAME/activity_open_email.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE activity_send_email
(
   activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    choice_number INTEGER,
    email_template_id INTEGER,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    primary_attribute_value_id INTEGER,
    primary_attribute_value TEXT,
    step_id INTEGER,
    action_result TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY activity_send_email FROM '$1/data/$DB_NAME/activity_send_email.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE activity_unsubscribe_email
(
   activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    client_ip_address TEXT,
    email_template_id INTEGER,
    form_fields TEXT,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    query_parameters TEXT,
    referrer_url TEXT,
    user_agent TEXT,
    webform_id INTEGER,
    webpage_id INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY activity_unsubscribe_email FROM '$1/data/$DB_NAME/activity_unsubscribe_email.csv' DELIMITER ',' CSV HEADER;"
