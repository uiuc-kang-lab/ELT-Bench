# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="tiktok_ads"    # Name of the new database
TABLE_NAME="tiktok_ad_report_hourly"
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
   ad_id INTEGER,
    stat_time_hour TIMESTAMP WITHOUT TIME ZONE,
    cost_per_conversion DOUBLE PRECISION,
    cpc DOUBLE PRECISION,
    video_play_actions INTEGER,
    conversion_rate INTEGER,
    video_views_p_75 INTEGER,
    result INTEGER,
    video_views_p_50 INTEGER,
    impressions INTEGER,
    comments INTEGER,
    real_time_cost_per_result DOUBLE PRECISION,
    conversion INTEGER,
    real_time_result INTEGER,
    video_views_p_100 INTEGER,
    shares INTEGER,
    real_time_conversion_rate INTEGER,
    cost_per_secondary_goal_result TEXT,
    secondary_goal_result_rate TEXT,
    clicks INTEGER,
    cost_per_1000_reached INTEGER,
    video_views_p_25 INTEGER,
    reach INTEGER,
    real_time_cost_per_conversion DOUBLE PRECISION,
    profile_visits_rate INTEGER,
    average_video_play DOUBLE PRECISION,
    profile_visits INTEGER,
    cpm DOUBLE PRECISION,
    ctr DOUBLE PRECISION,
    video_watched_2_s INTEGER,
    follows INTEGER,
    result_rate INTEGER,
    video_watched_6_s INTEGER,
    secondary_goal_result TEXT,
    cost_per_result DOUBLE PRECISION,
    average_video_play_per_user INTEGER,
    real_time_result_rate INTEGER,
    spend DOUBLE PRECISION,
    likes INTEGER,
    real_time_conversion INTEGER,
    total_purchase_value DOUBLE PRECISION,
    total_sales_lead_value DOUBLE PRECISION,
    _fivetran_synced TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE tiktok_adgroup_report_hourly
(
   adgroup_id INTEGER,
    stat_time_hour TIMESTAMP WITHOUT TIME ZONE,
    cost_per_conversion DOUBLE PRECISION,
    cpc DOUBLE PRECISION,
    video_play_actions INTEGER,
    conversion_rate INTEGER,
    video_views_p_75 INTEGER,
    result INTEGER,
    video_views_p_50 INTEGER,
    impressions INTEGER,
    comments INTEGER,
    real_time_cost_per_result DOUBLE PRECISION,
    conversion INTEGER,
    real_time_result INTEGER,
    video_views_p_100 INTEGER,
    shares INTEGER,
    real_time_conversion_rate DOUBLE PRECISION,
    cost_per_secondary_goal_result TEXT,
    secondary_goal_result_rate TEXT,
    clicks INTEGER,
    cost_per_1000_reached DOUBLE PRECISION,
    video_views_p_25 INTEGER,
    reach INTEGER,
    real_time_cost_per_conversion DOUBLE PRECISION,
    profile_visits_rate INTEGER,
    average_video_play DOUBLE PRECISION,
    profile_visits INTEGER,
    cpm DOUBLE PRECISION,
    ctr DOUBLE PRECISION,
    video_watched_2_s INTEGER,
    follows INTEGER,
    result_rate DOUBLE PRECISION,
    video_watched_6_s INTEGER,
    secondary_goal_result TEXT,
    cost_per_result DOUBLE PRECISION,
    average_video_play_per_user DOUBLE PRECISION,
    real_time_result_rate DOUBLE PRECISION,
    spend DOUBLE PRECISION,
    likes INTEGER,
    real_time_conversion INTEGER,
    total_purchase_value DOUBLE PRECISION,
    total_sales_lead_value DOUBLE PRECISION,
    _fivetran_synced TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY tiktok_adgroup_report_hourly FROM '$1/data/$DB_NAME/tiktok_adgroup_report_hourly.csv' DELIMITER ',' CSV HEADER;"
