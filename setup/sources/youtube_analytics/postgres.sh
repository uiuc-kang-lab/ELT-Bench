# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="youtube_analytics"    # Name of the new database
TABLE_NAME="channel_basic"
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
    _fivetran_id VARCHAR(255) PRIMARY KEY,
    date DATE,
    _fivetran_synced TIMESTAMP,
    annotation_click_through_rate FLOAT,
    annotation_clickable_impressions INT,
    annotation_clicks INT,
    annotation_closable_impressions INT,
    annotation_close_rate FLOAT,
    annotation_closes INT,
    annotation_impressions INT,
    average_view_duration_percentage FLOAT,
    average_view_duration_seconds FLOAT,
    card_click_rate FLOAT,
    card_clicks INT,
    card_impressions INT,
    card_teaser_click_rate FLOAT,
    card_teaser_clicks INT,
    card_teaser_impressions INT,
    channel_id VARCHAR(255),
    comments INT,
    country_code VARCHAR(10),
    dislikes INT,
    likes INT,
    live_or_on_demand VARCHAR(50),
    red_views INT,
    red_watch_time_minutes FLOAT,
    shares INT,
    subscribed_status VARCHAR(50),
    subscribers_gained INT,
    subscribers_lost INT,
    video_id VARCHAR(255),
    videos_added_to_playlists INT,
    videos_removed_from_playlists INT,
    views INT,
    watch_time_minutes FLOAT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"
