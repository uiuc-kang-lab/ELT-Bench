# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="thrombosis_prediction"    # Name of the new database
TABLE_NAME="laboratory"
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

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c '
CREATE TABLE laboratory
(
    ID        INTEGER NOT NULL,
    Date      DATE NOT NULL,
    GOT       INTEGER,
    GPT       INTEGER,
    LDH       INTEGER,
    ALP       INTEGER,
    TP        REAL,
    ALB       REAL,
    UA        REAL,
    UN        INTEGER,
    CRE       REAL,
    T_BIL   REAL,
    T_CHO   INTEGER,
    TG        INTEGER,
    CPK       INTEGER,
    GLU       INTEGER,
    WBC       REAL,
    RBC       REAL,
    HGB       REAL,
    HCT       REAL,
    PLT       INTEGER,
    PT        REAL,
    APTT      INTEGER,
    FG        REAL,
    PIC       INTEGER,
    TAT       INTEGER,
    TAT2      INTEGER,
    U_PRO   TEXT,
    IGG       INTEGER,
    IGA       INTEGER,
    IGM       INTEGER,
    CRP       TEXT,
    RA        TEXT,
    RF        TEXT,
    C3        INTEGER,
    C4        INTEGER,
    RNP       TEXT,
    SM        TEXT,
    SC170     TEXT,
    SSA       TEXT,
    SSB       TEXT,
    CENTROMEA TEXT,
    DNA       TEXT,
    DNA_II  INTEGER,
    PRIMARY KEY (ID, Date)
);
'

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"
