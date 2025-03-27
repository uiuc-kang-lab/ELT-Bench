# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="lever"    # Name of the new database
TABLE_NAME="application"
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
   id TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    archived_at TIMESTAMP WITHOUT TIME ZONE,
    archived_reason_id INTEGER,
    candidate_id INTEGER,
    comments INTEGER,
    company INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    posting_hiring_manager_id TEXT,
    posting_id TEXT,
    posting_owner_id TEXT,
    referrer_id TEXT,
    requisition_for_hire_id INTEGER,
    type TEXT,
    opportunity_id TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE feedback_form_field
(
   feedback_form_id TEXT,
    field_index BIGINT,
    value_index BIGINT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    code_language INTEGER,
    currency INTEGER,
    value_date TIMESTAMP WITHOUT TIME ZONE,
    value_decimal NUMERIC,
    value_file_id INTEGER,
    value_number INTEGER,
    value_text TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY feedback_form_field FROM '$1/data/$DB_NAME/feedback_form_field.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE offer
(
   id TEXT,  
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE, 
    candidate_id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE,  
    creator_id TEXT,  
    status TEXT 
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY offer FROM '$1/data/$DB_NAME/offer.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE requisition
(
   id TEXT,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    backfill BOOLEAN,
    compensation_band_currency TEXT,
    compensation_band_interval TEXT,
    compensation_band_max INTEGER,
    compensation_band_min INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    creator_id TEXT,
    employment_status TEXT,
    headcount_hired INTEGER,
    headcount_infinite INTEGER,
    headcount_total INTEGER,
    hiring_manager_id TEXT,
    internal_notes TEXT,
    location TEXT,
    name TEXT,
    owner_id TEXT,
    requisition_code INTEGER,
    status TEXT,
    team TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY requisition FROM '$1/data/$DB_NAME/requisition.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE posting
(
    id TEXT,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    categories_commitment TEXT,
    categories_department INTEGER,
    categories_level INTEGER,
    categories_location TEXT,
    categories_team TEXT,
    content_closing TEXT,
    content_closing_html TEXT,
    content_description TEXT,
    content_description_html TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    creator_id TEXT,
    owner_id TEXT,
    requisition_code INTEGER,
    state TEXT,
    text TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY posting FROM '$1/data/$DB_NAME/posting.csv' DELIMITER ',' CSV HEADER;"
