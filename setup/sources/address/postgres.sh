# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="address"    # Name of the new database
TABLE_NAME="area_code"
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
    zip_code  INTEGER NOT NULL,
    area_code INTEGER NOT NULL,
    PRIMARY KEY (zip_code, area_code)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE zip_congress (
    zip_code  INTEGER NOT NULL,
    district TEXT NOT NULL,
    PRIMARY KEY (zip_code, district)
)
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY zip_congress FROM '$1/data/$DB_NAME/zip_congress.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE country
(
    zip_code INTEGER NOT NULL,
    county   TEXT NOT NULL,
    state    TEXT,
    PRIMARY KEY (zip_code, county)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY country FROM '$1/data/$DB_NAME/country.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE zip_data (
    zip_code                         INTEGER PRIMARY KEY,
    city                             TEXT,
    state                            TEXT NOT NULL,
    multi_county                     TEXT,
    type                             TEXT,
    organization                     TEXT,
    time_zone                        TEXT,
    daylight_savings                 TEXT,
    latitude                         REAL,
    longitude                        REAL,
    elevation                        INTEGER,
    state_fips                       INTEGER,
    county_fips                      INTEGER,
    region                           TEXT,
    division                         TEXT,
    population_2020                  INTEGER,
    population_2010                  INTEGER,
    households                       INTEGER,
    avg_house_value                  INTEGER,
    avg_income_per_household         INTEGER,
    persons_per_household            REAL,
    white_population                 INTEGER,
    black_population                 INTEGER,
    hispanic_population              INTEGER,
    asian_population                 INTEGER,
    american_indian_population       INTEGER,
    hawaiian_population              INTEGER,
    other_population                 INTEGER,
    male_population                  INTEGER,
    female_population                INTEGER,
    median_age                       REAL,
    male_median_age                  REAL,
    female_median_age                REAL,
    residential_mailboxes            INTEGER,
    business_mailboxes               INTEGER,
    total_delivery_receptacles       INTEGER,
    businesses                       INTEGER,
    quarter_1_payroll                BIGINT,
    annual_payroll                   BIGINT,
    employees                        INTEGER,
    water_area                       REAL,
    land_area                        REAL,
    single_family_delivery_units     INTEGER,
    multi_family_delivery_units      INTEGER,
    total_beneficiaries              INTEGER,
    retired_workers                  INTEGER,
    disabled_workers                 INTEGER,
    parents_and_widowed              INTEGER,
    spouses                          INTEGER,
    children                         INTEGER,
    over_65                          INTEGER,
    monthly_benefits_all             INTEGER,
    monthly_benefits_retired_workers INTEGER,
    monthly_benefits_widowed         INTEGER,
    CBSA                             INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY zip_data FROM '$1/data/$DB_NAME/zip_data.csv' DELIMITER ',' CSV HEADER;"
