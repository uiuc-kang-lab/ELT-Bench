-- Schema definitions for apple_store
-- Auto-extracted from sources/apple_store/postgres.sh

-- Table: app_store_device
CREATE TABLE IF NOT EXISTS app_store_device (
    app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    impressions INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    impressions_unique_device INTEGER,
    page_views INTEGER,
    page_views_unique_device INTEGER
);

-- Table: crashes_app_version
CREATE TABLE IF NOT EXISTS crashes_app_version (
    app_id INTEGER,
    app_version TEXT,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    meets_threshold BOOLEAN,
    crashes INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE
);

-- Table: downloads_device
CREATE TABLE IF NOT EXISTS downloads_device (
    app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    device TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    first_time_downloads INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    redownloads INTEGER,
    total_downloads INTEGER
);

-- Table: downloads_platform_version
CREATE TABLE IF NOT EXISTS downloads_platform_version (
    app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    platform_version TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    first_time_downloads INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    redownloads INTEGER,
    total_downloads INTEGER
);

-- Table: sales_subscription_events
CREATE TABLE IF NOT EXISTS sales_subscription_events (
    _filename TEXT,
    account_number INTEGER,
    vendor_number INTEGER,
    _index INTEGER,
    event_date DATE,
    app_name TEXT,
    days_canceled INTEGER,
    subscription_name TEXT,
    consecutive_paid_periods INTEGER,
    previous_subscription_name INTEGER,
    cancellation_reason TEXT,
    proceeds_reason TEXT,
    subscription_apple_id INTEGER,
    standard_subscription_duration TEXT,
    original_start_date DATE,
    device TEXT,
    days_before_canceling INTEGER,
    quantity INTEGER,
    marketing_opt_in_duration INTEGER,
    promotional_offer_name INTEGER,
    state TEXT,
    previous_subscription_apple_id INTEGER,
    event TEXT,
    subscription_group_id INTEGER,
    country TEXT,
    promotional_offer_id INTEGER,
    app_apple_id INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    subscription_offer_type INTEGER,
    subscription_offer_duration INTEGER
);

-- Table: usage_platform_version
CREATE TABLE IF NOT EXISTS usage_platform_version (
    app_id INTEGER,
    date TIMESTAMP WITHOUT TIME ZONE,
    platform_version TEXT,
    source_type TEXT,
    meets_threshold BOOLEAN,
    installations INTEGER,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    sessions INTEGER,
    active_devices INTEGER,
    active_devices_last_30_days INTEGER,
    deletions INTEGER
);

