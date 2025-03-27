# Variables
DB_USER="postgres"       # PostgreSQL username (change as needed)
DB_PASSWORD="testelt"  # PostgreSQL password (optional, only needed if using password auth)
DB_NAME="linkedin"    # Name of the new database
TABLE_NAME="ad_analytics_by_campaign"
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
   campaign_id INTEGER,
    day TIMESTAMP WITHOUT TIME ZONE,
    action_clicks INTEGER,
    ad_unit_clicks INTEGER,
    approximate_unique_impressions INTEGER,
    card_clicks INTEGER,
    card_impressions INTEGER,
    clicks INTEGER,
    comment_likes INTEGER,
    comments INTEGER,
    company_page_clicks INTEGER,
    conversion_value_in_local_currency INTEGER,
    cost_in_local_currency DOUBLE PRECISION,
    cost_in_usd DOUBLE PRECISION,
    external_website_conversions INTEGER,
    external_website_post_click_conversions INTEGER,
    external_website_post_view_conversions INTEGER,
    follows INTEGER,
    full_screen_plays INTEGER,
    impressions INTEGER,
    landing_page_clicks INTEGER,
    lead_generation_mail_contact_info_shares INTEGER,
    lead_generation_mail_interested_clicks INTEGER,
    likes INTEGER,
    one_click_lead_form_opens INTEGER,
    one_click_leads INTEGER,
    opens INTEGER,
    other_engagements INTEGER,
    shares INTEGER,
    text_url_clicks INTEGER,
    total_engagements INTEGER,
    video_completions INTEGER,
    video_first_quartile_completions INTEGER,
    video_midpoint_completions INTEGER,
    video_starts INTEGER,
    video_third_quartile_completions INTEGER,
    video_views INTEGER,
    viral_card_clicks INTEGER,
    viral_card_impressions INTEGER,
    viral_clicks INTEGER,
    viral_comment_likes INTEGER,
    viral_comments INTEGER,
    viral_company_page_clicks INTEGER,
    viral_external_website_conversions INTEGER,
    viral_external_website_post_click_conversions INTEGER,
    viral_external_website_post_view_conversions INTEGER,
    viral_follows INTEGER,
    viral_full_screen_plays INTEGER,
    viral_impressions INTEGER,
    viral_landing_page_clicks INTEGER,
    viral_likes INTEGER,
    viral_one_click_lead_form_opens INTEGER,
    viral_one_click_leads INTEGER,
    viral_other_engagements INTEGER,
    viral_shares INTEGER,
    viral_total_engagements INTEGER,
    viral_video_completions INTEGER,
    viral_video_first_quartile_completions INTEGER,
    viral_video_midpoint_completions INTEGER,
    viral_video_starts INTEGER,
    viral_video_third_quartile_completions INTEGER,
    viral_video_views INTEGER
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY $TABLE_NAME FROM '$1/data/$DB_NAME/$TABLE_NAME.csv' DELIMITER ',' CSV HEADER;"


PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "
CREATE TABLE ad_analytics_by_creative
(
   creative_id INT,
    day TIMESTAMP WITHOUT TIME ZONE,
    action_clicks INT,
    card_clicks INT,
    ad_unit_clicks INT,
    landing_page_clicks INT,
    clicks INT,
    approximate_unique_impressions INT,
    impressions INT,
    card_impressions INT,
    cost_in_local_currency INT,
    cost_in_usd INT,
    comment_likes INT,
    comments INT,
    company_page_clicks INT,
    conversion_value_in_local_currency INT,
    external_website_conversions INT,
    external_website_post_click_conversions INT,
    external_website_post_view_conversions INT,
    follows INT,
    full_screen_plays INT,
    lead_generation_mail_contact_info_shares INT,
    lead_generation_mail_interested_clicks INT,
    likes INT,
    one_click_lead_form_opens INT,
    one_click_leads INT,
    opens INT,
    other_engagements INT,
    shares INT,
    text_url_clicks INT,
    total_engagements INT,
    video_completions INT,
    video_first_quartile_completions INT,
    video_midpoint_completions INT,
    video_starts INT,
    video_third_quartile_completions INT,
    video_views INT,
    viral_card_clicks INT,
    viral_card_impressions INT,
    viral_clicks INT,
    viral_comment_likes INT,
    viral_comments INT,
    viral_company_page_clicks INT,
    viral_external_website_conversions INT,
    viral_external_website_post_click_conversions INT,
    viral_external_website_post_view_conversions INT,
    viral_follows INT,
    viral_full_screen_plays INT,
    viral_impressions INT,
    viral_landing_page_clicks INT,
    viral_likes INT,
    viral_one_click_lead_form_opens INT,
    viral_one_click_leads INT,
    viral_other_engagements INT,
    viral_shares INT,
    viral_total_engagements INT,
    viral_video_completions INT,
    viral_video_first_quartile_completions INT,
    viral_video_midpoint_completions INT,
    viral_video_starts INT,
    viral_video_third_quartile_completions INT,
    viral_video_views INT
);
"

PGPASSWORD=$DB_PASSWORD psql -h $HOST -U $DB_USER -p $DB_PORT -d $DB_NAME -c "\COPY ad_analytics_by_creative FROM '$1/data/$DB_NAME/ad_analytics_by_creative.csv' DELIMITER ',' CSV HEADER;"
