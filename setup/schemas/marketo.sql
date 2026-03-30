-- Schema definitions for marketo
-- Auto-extracted from sources/marketo/postgres.sh

-- Table: activity_change_data_value
CREATE TABLE IF NOT EXISTS activity_change_data_value (
    activity_date TEXT,
    activity_type_id INTEGER,
    api_method_name INTEGER,
    campaign_id INTEGER,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    modifying_user INTEGER,
    new_value TEXT,
    old_value TEXT,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    reason TEXT,
    request_id INTEGER,
    source TEXT
);

-- Table: activity_open_email
CREATE TABLE IF NOT EXISTS activity_open_email (
    activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    choice_number INTEGER,
    device TEXT,
    email_template_id INTEGER,
    id INTEGER PRIMARY KEY,
    is_mobile_device BOOLEAN,
    lead_id INTEGER,
    platform TEXT,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    step_id INTEGER,
    user_agent TEXT
);

-- Table: activity_send_email
CREATE TABLE IF NOT EXISTS activity_send_email (
    activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    choice_number INTEGER,
    email_template_id INTEGER,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    primary_attribute_value_id INTEGER,
    primary_attribute_value TEXT,
    step_id INTEGER,
    action_result TEXT
);

-- Table: activity_unsubscribe_email
CREATE TABLE IF NOT EXISTS activity_unsubscribe_email (
    activity_date TEXT,
    activity_type_id INTEGER,
    campaign_id INTEGER,
    campaign_run_id INTEGER,
    client_ip_address TEXT,
    email_template_id INTEGER,
    form_fields TEXT,
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    primary_attribute_value TEXT,
    primary_attribute_value_id INTEGER,
    query_parameters TEXT,
    referrer_url TEXT,
    user_agent TEXT,
    webform_id INTEGER,
    webpage_id INTEGER
);

