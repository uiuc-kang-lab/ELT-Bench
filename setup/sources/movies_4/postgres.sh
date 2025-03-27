# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="movies_4"    # Name of the new database
TABLE_NAME="movie_cast"
TABLE_NAME2="movie_company"
TABLE_NAME3="movie_crew"
TABLE_NAME4="production_country"
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
    movie_id       INTEGER DEFAULT NULL,
    person_id      INTEGER DEFAULT NULL,
    character_name TEXT DEFAULT NULL,
    gender_id      INTEGER DEFAULT NULL,
    cast_order     INTEGER DEFAULT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE $TABLE_NAME2 (
    movie_id   INTEGER DEFAULT NULL,
    company_id INTEGER DEFAULT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME2 FROM '$1/data/$DB_NAME/$TABLE_NAME2.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE $TABLE_NAME3 (
    movie_id      INTEGER DEFAULT NULL,
    person_id     INTEGER DEFAULT NULL,
    department_id INTEGER DEFAULT NULL,
    job           TEXT DEFAULT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME3 FROM '$1/data/$DB_NAME/$TABLE_NAME3.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE $TABLE_NAME4 (
    movie_id   INTEGER DEFAULT NULL,
    country_id INTEGER DEFAULT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME4 FROM '$1/data/$DB_NAME/$TABLE_NAME4.csv' DELIMITER ',' CSV HEADER;"
