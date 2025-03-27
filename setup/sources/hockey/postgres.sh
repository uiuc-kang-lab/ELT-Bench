# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="hockey"    # Name of the new database
TABLE_NAME="goalies_shootout"
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
    playerID TEXT,
  year INTEGER,
  stint INTEGER,
  tmID TEXT,
  W INTEGER,
  L INTEGER,
  SA INTEGER,
  GA INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE master
(
  playerID TEXT,
  coachID TEXT,
  hofID TEXT,
  firstName TEXT,
  lastName TEXT NOT NULL,
  nameNote TEXT,
  nameGiven TEXT,
  nameNick TEXT,
  height TEXT,
  weight TEXT,
  shootCatch TEXT,
  legendsID TEXT,
  ihdbID TEXT,
  hrefID TEXT,
  firstNHL TEXT,
  lastNHL TEXT,
  firstWHA TEXT,
  lastWHA TEXT,
  pos TEXT,
  birthYear TEXT,
  birthMon TEXT,
  birthDay TEXT,
  birthCountry TEXT,
  birthState TEXT,
  birthCity TEXT,
  deathYear TEXT,
  deathMon TEXT,
  deathDay TEXT,
  deathCountry TEXT,
  deathState TEXT,
  deathCity TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY master FROM '$1/data/$DB_NAME/master.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE scoring
(
  playerID TEXT,
  year INTEGER,
  stint INTEGER,
  tmID TEXT,
  lgID TEXT,
  pos TEXT,
  GP DECIMAL,
  G DECIMAL,
  A DECIMAL,
  Pts DECIMAL,
  PIM DECIMAL,
  p_n TEXT,
  PPG TEXT,
  PPA TEXT,
  SHG TEXT,
  SHA TEXT,
  GWG TEXT,
  GTG TEXT,
  SOG TEXT,
  PostGP TEXT,
  PostG TEXT,
  PostA TEXT,
  PostPts TEXT,
  PostPIM TEXT,
  Post_p_n TEXT,
  PostPPG TEXT,
  PostPPA TEXT,
  PostSHG TEXT,
  PostSHA TEXT,
  PostGWG TEXT,
  PostSOG TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY scoring FROM '$1/data/$DB_NAME/scoring.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE team_half
(
   year INTEGER NOT NULL,
  lgID TEXT,
  tmID TEXT NOT NULL,
  half INTEGER NOT NULL,
  rank INTEGER,
  G INTEGER,
  W INTEGER,
  L INTEGER,
  T INTEGER,
  GF INTEGER,
  GA INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY team_half FROM '$1/data/$DB_NAME/team_half.csv' DELIMITER ',' CSV HEADER;"
