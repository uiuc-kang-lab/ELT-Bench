# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="apple_store"    # Name of the new database
TABLE_NAME="app_store_device"
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
   app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    impressions INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    impressions_unique_device INTEGER,
    page_views INTEGER,
    page_views_unique_device INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE crashes_app_version
(
   app_id INTEGER,
    app_version TEXT,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    meets_threshold BOOLEAN,
    crashes INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY crashes_app_version FROM '$1/data/$DB_NAME/crashes_app_version.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE downloads_device
(
   app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    first_time_downloads INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    redownloads INTEGER,
    total_downloads INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY downloads_device FROM '$1/data/$DB_NAME/downloads_device.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE downloads_platform_version
(
   app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    platform_version TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    first_time_downloads INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    redownloads INTEGER,
    total_downloads INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY downloads_platform_version FROM '$1/data/$DB_NAME/downloads_platform_version.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE sales_subscription_events
(
   _filename TEXT,
    account_number INTEGER,
    vendor_number INTEGER,
    _index INTEGER,
    event_date DATE,
    app_name TEXT,
    days_canceled INTEGER,
    subscription_name TEXT,
    consecutive_paid_periods INTEGER,
    previous_subscription_name INTEGER,
    cancellation_reason TEXT,
    proceeds_reason TEXT,
    subscription_apple_id INTEGER,
    standard_subscription_duration TEXT,
    original_start_date DATE,
    device TEXT,
    days_before_canceling INTEGER,
    quantity INTEGER,
    marketing_opt_in_duration INTEGER,
    promotional_offer_name INTEGER,
    state TEXT,
    previous_subscription_apple_id INTEGER,
    event TEXT,
    subscription_group_id INTEGER,
    country TEXT,
    promotional_offer_id INTEGER,
    app_apple_id INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    subscription_offer_type INTEGER,
    subscription_offer_duration INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY sales_subscription_events FROM '$1/data/$DB_NAME/sales_subscription_events.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE usage_platform_version
(
   app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    platform_version TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    installations INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    sessions INTEGER,
    active_devices INTEGER,
    active_devices_last_30_days INTEGER,
    deletions INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY usage_platform_version FROM '$1/data/$DB_NAME/usage_platform_version.csv' DELIMITER ',' CSV HEADER;"
