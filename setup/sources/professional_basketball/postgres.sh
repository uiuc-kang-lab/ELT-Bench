# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="professional_basketball"    # Name of the new database
TABLE_NAME="coaches"
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
    coachID     TEXT NOT NULL,
    year        INTEGER NOT NULL,
    tmID        TEXT NOT NULL,
    lgID        TEXT,
    stint       INTEGER NOT NULL,
    won         INTEGER,
    lost        INTEGER,
    post_wins   INTEGER,
    post_losses INTEGER,
    PRIMARY KEY (coachID, year, tmID, stint)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE players_teams (
    id                 SERIAL PRIMARY KEY,
    playerID           TEXT NOT NULL,
    year               INTEGER,
    stint              INTEGER,
    tmID               TEXT,
    lgID               TEXT,
    GP                 INTEGER,
    GS                 INTEGER,
    minutes            INTEGER,
    points             INTEGER,
    oRebounds          INTEGER,
    dRebounds          INTEGER,
    rebounds           INTEGER,
    assists            INTEGER,
    steals             INTEGER,
    blocks             INTEGER,
    turnovers          INTEGER,
    PF                 INTEGER,
    fgAttempted        INTEGER,
    fgMade             INTEGER,
    ftAttempted        INTEGER,
    ftMade             INTEGER,
    threeAttempted     INTEGER,
    threeMade          INTEGER,
    PostGP             INTEGER,
    PostGS             INTEGER,
    PostMinutes        INTEGER,
    PostPoints         INTEGER,
    PostoRebounds      INTEGER,
    PostdRebounds      INTEGER,
    PostRebounds       INTEGER,
    PostAssists        INTEGER,
    PostSteals         INTEGER,
    PostBlocks         INTEGER,
    PostTurnovers      INTEGER,
    PostPF             INTEGER,
    PostfgAttempted    INTEGER,
    PostfgMade         INTEGER,
    PostftAttempted    INTEGER,
    PostftMade         INTEGER,
    PostthreeAttempted INTEGER,
    PostthreeMade      INTEGER,
    note               TEXT
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY players_teams FROM '$1/data/$DB_NAME/players_teams.csv' DELIMITER ',' CSV HEADER;"
