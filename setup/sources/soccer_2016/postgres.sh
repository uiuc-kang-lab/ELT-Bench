# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="soccer_2016"    # Name of the new database
TABLE_NAME="extra_runs"
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
    Match_Id      INTEGER,
    Over_Id       INTEGER,
    Ball_Id       INTEGER,
    Extra_Type_Id INTEGER,
    Extra_Runs    INTEGER,
    Innings_No    INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE wicket_taken (
    Match_Id   INTEGER,
    Over_Id    INTEGER,
    Ball_Id    INTEGER,
    Player_Out INTEGER,
    Kind_Out   INTEGER,
    Fielders   Float,
    Innings_No INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY wicket_taken FROM '$1/data/$DB_NAME/wicket_taken.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE ball_by_ball (
    Match_Id                 INTEGER,
    Over_Id                  INTEGER,
    Ball_Id                  INTEGER,
    Innings_No               INTEGER,
    Team_Batting             INTEGER,
    Team_Bowling             INTEGER,
    Striker_Batting_Position INTEGER,
    Striker                  INTEGER,
    Non_Striker              INTEGER,
    Bowler                   INTEGER,
    PRIMARY KEY (Match_Id, Over_Id, Ball_Id, Innings_No)
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY ball_by_ball FROM '$1/data/$DB_NAME/ball_by_ball.csv' DELIMITER ',' CSV HEADER;"
