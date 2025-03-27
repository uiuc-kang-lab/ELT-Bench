# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="pinterest"    # Name of the new database
TABLE_NAME="advertiser_report"
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
   date DATE,
    advertiser_id TEXT,
    _fivetran_synced TIMESTAMP,  
    impression_1 BIGINT,
    impression_2 BIGINT,
    clickthrough_1 BIGINT,
    clickthrough_2 BIGINT,
    spend_in_micro_dollar BIGINT,
    total_conversions BIGINT,
    total_conversions_quantity BIGINT,
    total_conversions_value_in_micro_dollar BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE campaign_history
(
   id TEXT,
    created_time TEXT,
    name TEXT,
    status TEXT,
    _fivetran_synced TEXT,
    advertiser_id TEXT,
    default_ad_group_budget_in_micro_currency BIGINT,
    is_automated_campaign BOOLEAN,
    is_campaign_budget_optimization BOOLEAN,
    is_flexible_daily_budgets BOOLEAN
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY campaign_history FROM '$1/data/$DB_NAME/campaign_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE campaign_report
(
   date DATE,
    campaign_id TEXT,
    campaign_name TEXT,
    campaign_status TEXT,
    advertiser_id TEXT,
    _fivetran_synced TIMESTAMP,
    impression_1 BIGINT,
    impression_2 BIGINT,
    clickthrough_1 BIGINT,
    clickthrough_2 BIGINT,
    spend_in_micro_dollar BIGINT,
    total_conversions BIGINT,
    total_conversions_quantity BIGINT,
    total_conversions_value_in_micro_dollar BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY campaign_report FROM '$1/data/$DB_NAME/campaign_report.csv' DELIMITER ',' CSV HEADER;"
