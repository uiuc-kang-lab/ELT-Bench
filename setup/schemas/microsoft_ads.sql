-- Schema definitions for microsoft_ads
-- Auto-extracted from sources/microsoft_ads/postgres.sh

-- Table: account_performance_daily_report
CREATE TABLE IF NOT EXISTS account_performance_daily_report (
    date DATE,
    account_id BIGINT,
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    currency_code VARCHAR(10),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(255),
    delivered_match_type VARCHAR(255),
    top_vs_other VARCHAR(255),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT
);

-- Table: ad_group_performance_daily_report
CREATE TABLE IF NOT EXISTS ad_group_performance_daily_report (
    date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    ad_group_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    language VARCHAR(50),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);

-- Table: ad_performance_daily_report
CREATE TABLE IF NOT EXISTS ad_performance_daily_report (
    date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    ad_group_id BIGINT,
    ad_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    language VARCHAR(50),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);

-- Table: campaign_performance_daily_report
CREATE TABLE IF NOT EXISTS campaign_performance_daily_report (
    date DATE,
    account_id BIGINT,
    campaign_id BIGINT,
    currency_code VARCHAR(10),
    device_os VARCHAR(255),
    device_type VARCHAR(255),
    network VARCHAR(255),
    ad_distribution VARCHAR(255),
    bid_match_type VARCHAR(50),
    delivered_match_type VARCHAR(50),
    top_vs_other VARCHAR(50),
    budget_association_status VARCHAR(50),
    budget_name VARCHAR(255),
    clicks BIGINT,
    impressions BIGINT,
    spend NUMERIC,
    conversions_qualified BIGINT,
    conversions BIGINT,
    revenue NUMERIC,
    all_conversions_qualified BIGINT,
    all_conversions BIGINT,
    all_revenue NUMERIC
);

