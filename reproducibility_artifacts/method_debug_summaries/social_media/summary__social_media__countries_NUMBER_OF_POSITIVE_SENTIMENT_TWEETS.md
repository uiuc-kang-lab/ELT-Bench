# Column Mismatch Summary

## Database: social_media
## Table: countries
## Column: NUMBER_OF_POSITIVE_SENTIMENT_TWEETS

**Description:**
The number of tweets with positive sentiment from the country, replace NULL values with 0.

---

## Root Cause
**Missing countries: SQL query excludes countries with no tweets due to LEFT JOIN from twitter table**

### Incorrect SQL Logic
```sql
WITH joined_data AS (
    SELECT
        l.COUNTRY,
        t.SENTIMENT,
        ...
    FROM twitter_data t
    LEFT JOIN location_data l ON t.LOCATIONID = l.LOCATIONID
    ...
),
country_aggregates AS (
    SELECT
        COUNTRY,
        COUNT(CASE WHEN SENTIMENT > 0 THEN 1 END) AS number_of_positive_sentiment_tweets
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
positive_sentiment_counts AS (
    SELECT
        l.COUNTRY,
        COUNT(CASE WHEN t.Sentiment > 0 THEN 1 END) AS pos_count
    FROM {{ source('airbyte_schema', 'twitter') }} t
    LEFT JOIN {{ source('airbyte_schema', 'location') }} l ON t.LocationID = l.LocationID
    GROUP BY l.COUNTRY
)
SELECT
    ac.COUNTRY,
    COALESCE(psc.pos_count, 0) AS number_of_positive_sentiment_tweets
FROM all_countries ac
LEFT JOIN positive_sentiment_counts psc ON ac.COUNTRY = psc.COUNTRY
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count of tweets with positive sentiment (Sentiment > 0) per country
  * Countries with no tweets should show 0

* **What the SQL actually computes:**
  * Correctly counts positive sentiment tweets for countries that have tweets
  * Correctly interprets "positive sentiment" as Sentiment > 0
  * But excludes countries with no tweets entirely (they don't appear in the result set)

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total countries | 175 | 152 |
| Countries with positive tweets | 134 | 134 |
| Countries with 0 positive tweets | 41 | 18 (missing 23) |

**Sentiment data summary:**
- Total tweets with positive sentiment (> 0): 27,007
- Sentiment value range: -6.0 to 7.33
- Current logic `SENTIMENT > 0` is correct interpretation

**Missing countries (all should show NUMBER_OF_POSITIVE_SENTIMENT_TWEETS = 0):**
- Andorra, Antigua and Barbuda, Aruba, Azerbaijan, Barbados, Bhutan
- Guernsey, Iran, Iran (Islamic Republic of), Korea (Democratic People's Republic of)
- Kuwait, Laos, Libya, Madagascar, Malta, Martinique
- Monaco, Mozambique, Reunion, San Marino, Swaziland, Uzbekistan
- Virgin Islands (U.S.)

**Additional issue:**
- Predicted has a NULL country row with 168 positive sentiment tweets
- GT handles this as a separate row with empty country name showing 0

**Impact:**
* Current implementation: **151/175 matches (86.3%)**
* Corrected implementation: **175/175 matches (100%)**

---

## Result

**Missing rows for countries with no tweets**

The positive sentiment counting logic (`SENTIMENT > 0`) is correct, but countries with no tweets are excluded from the result. The fix requires starting from the location table to ensure all countries appear in the output.
