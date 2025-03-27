# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="microsoft_ads"    # Name of the new database
TABLE_NAME="account_performance_daily_report"
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
    account_id BIGINT,
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    currency_code VARCHAR(10),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(255),
    delivered_match_type VARCHAR(255),
    top_vs_other VARCHAR(255),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE ad_group_performance_daily_report
(
  date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    ad_group_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    language VARCHAR(50),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY ad_group_performance_daily_report FROM '$1/data/$DB_NAME/ad_group_performance_daily_report.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE ad_performance_daily_report
(
   date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    ad_group_id BIGINT,
    ad_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    language VARCHAR(50),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY ad_performance_daily_report FROM '$1/data/$DB_NAME/ad_performance_daily_report.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE campaign_performance_daily_report
(
    date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    budget_association_status VARCHAR(50),
    budget_name VARCHAR(255),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY campaign_performance_daily_report FROM '$1/data/$DB_NAME/campaign_performance_daily_report.csv' DELIMITER ',' CSV HEADER;"

