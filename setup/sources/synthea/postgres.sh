# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="synthea"    # Name of the new database
TABLE_NAME="allergies"
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
    START       DATE,
    STOP        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        INTEGER,
    DESCRIPTION TEXT,
    PRIMARY KEY (PATIENT, ENCOUNTER, CODE)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE careplans (
    ID                TEXT,
    START             DATE,
    STOP              DATE,
    PATIENT           TEXT,
    ENCOUNTER         TEXT,
    CODE              REAL,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY careplans FROM '$1/data/$DB_NAME/careplans.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE claims
(
    ID             TEXT PRIMARY KEY,
    PATIENT        TEXT,
    BILLABLEPERIOD DATE,
    ORGANIZATION   TEXT,
    ENCOUNTER      TEXT,
    DIAGNOSIS      TEXT,
    TOTAL          INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY claims FROM '$1/data/$DB_NAME/claims.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE conditions
(
    START       DATE,
    STOP        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        BIGINT,
    DESCRIPTION TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY conditions FROM '$1/data/$DB_NAME/conditions.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE encounters
(
    ID                TEXT PRIMARY KEY,
    DATE              DATE,
    PATIENT           TEXT,
    CODE              INTEGER,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY encounters FROM '$1/data/$DB_NAME/encounters.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE immunizations
(
    DATE        DATE,
    PATIENT     TEXT,
    ENCOUNTER   TEXT,
    CODE        INTEGER,
    DESCRIPTION TEXT,
    PRIMARY KEY (DATE, PATIENT, ENCOUNTER, CODE)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY immunizations FROM '$1/data/$DB_NAME/immunizations.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE medications
(
    START             DATE,
    STOP              DATE,
    PATIENT           TEXT,
    ENCOUNTER         TEXT,
    CODE              INTEGER,
    DESCRIPTION       TEXT,
    REASONCODE        BIGINT,
    REASONDESCRIPTION TEXT,
    PRIMARY KEY (START, PATIENT, ENCOUNTER, CODE)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY medications FROM '$1/data/$DB_NAME/medications.csv' DELIMITER ',' CSV HEADER;"
