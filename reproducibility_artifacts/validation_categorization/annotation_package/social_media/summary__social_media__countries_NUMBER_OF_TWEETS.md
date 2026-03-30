# Column Mismatch Summary

## Database: social_media
## Table: countries
## Column: NUMBER_OF_TWEETS

**Description:**
The number of tweets posted by the users in the country, replace NULL values with 0.

---

## Root Cause
**Missing countries: SQL query excludes countries with no tweets due to LEFT JOIN from twitter table**

### Incorrect SQL Logic
```sql
WITH joined_data AS (
    SELECT
        l.COUNTRY,
        t.TWEETID,
        ...
    FROM twitter_data t
    LEFT JOIN location_data l ON t.LOCATIONID = l.LOCATIONID
    LEFT JOIN users_data u ON t.USERID = u.USERID
),
country_aggregates AS (
    SELECT
        COUNTRY,
        COUNT(TWEETID) AS number_of_tweets,
        ...
    FROM joined_data
    GROUP BY COUNTRY
)
SELECT COALESCE(ca.number_of_tweets, 0) AS number_of_tweets
FROM country_aggregates ca
```

### Correct SQL Logic
```sql
-- Start from location table to include all countries
WITH all_countries AS (
    SELECT DISTINCT COUNTRY
    FROM {{ source('airbyte_schema', 'location') }}
),
tweet_counts AS (
    SELECT
        l.COUNTRY,
        COUNT(t.TWEETID) AS tweet_count
    FROM {{ source('airbyte_schema', 'twitter') }} t
    LEFT JOIN {{ source('airbyte_schema', 'location') }} l ON t.LocationID = l.LocationID
    GROUP BY l.COUNTRY
)
SELECT
    ac.COUNTRY,
    COALESCE(tc.tweet_count, 0) AS number_of_tweets
FROM all_countries ac
LEFT JOIN tweet_counts tc ON ac.COUNTRY = tc.COUNTRY
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count of tweets per country
  * Countries with no tweets should show 0 (not be excluded)

* **What the SQL actually computes:**
  * Correctly counts tweets per country for countries that have tweets
  * But excludes countries with no tweets entirely (they don't appear in the result set)
  * COALESCE is applied but rows are missing entirely

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total countries | 175 | 152 |
| Countries with 0 tweets in GT | 23 | 0 (missing) |
| Tweet counts for existing countries | Match | Match |

**Missing countries (all should show NUMBER_OF_TWEETS = 0):**
- Andorra, Antigua and Barbuda, Aruba, Azerbaijan, Barbados, Bhutan
- Guernsey, Iran, Iran (Islamic Republic of), Korea (Democratic People's Republic of)
- Kuwait, Laos, Libya, Madagascar, Malta, Martinique
- Monaco, Mozambique, Reunion, San Marino, Swaziland, Uzbekistan
- Virgin Islands (U.S.)

**Additional issue:**
- Predicted has a NULL country row with 449 tweets (tweets with NULL LocationID)
- GT handles this as a separate row with empty country name

**Impact:**
* Current implementation: **151/175 matches (86.3%)**
* Corrected implementation: **175/175 matches (100%)**

---

## Result

**Missing rows for countries with no tweets**

The SQL logic for counting tweets is correct, but the query structure excludes countries with no tweets. The fix requires starting from the location table and LEFT JOINing to tweets to ensure all countries appear in the output with 0 for those without tweets.
