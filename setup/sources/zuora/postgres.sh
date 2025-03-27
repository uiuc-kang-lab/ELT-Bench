# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="zuora"    # Name of the new database
TABLE_NAME="credit_balance_adjustment"
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
   id VARCHAR(255) PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    account_id VARCHAR(255),
    account_receivable_accounting_code_id VARCHAR(255),
    accounting_code VARCHAR(255),
    accounting_period_id VARCHAR(255),
    adjustment_date DATE,
    amount DECIMAL(15,2),
    amount_currency_rounding DECIMAL(15,2),
    amount_home_currency DECIMAL(15,2),
    bill_to_contact_id VARCHAR(255),
    cancelled_on TIMESTAMP,
    comment TEXT,
    created_by_id VARCHAR(255),
    created_date TIMESTAMP,
    customer_cash_on_account_accounting_code_id VARCHAR(255),
    default_payment_method_id VARCHAR(255),
    exchange_rate DECIMAL(15,8),
    exchange_rate_date DATE,
    home_currency VARCHAR(10),
    invoice_id VARCHAR(255),
    journal_entry_id VARCHAR(255),
    journal_run_id VARCHAR(255),
    number VARCHAR(255),
    parent_account_id VARCHAR(255),
    provider_exchange_rate_date DATE,
    reason_code VARCHAR(255),
    reference_id VARCHAR(255),
    sold_to_contact_id VARCHAR(255),
    source_transaction_id VARCHAR(255),
    source_transaction_number VARCHAR(255),
    source_transaction_type VARCHAR(50),
    status VARCHAR(50),
    transaction_currency VARCHAR(10),
    transferred_to_accounting BOOLEAN,
    type VARCHAR(50),
    updated_by_id VARCHAR(255),
    updated_date TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE invoice
(
   id VARCHAR(255) PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    account_id VARCHAR(255),
    adjustment_amount DECIMAL(15,2),
    amount DECIMAL(15,2),
    amount_currency_rounding DECIMAL(15,2),
    amount_home_currency DECIMAL(15,2),
    amount_without_tax DECIMAL(15,2),
    amount_without_tax_currency_rounding DECIMAL(15,2),
    amount_without_tax_home_currency DECIMAL(15,2),
    auto_pay BOOLEAN,
    balance DECIMAL(15,2),
    bill_to_contact_id VARCHAR(255),
    comments TEXT,
    created_by_id VARCHAR(255),
    created_date TIMESTAMP,
    credit_balance_adjustment_amount DECIMAL(15,2),
    default_payment_method_id VARCHAR(255),
    due_date DATE,
    exchange_rate DECIMAL(15,8),
    exchange_rate_date DATE,
    home_currency VARCHAR(10),
    includes_one_time BOOLEAN,
    includes_recurring BOOLEAN,
    includes_usage BOOLEAN,
    invoice_date DATE,
    invoice_number VARCHAR(255),
    last_email_sent_date DATE,
    parent_account_id VARCHAR(255),
    payment_amount DECIMAL(15,2),
    payment_term VARCHAR(50),
    posted_by VARCHAR(255),
    posted_date TIMESTAMP,
    provider_exchange_rate_date DATE,
    refund_amount DECIMAL(15,2),
    reversed BOOLEAN,
    sold_to_contact_id VARCHAR(255),
    source VARCHAR(255),
    source_id VARCHAR(255),
    source_type VARCHAR(100),
    status VARCHAR(50),
    target_date DATE,
    tax_amount DECIMAL(15,2),
    tax_exempt_amount DECIMAL(15,2),
    tax_message TEXT,
    tax_status VARCHAR(50),
    template_id VARCHAR(255),
    transaction_currency VARCHAR(10),
    transferred_to_accounting BOOLEAN,
    updated_by_id VARCHAR(255),
    updated_date TIMESTAMP,
    sequence_set_id VARCHAR(255),
    credit_memo_amount DECIMAL(15,2)
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY invoice FROM '$1/data/$DB_NAME/invoice.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE orders
(
   id VARCHAR(255) PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    account_id VARCHAR(255),
    bill_to_contact_id VARCHAR(255),
    created_by_id VARCHAR(255),
    created_by_migration BOOLEAN,
    created_date TIMESTAMP,
    default_payment_method_id VARCHAR(255),
    description TEXT,
    order_date DATE,
    order_number VARCHAR(50),
    parent_account_id VARCHAR(255),
    sold_to_contact_id VARCHAR(255),
    state VARCHAR(50),
    status VARCHAR(50),
    updated_by_id VARCHAR(255),
    updated_date TIMESTAMP,
    category VARCHAR(50),
    error_message TEXT,
    scheduled_date_policy VARCHAR(50),
    response TEXT,
    error_code VARCHAR(50),
    scheduled_date DATE
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY orders FROM '$1/data/$DB_NAME/orders.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE payment
(
   id VARCHAR(255) PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    account_id VARCHAR(255),
    accounting_code VARCHAR(255),
    amount DECIMAL(15,2),
    amount_currency_rounding DECIMAL(15,2),
    amount_home_currency DECIMAL(15,2),
    applied_amount DECIMAL(15,2),
    applied_credit_balance_amount DECIMAL(15,2),
    auth_transaction_id VARCHAR(255),
    bank_identification_number VARCHAR(50),
    bill_to_contact_id VARCHAR(255),
    cancelled_on TIMESTAMP,
    comment TEXT,
    created_by_id VARCHAR(255),
    created_date TIMESTAMP,
    currency VARCHAR(10),
    default_payment_method_id VARCHAR(255),
    effective_date DATE,
    exchange_rate DECIMAL(15,8),
    exchange_rate_date DATE,
    gateway VARCHAR(100),
    gateway_order_id VARCHAR(255),
    gateway_reconciliation_reason TEXT,
    gateway_reconciliation_status VARCHAR(100),
    gateway_response TEXT,
    gateway_response_code VARCHAR(50),
    gateway_state VARCHAR(100),
    home_currency VARCHAR(10),
    is_standalone BOOLEAN,
    marked_for_submission_on DATE,
    parent_account_id VARCHAR(255),
    payment_method_id VARCHAR(255),
    payment_number VARCHAR(50),
    payout_id VARCHAR(255),
    provider_exchange_rate_date DATE,
    reference_id VARCHAR(255),
    referenced_payment_id VARCHAR(255),
    refund_amount DECIMAL(15,2),
    second_payment_reference_id VARCHAR(255),
    settled_on DATE,
    soft_descriptor VARCHAR(255),
    soft_descriptor_phone VARCHAR(50),
    sold_to_contact_id VARCHAR(255),
    source VARCHAR(100),
    source_name VARCHAR(255),
    status VARCHAR(100),
    submitted_on TIMESTAMP,
    transaction_currency VARCHAR(10),
    transferred_to_accounting BOOLEAN,
    type VARCHAR(100),
    unapplied_amount DECIMAL(15,2),
    updated_by_id VARCHAR(255),
    updated_date TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY payment FROM '$1/data/$DB_NAME/payment.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE refund
(
   id VARCHAR(255) PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    accounting_code VARCHAR(255),
    amount DECIMAL(15,2),
    cancelled_on TIMESTAMP,
    comment TEXT,
    created_by_id VARCHAR(255),
    created_date TIMESTAMP,
    gateway VARCHAR(100),
    gateway_reconciliation_reason TEXT,
    gateway_reconciliation_status VARCHAR(100),
    gateway_response TEXT,
    gateway_response_code VARCHAR(50),
    gateway_state VARCHAR(100),
    marked_for_submission_on TIMESTAMP,
    method_type VARCHAR(50),
    payment_method_id VARCHAR(255),
    payout_id VARCHAR(255),
    reason_code VARCHAR(100),
    reference_id VARCHAR(255),
    refund_date DATE,
    refund_number VARCHAR(100),
    refund_transaction_time TIMESTAMP,
    second_refund_reference_id VARCHAR(255),
    soft_descriptor VARCHAR(255),
    soft_descriptor_phone VARCHAR(50),
    source_type VARCHAR(100),
    status VARCHAR(100),
    submitted_on TIMESTAMP,
    transferred_to_accounting BOOLEAN,
    type VARCHAR(100),
    updated_by_id VARCHAR(255),
    updated_date TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY refund FROM '$1/data/$DB_NAME/refund.csv' DELIMITER ',' CSV HEADER;"
