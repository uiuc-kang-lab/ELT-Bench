# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="movie_platform"    # Name of the new database
TABLE_NAME="ratings"
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
CREATE TABLE $TABLE_NAME(
    movie_id                INTEGER,
    rating_id               SERIAL,
    rating_url              TEXT,
    rating_score            INTEGER,
    rating_timestamp_utc    TEXT,
    critic                  TEXT,
    critic_likes            INTEGER,
    critic_comments         INTEGER,
    user_id                 INTEGER,
    user_trialist           INTEGER,
    user_subscriber         INTEGER,
    user_eligible_for_trial INTEGER,
    user_has_payment_method INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE ratings_users
(
   user_id                 INTEGER,
    rating_date_utc         TEXT,
    user_trialist           INTEGER,
    user_subscriber         INTEGER,
    user_avatar_image_url   TEXT,
    user_cover_image_url    TEXT,
    user_eligible_for_trial INTEGER,
    user_has_payment_method INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY ratings_users FROM '$1/data/$DB_NAME/ratings_users.csv' DELIMITER ',' CSV HEADER;"
