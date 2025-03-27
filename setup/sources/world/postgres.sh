# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="world"    # Name of the new database
TABLE_NAME="country"
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
  Code VARCHAR NOT NULL DEFAULT '',
  Name VARCHAR NOT NULL DEFAULT '',
  Continent VARCHAR NOT NULL DEFAULT 'Asia',
  Region VARCHAR NOT NULL DEFAULT '',
  SurfaceArea REAL NOT NULL DEFAULT 0.00,
  IndepYear INTEGER DEFAULT NULL,
  Population INTEGER NOT NULL DEFAULT 0,
  LifeExpectancy REAL DEFAULT NULL,
  GNP REAL DEFAULT NULL,
  GNPOld REAL DEFAULT NULL,
  LocalName VARCHAR NOT NULL DEFAULT '',
  GovernmentForm VARCHAR NOT NULL DEFAULT '',
  HeadOfState VARCHAR DEFAULT NULL,
  Capital INTEGER DEFAULT NULL,
  Code2 VARCHAR NOT NULL DEFAULT '',
  PRIMARY KEY (Code)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"