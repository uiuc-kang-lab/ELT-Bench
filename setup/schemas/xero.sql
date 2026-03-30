-- Schema definitions for xero
-- Auto-extracted from sources/xero/postgres.sh

-- Table: bank_transaction
CREATE TABLE IF NOT EXISTS bank_transaction (
    bank_transaction_id VARCHAR ,  
    contact_id VARCHAR
);

-- Table: invoice
CREATE TABLE IF NOT EXISTS invoice (
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

