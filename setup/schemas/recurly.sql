-- Schema definitions for recurly
-- Auto-extracted from sources/recurly/postgres.sh

-- Table: account
CREATE TABLE IF NOT EXISTS account (
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

-- Table: account_balance
CREATE TABLE IF NOT EXISTS account_balance (
    account_id TEXT,
    account_updated_at TIMESTAMP WITHOUT TIME ZONE,
    currency TEXT,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    amount DOUBLE PRECISION,
    past_due BOOLEAN
);

-- Table: credit_payment
CREATE TABLE IF NOT EXISTS credit_payment (
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

-- Table: invoice
CREATE TABLE IF NOT EXISTS invoice (
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

-- Table: transaction
CREATE TABLE IF NOT EXISTS transaction (
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

