# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="xero"    # Name of the new database
TABLE_NAME="bank_transaction"
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
   bank_transaction_id VARCHAR ,  
    contact_id VARCHAR
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE invoice
(
 invoice_id VARCHAR,
    contact_id VARCHAR,
    date DATE,
    updated_date_utc VARCHAR,
    planned_payment_date BIGINT,
    due_date DATE,
    expected_payment_date BIGINT,
    fully_paid_on_date DATE,
    _fivetran_synced VARCHAR,
    amount_credited BIGINT,
    amount_due DOUBLE PRECISION,
    amount_paid DOUBLE PRECISION,
    sub_total DOUBLE PRECISION,
    total DOUBLE PRECISION,
    total_tax DOUBLE PRECISION,
    currency_code VARCHAR,
    currency_rate DOUBLE PRECISION,
    has_attachments BOOLEAN,
    has_errors BOOLEAN,
    invoice_number VARCHAR,
    is_discounted BOOLEAN,
    line_amount_types VARCHAR,
    reference VARCHAR,
    sent_to_contact BOOLEAN,
    status VARCHAR,
    type VARCHAR,
    url BIGINT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY invoice FROM '$1/data/$DB_NAME/invoice.csv' DELIMITER ',' CSV HEADER;"
