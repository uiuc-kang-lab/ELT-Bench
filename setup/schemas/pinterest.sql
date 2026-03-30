-- Schema definitions for pinterest
-- Auto-extracted from sources/pinterest/postgres.sh

-- Table: advertiser_report
CREATE TABLE IF NOT EXISTS advertiser_report (
    date DATE,
    advertiser_id TEXT,
    _fivetran_synced TIMESTAMP,  
    impression_1 BIGINT,
    impression_2 BIGINT,
    clickthrough_1 BIGINT,
    clickthrough_2 BIGINT,
    spend_in_micro_dollar BIGINT,
    total_conversions BIGINT,
    total_conversions_quantity BIGINT,
    total_conversions_value_in_micro_dollar BIGINT
);

-- Table: campaign_history
CREATE TABLE IF NOT EXISTS campaign_history (
    id TEXT,
    created_time TEXT,
    name TEXT,
    status TEXT,
    _fivetran_synced TEXT,
    advertiser_id TEXT,
    default_ad_group_budget_in_micro_currency BIGINT,
    is_automated_campaign BOOLEAN,
    is_campaign_budget_optimization BOOLEAN,
    is_flexible_daily_budgets BOOLEAN
);

-- Table: campaign_report
CREATE TABLE IF NOT EXISTS campaign_report (
    date DATE,
    campaign_id TEXT,
    campaign_name TEXT,
    campaign_status TEXT,
    advertiser_id TEXT,
    _fivetran_synced TIMESTAMP,
    impression_1 BIGINT,
    impression_2 BIGINT,
    clickthrough_1 BIGINT,
    clickthrough_2 BIGINT,
    spend_in_micro_dollar BIGINT,
    total_conversions BIGINT,
    total_conversions_quantity BIGINT,
    total_conversions_value_in_micro_dollar BIGINT
);

