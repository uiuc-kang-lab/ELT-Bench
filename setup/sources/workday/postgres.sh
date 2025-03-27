# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="workday"    # Name of the new database
TABLE_NAME="military_service"
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
   index integer, 
    personal_info_system_id text ,  
    _fivetran_deleted BOOLEAN,
    _fivetran_synced timestamp without time zone,
    discharge_date DATE,  
    notes integer,  
    rank integer,  
    service text,  
    service_type integer,  
    status text,  
    status_begin_date integer
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE organization
(
   id text PRIMARY KEY,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP,
    availability_date TIMESTAMP,
    available_for_hire integer,
    code integer,
    description integer,
    external_url text,
    hiring_freeze BOOLEAN,
    inactive BOOLEAN,
    inactive_date integer,
    include_manager_in_name BOOLEAN,
    include_organization_code_in_name BOOLEAN,
    last_updated_date_time TIMESTAMP,
    location text,
    manager_id text,
    name text,
    organization_code text,
    organization_owner_id text,
    staffing_model text,
    sub_type text,
    superior_organization_id text,
    supervisory_position_availability_date date,
    supervisory_position_earliest_hire_date date,
    supervisory_position_time_type integer,
    supervisory_position_worker_type integer,
    top_level_organization_id text,
    type text,
    visibility text
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY organization FROM '$1/data/$DB_NAME/organization.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE person_name
(
   index INTEGER,
    personal_info_system_id TEXT,
    type TEXT,
    _fivetran_deleted BOOLEAN,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    academic_suffix INTEGER,
    additional_name_type INTEGER,
    country TEXT,
    first_name TEXT,
    full_name_singapore_malaysia INTEGER,
    hereditary_suffix INTEGER,
    honorary_suffix INTEGER,
    last_name TEXT,
    local_first_name INTEGER,
    local_first_name_2 INTEGER,
    local_last_name INTEGER,
    local_last_name_2 INTEGER,
    local_middle_name INTEGER,
    local_middle_name_2 INTEGER,
    local_secondary_last_name INTEGER,
    local_secondary_last_name_2 INTEGER,
    middle_name INTEGER,
    prefix_salutation INTEGER,
    prefix_title INTEGER,
    prefix_title_code INTEGER,
    professional_suffix INTEGER,
    religious_suffix INTEGER,
    royal_suffix INTEGER,
    secondary_last_name INTEGER,
    social_suffix INTEGER,
    social_suffix_id INTEGER,
    tertiary_last_name INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY person_name FROM '$1/data/$DB_NAME/person_name.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE personal_information_history
(
   id TEXT PRIMARY KEY,
    type TEXT,
    _fivetran_active BOOLEAN DEFAULT FALSE,
    _fivetran_start TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_end TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    additional_nationality INTEGER,
    blood_type INTEGER,
    citizenship_status TEXT,
    city_of_birth TEXT,
    city_of_birth_code INTEGER,
    country_of_birth TEXT,
    date_of_birth DATE,
    date_of_death INTEGER,
    gender TEXT,
    hispanic_or_latino INTEGER,
    hukou_locality INTEGER,
    hukou_postal_code INTEGER,
    hukou_region INTEGER,
    hukou_subregion INTEGER,
    hukou_type INTEGER,
    last_medical_exam_date INTEGER,
    last_medical_exam_valid_to INTEGER,
    local_hukou INTEGER,
    marital_status TEXT,
    marital_status_date INTEGER,
    medical_exam_notes INTEGER,
    native_region INTEGER,
    native_region_code INTEGER,
    personnel_file_agency INTEGER,
    political_affiliation INTEGER,
    primary_nationality TEXT,
    region_of_birth INTEGER,
    region_of_birth_code TEXT,
    religion TEXT,
    social_benefit INTEGER,
    tobacco_use BOOLEAN,
    ll INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY personal_information_history FROM '$1/data/$DB_NAME/personal_information_history.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE position
(
   id TEXT PRIMARY KEY,
    _fivetran_deleted BOOLEAN DEFAULT FALSE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    academic_tenure_eligible BOOLEAN,
    availability_date DATE,
    available_for_hire BOOLEAN,
    available_for_overlap BOOLEAN,
    available_for_recruiting BOOLEAN,
    closed BOOLEAN,
    compensation_grade_code INTEGER,
    compensation_grade_profile_code INTEGER,
    compensation_package_code INTEGER,
    compensation_step_code INTEGER,
    critical_job BOOLEAN,
    difficulty_to_fill_code INTEGER,
    earliest_hire_date DATE,
    earliest_overlap_date INTEGER,
    effective_date DATE,
    hiring_freeze BOOLEAN,
    job_description TEXT,
    job_description_summary TEXT,
    job_posting_title TEXT,
    position_code TEXT,
    position_time_type_code TEXT,
    primary_compensation_basis DOUBLE PRECISION,
    primary_compensation_basis_amount_change INTEGER,
    primary_compensation_basis_percent_change INTEGER,
    supervisory_organization_id TEXT,
    work_shift_required BOOLEAN,
    worker_for_filled_position_id TEXT,
    worker_position_id TEXT,
    worker_type_code TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY position FROM '$1/data/$DB_NAME/position.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE worker_history
(
   id TEXT PRIMARY KEY,
    _fivetran_active BOOLEAN,
    _fivetran_start TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_end TIMESTAMP WITHOUT TIME ZONE,
    _fivetran_synced TIMESTAMP WITHOUT TIME ZONE,
    academic_tenure_date INTEGER,
    active BOOLEAN,
    active_status_date DATE,
    annual_currency_summary_currency TEXT,
    annual_currency_summary_frequency TEXT,
    annual_currency_summary_primary_compensation_basis DOUBLE PRECISION,
    annual_currency_summary_total_base_pay DOUBLE PRECISION,
    annual_currency_summary_total_salary_and_allowances DOUBLE PRECISION,
    annual_summary_currency TEXT,
    annual_summary_frequency TEXT,
    annual_summary_primary_compensation_basis DOUBLE PRECISION,
    annual_summary_total_base_pay DOUBLE PRECISION,
    annual_summary_total_salary_and_allowances DOUBLE PRECISION,
    benefits_service_date INTEGER,
    company_service_date INTEGER,
    compensation_effective_date DATE,
    compensation_grade_id TEXT,
    compensation_grade_profile_id TEXT,
    continuous_service_date DATE,
    contract_assignment_details INTEGER,
    contract_currency_code INTEGER,
    contract_end_date INTEGER,
    contract_frequency_name INTEGER,
    contract_pay_rate INTEGER,
    contract_vendor_name INTEGER,
    date_entered_workforce INTEGER,
    days_unemployed DOUBLE PRECISION,
    eligible_for_hire TEXT,
    eligible_for_rehire_on_latest_termination TEXT,
    employee_compensation_currency TEXT,
    employee_compensation_frequency TEXT,
    employee_compensation_primary_compensation_basis DOUBLE PRECISION,
    employee_compensation_total_base_pay DOUBLE PRECISION,
    employee_compensation_total_salary_and_allowances DOUBLE PRECISION,
    end_employment_date DATE,
    expected_date_of_return INTEGER,
    expected_retirement_date INTEGER,
    first_day_of_work DATE,
    has_international_assignment BOOLEAN,
    hire_date DATE,
    hire_reason TEXT,
    hire_rescinded BOOLEAN,
    home_country INTEGER,
    hourly_frequency_currency TEXT,
    hourly_frequency_frequency TEXT,
    hourly_frequency_primary_compensation_basis INTEGER,
    hourly_frequency_total_base_pay DOUBLE PRECISION,
    hourly_frequency_total_salary_and_allowances INTEGER,
    last_date_for_which_paid INTEGER,
    local_termination_reason INTEGER,
    months_continuous_prior_employment DOUBLE PRECISION,
    not_returning BOOLEAN,
    original_hire_date DATE,
    pay_group_frequency_currency TEXT,
    pay_group_frequency_frequency INTEGER,
    pay_group_frequency_primary_compensation_basis DOUBLE PRECISION,
    pay_group_frequency_total_base_pay DOUBLE PRECISION,
    pay_group_frequency_total_salary_and_allowances DOUBLE PRECISION,
    pay_through_date DATE,
    primary_termination_category TEXT,
    primary_termination_reason TEXT,
    probation_end_date INTEGER,
    probation_start_date INTEGER,
    reason_reference_id TEXT,
    regrettable_termination BOOLEAN,
    rehire BOOLEAN,
    resignation_date INTEGER,
    retired BOOLEAN,
    retirement_date INTEGER,
    retirement_eligibility_date INTEGER,
    return_unknown BOOLEAN,
    seniority_date DATE,
    severance_date INTEGER,
    terminated BOOLEAN,
    termination_date DATE,
    termination_involuntary BOOLEAN,
    termination_last_day_of_work DATE,
    time_off_service_date INTEGER,
    universal_id INTEGER,
    user_id TEXT,
    vesting_date INTEGER,
    worker_code INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY worker_history FROM '$1/data/$DB_NAME/worker_history.csv' DELIMITER ',' CSV HEADER;"
