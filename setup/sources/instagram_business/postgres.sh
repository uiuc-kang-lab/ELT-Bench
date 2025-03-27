# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="instagram_business"    # Name of the new database
TABLE_NAME="media_insights"
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
   _fivetran_id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    carousel_album_engagement FLOAT,
    carousel_album_impressions FLOAT,
    carousel_album_reach FLOAT,
    carousel_album_saved FLOAT,
    carousel_album_video_views FLOAT,
    comment_count FLOAT,
    id BIGINT,
    like_count INTEGER,
    story_exits INTEGER,
    story_impressions INTEGER,
    story_reach INTEGER,
    story_replies INTEGER,
    story_taps_back INTEGER,
    story_taps_forward INTEGER,
    video_photo_engagement FLOAT,
    video_photo_impressions FLOAT,
    video_photo_reach FLOAT,
    video_photo_saved FLOAT,
    video_views FLOAT,
    reel_comments FLOAT,
    reel_likes FLOAT,
    reel_plays FLOAT,
    reel_reach FLOAT,
    reel_shares FLOAT,
    reel_total_interactions FLOAT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

