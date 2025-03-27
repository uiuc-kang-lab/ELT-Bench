# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="recurly"    # Name of the new database
TABLE_NAME="account"
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
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    id TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    deleted_at TIMESTAMP WITHOUT TIME ZONE,
    code TEXT,
    bill_to TEXT,
    state TEXT,
    username TEXT,
    account_first_name INTEGER,
    account_last_name INTEGER,
    email TEXT,
    cc_emails TEXT,
    company TEXT,
    vat_number TEXT,
    tax_exempt BOOLEAN,
    account_country TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE account_balance
(
   account_id TEXT,
    account_updated_at TIMESTAMP WITHOUT TIME ZONE,
    currency TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    amount DOUBLE PRECISION,
    past_due BOOLEAN
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY account_balance FROM '$1/data/$DB_NAME/account_balance.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE credit_payment
(
   _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    id VARCHAR,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    account_id VARCHAR,
    applied_to_invoice_id VARCHAR,
    original_invoice_id VARCHAR,
    refund_transaction_id VARCHAR,
    original_credit_payment_id VARCHAR,
    uuid VARCHAR,
    action TEXT,
    currency TEXT,
    amount DOUBLE PRECISION,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    voided_at TIMESTAMP WITHOUT TIME ZONE
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY credit_payment FROM '$1/data/$DB_NAME/credit_payment.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE invoice
(
   _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    id TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    due_at TIMESTAMP WITHOUT TIME ZONE,
    closed_at TIMESTAMP WITHOUT TIME ZONE,
    account_id TEXT,
    previous_invoice_id INTEGER,
    type TEXT,
    origin TEXT,
    state TEXT,
    number INTEGER,
    collection_method TEXT,
    po_number INTEGER,
    net_terms INTEGER,
    currency TEXT,
    balance DOUBLE PRECISION,
    paid DOUBLE PRECISION,
    total DOUBLE PRECISION,
    subtotal DOUBLE PRECISION,
    refundable_amount DOUBLE PRECISION,
    discount DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    tax_type INTEGER,
    tax_region INTEGER,
    tax_rate INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY invoice FROM '$1/data/$DB_NAME/invoice.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE transaction
(
   _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    id TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    voided_at TIMESTAMP WITHOUT TIME ZONE,
    collected_at TIMESTAMP WITHOUT TIME ZONE,
    original_transaction_id INTEGER,
    account_id TEXT,
    invoice_id TEXT,
    voided_by_invoice_id TEXT,
    uuid TEXT,
    type TEXT,
    origin TEXT,
    currency TEXT,
    amount DOUBLE PRECISION,
    status TEXT,
    success BOOLEAN,
    refunded BOOLEAN,
    billing_first_name TEXT,
    billing_last_name TEXT,
    billing_phone TEXT,
    billing_street_1 TEXT,
    billing_street_2 TEXT,
    billing_city TEXT,
    billing_region TEXT,
    billing_postal_code TEXT,
    billing_country TEXT,
    collection_method TEXT,
    payment_method_object TEXT,
    status_code TEXT,
    status_message TEXT,
    customer_message TEXT,
    customer_message_locale TEXT,
    gateway_message TEXT,
    gateway_reference INTEGER,
    gateway_approval_code INTEGER,
    gateway_response_code INTEGER,
    gateway_response_time DOUBLE PRECISION,
    payment_gateway_id INTEGER,
    payment_gateway_name TEXT,
    gateway_response_values TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY transaction FROM '$1/data/$DB_NAME/transaction.csv' DELIMITER ',' CSV HEADER;"
