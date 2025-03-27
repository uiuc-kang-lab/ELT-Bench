# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="formula_1"    # Name of the new database
TABLE_NAME="constructor_results"
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
    constructorResultsId SERIAL PRIMARY KEY,
    raceId               INTEGER DEFAULT 0 NOT NULL,
    constructorId        INTEGER DEFAULT 0 NOT NULL,
    points               REAL,
    status               TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE constructor_standings (
    constructorStandingsId SERIAL PRIMARY KEY,
    raceId                 INTEGER DEFAULT 0 NOT NULL,
    constructorId          INTEGER DEFAULT 0 NOT NULL,
    points                 REAL DEFAULT 0 NOT NULL,
    position               INTEGER,
    positionText           TEXT,
    wins                   INTEGER DEFAULT 0 NOT NULL
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY constructor_standings FROM '$1/data/$DB_NAME/constructor_standings.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE qualifying
(
    qualifyId     SERIAL PRIMARY KEY,
    raceId        INTEGER DEFAULT 0 NOT NULL,
    driverId      INTEGER DEFAULT 0 NOT NULL,
    constructorId INTEGER DEFAULT 0 NOT NULL,
    number        INTEGER DEFAULT 0 NOT NULL,
    position      INTEGER,
    q1            TEXT,
    q2            TEXT,
    q3            TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY qualifying FROM '$1/data/$DB_NAME/qualifying.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE results (
    resultId        SERIAL PRIMARY KEY,
    raceId          INTEGER DEFAULT 0 NOT NULL,
    driverId        INTEGER DEFAULT 0 NOT NULL,
    constructorId   INTEGER DEFAULT 0 NOT NULL,
    number          INTEGER,
    grid            INTEGER DEFAULT 0 NOT NULL,
    position        INTEGER,
    positionText    TEXT DEFAULT '' NOT NULL,
    positionOrder   INTEGER DEFAULT 0 NOT NULL,
    points          REAL DEFAULT 0 NOT NULL,
    laps            INTEGER DEFAULT 0 NOT NULL,
    time            TEXT,
    milliseconds    INTEGER,
    fastestLap      INTEGER,
    rank            INTEGER DEFAULT 0,
    fastestLapTime  TEXT,
    fastestLapSpeed TEXT,
    statusId        INTEGER DEFAULT 0 NOT NULL
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY results FROM '$1/data/$DB_NAME/results.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE lap_times (
  raceId       INTEGER NOT NULL,
  driverId     INTEGER NOT NULL,
  lap           INTEGER NOT NULL,
  position      INTEGER,
  time          TEXT,
  milliseconds  INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY lap_times FROM '$1/data/$DB_NAME/lap_times.csv' DELIMITER ',' CSV HEADER;"
