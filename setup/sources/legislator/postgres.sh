# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="legislator"    # Name of the new database
TABLE_NAME="legislator_current"
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
    ballotpedia_id      TEXT,
    bioguide_id         TEXT,
    birthday_bio        DATE,
    cspan_id            REAL,
    fec_id              TEXT,
    first_name          TEXT,
    gender_bio          TEXT,
    google_entity_id_id TEXT,
    govtrack_id         INTEGER,
    house_history_id    REAL,
    icpsr_id            REAL,
    last_name           TEXT,
    lis_id              TEXT,
    maplight_id         REAL,
    middle_name         TEXT,
    nickname_name       TEXT,
    official_full_name  TEXT,
    opensecrets_id      TEXT,
    religion_bio        TEXT,
    suffix_name         TEXT,
    thomas_id           TEXT,
    votesmart_id        REAL,
    wikidata_id         TEXT,
    wikipedia_id        TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

