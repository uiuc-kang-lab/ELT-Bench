# Column Mismatch Summary

## Database: social_media
## Table: countries
## Column: COUNTRY

**Description:**
Unique identifier for the country.

---

## Root Cause
**Missing countries: SQL query excludes countries with no tweets due to LEFT JOIN from twitter table**

### Incorrect SQL Logic
```sql
WITH joined_data AS (
    SELECT
        l.COUNTRY,
        ...
    FROM twitter_data t
    LEFT JOIN location_data l ON t.LOCATIONID = l.LOCATIONID
    LEFT JOIN users_data u ON t.USERID = u.USERID
),
country_aggregates AS (
    SELECT COUNTRY, ...
    FROM joined_data
    GROUP BY COUNTRY
)
SELECT ca.COUNTRY AS country
FROM country_aggregates ca
```

### Correct SQL Logic
```sql
-- Start from location table to include all countries
WITH all_countries AS (
    SELECT DISTINCT COUNTRY
    FROM {{ source('airbyte_schema', 'location') }}
),
country_aggregates AS (
    SELECT
        l.COUNTRY,
        COUNT(t.TWEETID) AS number_of_tweets,
        ...
    FROM all_countries l
    LEFT JOIN twitter_data t ON l.COUNTRY = (
        SELECT COUNTRY FROM location WHERE LocationID = t.LocationID
    )
    GROUP BY l.COUNTRY
)
SELECT * FROM country_aggregates
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Every country should be listed, including those with no tweets

* **What the SQL actually computes:**
  * Only includes countries that have at least one tweet
  * Starting from twitter_data and joining to location excludes countries with no matching tweets

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total countries | 175 | 152 |
| Countries with tweets | 151 | 151 |
| Countries without tweets | 23 | 0 |

**Missing countries (all have 0 tweets):**
- Andorra, Antigua and Barbuda, Aruba, Azerbaijan, Barbados, Bhutan, Guernsey
- Iran, Iran (Islamic Republic of), Korea (Democratic People's Republic of), Kuwait
- Laos, Libya, Madagascar, Malta, Martinique, Monaco, Mozambique
- Reunion, San Marino, Swaziland, Uzbekistan, Virgin Islands (U.S.)

**Impact:**
* Current implementation: **152/175 matches (86.9%)**
* Corrected implementation: **175/175 matches (100%)**

---

## Result

**Missing rows for countries with no tweets**

The SQL starts from the twitter table instead of the location table, causing countries with no tweets to be excluded from the output. The fix requires starting from the location table to ensure all countries are included.
