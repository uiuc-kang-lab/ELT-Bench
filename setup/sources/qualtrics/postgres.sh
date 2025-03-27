# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="qualtrics"    # Name of the new database
TABLE_NAME="directory"
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
  id TEXT PRIMARY KEY,
  _fivetran_deleted BOOLEAN,
  _fivetran_synced TIMESTAMP,
  deduplication_criteria_email BOOLEAN,
  deduplication_criteria_external_data_reference BOOLEAN,
  deduplication_criteria_first_name BOOLEAN,
  deduplication_criteria_last_name BOOLEAN,
  deduplication_criteria_phone BOOLEAN,
  is_default BOOLEAN,
  name TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE survey_embedded
(
  import_id TEXT,
  key TEXT,
  response_id TEXT,
  value BIGINT,
  _fivetran_synced TIMESTAMP
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY survey_embedded FROM '$1/data/$DB_NAME/survey_embedded.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE survey_response
(
  id TEXT PRIMARY KEY,
  _fivetran_synced TIMESTAMP,
  distribution_channel TEXT,
  duration_in_seconds BIGINT,
  end_date TEXT,
  finished BIGINT,
  ip_address TEXT,
  last_modified_date TEXT,
  location_latitude BIGINT,
  location_longitude BIGINT,
  progress BIGINT,
  recipient_email TEXT,
  recipient_first_name TEXT,
  recipient_last_name TEXT,
  recorded_date TIMESTAMP,
  start_date TIMESTAMP,
  status BIGINT,
  survey_id TEXT,
  user_language TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY survey_response FROM '$1/data/$DB_NAME/survey_response.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE survey_version
(
  id BIGINT PRIMARY KEY,
  survey_id TEXT,
  _fivetran_deleted BOOLEAN,
  _fivetran_synced TIMESTAMP,
  creation_date TEXT,
  description TEXT,
  published BOOLEAN,
  user_id TEXT,
  version_number BIGINT,
  was_published BOOLEAN
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY survey_version FROM '$1/data/$DB_NAME/survey_version.csv' DELIMITER ',' CSV HEADER;"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE survey
(
  id TEXT PRIMARY KEY,
  _fivetran_deleted BOOLEAN,
  _fivetran_synced TIMESTAMP,
  auto_scoring_category BIGINT,
  brand_base_url TEXT,
  brand_id TEXT,
  bundle_short_name BIGINT,
  composition_type BIGINT,
  creator_id TEXT,
  default_scoring_category BIGINT,
  division_id BIGINT,
  is_active BIGINT,
  last_accessed TIMESTAMP,
  last_activated TEXT,
  last_modified TEXT,
  option_active_response_set TEXT,
  option_anonymize_response BIGINT,
  option_auto_confirm_start BIGINT,
  option_autoadvance BOOLEAN,
  option_autoadvance_pages BOOLEAN,
  option_autofocus BOOLEAN,
  option_available_languages BIGINT,
  option_back_button BOOLEAN,
  option_ballot_box_stuffing_prevention BOOLEAN,
  option_collect_geo_location BIGINT,
  option_confirm_start BIGINT,
  option_custom_styles TEXT,
  option_email_thank_you BIGINT,
  option_eosredirect_url BIGINT,
  option_highlight_questions TEXT,
  option_inactive_survey BIGINT,
  option_new_scoring BIGINT,
  option_next_button TEXT,
  option_no_index TEXT,
  option_page_transition TEXT,
  option_partial_data TEXT,
  option_partial_data_close_after BIGINT,
  option_password_protection BIGINT,
  option_previous_button TEXT,
  option_progress_bar_display TEXT,
  option_protect_selection_ids BIGINT,
  option_recaptcha_v_3 BIGINT,
  option_referer_check BIGINT,
  option_referer_url BIGINT,
  option_relevant_id BIGINT,
  option_relevant_idlockout_period BIGINT,
  option_response_summary BIGINT,
  option_save_and_continue BOOLEAN,
  option_secure_response_files BOOLEAN,
  option_show_export_tags BIGINT,
  option_skin TEXT,
  option_skin_library TEXT,
  option_skin_question_width BIGINT,
  option_skin_type TEXT,
  option_survey_creation_date TEXT,
  option_survey_expiration TEXT,
  option_survey_language TEXT,
  option_survey_meta_description BIGINT,
  option_survey_name BIGINT,
  option_survey_protection TEXT,
  option_survey_termination TEXT,
  option_survey_title TEXT,
  option_validate_message BIGINT,
  owner_id TEXT,
  project_category TEXT,
  project_type TEXT,
  registry_sha BIGINT,
  registry_version BIGINT,
  schema_version BIGINT,
  scoring_summary_after_questions BOOLEAN,
  scoring_summary_after_survey BOOLEAN,
  scoring_summary_category BIGINT,
  survey_name TEXT,
  survey_status TEXT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY survey FROM '$1/data/$DB_NAME/survey.csv' DELIMITER ',' CSV HEADER;"
