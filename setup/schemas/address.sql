-- Schema definitions for address
-- Auto-extracted from sources/address/postgres.sh

-- Table: area_code
CREATE TABLE IF NOT EXISTS area_code (
    zip_code  INTEGER NOT NULL,
    area_code INTEGER NOT NULL,
    PRIMARY KEY (zip_code, area_code)
);

-- Table: zip_congress
CREATE TABLE IF NOT EXISTS zip_congress (
    zip_code  INTEGER NOT NULL,
    district TEXT NOT NULL,
    PRIMARY KEY (zip_code, district)
);

-- Table: country
CREATE TABLE IF NOT EXISTS country (
    zip_code INTEGER NOT NULL,
    county   TEXT NOT NULL,
    state    TEXT,
    PRIMARY KEY (zip_code, county)
);

-- Table: zip_data
CREATE TABLE IF NOT EXISTS zip_data (
    zip_code                         INTEGER PRIMARY KEY,
    city                             TEXT,
    state                            TEXT NOT NULL,
    multi_county                     TEXT,
    type                             TEXT,
    organization                     TEXT,
    time_zone                        TEXT,
    daylight_savings                 TEXT,
    latitude                         REAL,
    longitude                        REAL,
    elevation                        INTEGER,
    state_fips                       INTEGER,
    county_fips                      INTEGER,
    region                           TEXT,
    division                         TEXT,
    population_2020                  INTEGER,
    population_2010                  INTEGER,
    households                       INTEGER,
    avg_house_value                  INTEGER,
    avg_income_per_household         INTEGER,
    persons_per_household            REAL,
    white_population                 INTEGER,
    black_population                 INTEGER,
    hispanic_population              INTEGER,
    asian_population                 INTEGER,
    american_indian_population       INTEGER,
    hawaiian_population              INTEGER,
    other_population                 INTEGER,
    male_population                  INTEGER,
    female_population                INTEGER,
    median_age                       REAL,
    male_median_age                  REAL,
    female_median_age                REAL,
    residential_mailboxes            INTEGER,
    business_mailboxes               INTEGER,
    total_delivery_receptacles       INTEGER,
    businesses                       INTEGER,
    quarter_1_payroll                BIGINT,
    annual_payroll                   BIGINT,
    employees                        INTEGER,
    water_area                       REAL,
    land_area                        REAL,
    single_family_delivery_units     INTEGER,
    multi_family_delivery_units      INTEGER,
    total_beneficiaries              INTEGER,
    retired_workers                  INTEGER,
    disabled_workers                 INTEGER,
    parents_and_widowed              INTEGER,
    spouses                          INTEGER,
    children                         INTEGER,
    over_65                          INTEGER,
    monthly_benefits_all             INTEGER,
    monthly_benefits_retired_workers INTEGER,
    monthly_benefits_widowed         INTEGER,
    CBSA                             INTEGER
);

