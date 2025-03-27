# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="ice_hockey_draft"    # Name of the new database
TABLE_NAME="seasonstatus"
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
    ELITEID   INTEGER,
    SEASON    TEXT,  -- You could change this to VARCHAR if there's a length limit
    TEAM      TEXT,  -- You could change this to VARCHAR if there's a length limit
    LEAGUE    TEXT,  -- You could change this to VARCHAR if there's a length limit
    GAMETYPE  TEXT,  -- You could change this to VARCHAR if there's a length limit
    GP        INTEGER,
    G         INTEGER,
    A         INTEGER,
    P         INTEGER,
    PIM       INTEGER,
    PLUSMINUS INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"