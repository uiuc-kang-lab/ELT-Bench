# Column Mismatch Summary

## Database: social_media
## Table: countries
## Column: NUMBER_OF_LIKES

**Description:**
The number of likes on tweets from the country, replace NULL values with 0.

---

## Root Cause
**Missing countries: SQL query excludes countries with no tweets due to LEFT JOIN from twitter table**

### Incorrect SQL Logic
```sql
WITH joined_data AS (
    SELECT
        l.COUNTRY,
        t.LIKES,
        ...
    FROM twitter_data t
    LEFT JOIN location_data l ON t.LOCATIONID = l.LOCATIONID
    ...
),
country_aggregates AS (
    SELECT
        COUNTRY,
        COALESCE(SUM(LIKES), 0) AS number_of_likes
    FROM joined_data
    GROUP BY COUNTRY
)
```

### Correct SQL Logic
```sql
-- Start from location table to include all countries
WITH all_countries AS (
    SELECT DISTINCT COUNTRY
    FROM {{ source('airbyte_schema', 'location') }}
),
likes_per_country AS (
    SELECT
        l.COUNTRY,
        COALESCE(SUM(t.Likes), 0) AS total_likes
    FROM {{ source('airbyte_schema', 'twitter') }} t
    LEFT JOIN {{ source('airbyte_schema', 'location') }} l ON t.LocationID = l.LocationID
    GROUP BY l.COUNTRY
)
SELECT
    ac.COUNTRY,
    COALESCE(lpc.total_likes, 0) AS number_of_likes
FROM all_countries ac
LEFT JOIN likes_per_country lpc ON ac.COUNTRY = lpc.COUNTRY
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Sum of likes on tweets from each country
  * Countries with no tweets should show 0

* **What the SQL actually computes:**
  * Correctly sums likes for countries that have tweets
  * But excludes countries with no tweets entirely (they don't appear in the result set)

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total countries | 175 | 152 |
| Countries with non-zero likes | 1 (United States) | 1 (United States) |
| United States likes | 15277.0 | 15277.0 |
| Countries with 0 likes | 174 | 151 (missing 23) |

**Likes data summary:**
- Total likes in database: 15,277
- All likes are from United States tweets
- Most tweets have 0 likes (75th percentile = 0)

**Missing countries (all should show NUMBER_OF_LIKES = 0):**
- Andorra, Antigua and Barbuda, Aruba, Azerbaijan, Barbados, Bhutan
- Guernsey, Iran, Iran (Islamic Republic of), Korea (Democratic People's Republic of)
- Kuwait, Laos, Libya, Madagascar, Malta, Martinique
- Monaco, Mozambique, Reunion, San Marino, Swaziland, Uzbekistan
- Virgin Islands (U.S.)

**Impact:**
* Current implementation: **152/175 matches (86.9%)**
* Corrected implementation: **175/175 matches (100%)**

---

## Result

**Missing rows for countries with no tweets**

The likes calculation itself is correct (COALESCE(SUM(LIKES), 0)), but countries with no tweets are excluded from the result. The fix requires starting from the location table to ensure all countries appear in the output.
