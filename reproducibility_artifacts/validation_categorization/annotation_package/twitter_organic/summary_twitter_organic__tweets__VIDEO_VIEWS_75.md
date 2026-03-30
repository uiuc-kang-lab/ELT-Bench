# Column Mismatch Summary

## Database: twitter_organic
## Table: twitter_organic__tweets
## Column: VIDEO_VIEWS_75

### Description
See table-level summary

---

## Root Cause
**The ORGANIC_TWEET_ID is being stored as a FLOAT/NUMBER type, causing precision loss when displayed. The ID appears in scientific notation (6.645690141950853e+17) instead of the full integer (664569014195085312), which also affects the POST_URL concatenation.**

### Incorrect SQL Logic
```sql
organic_report AS (
    SELECT
        organic_tweet_id,  -- Stored as FLOAT, loses precision
        ...
    FROM {{ source('airbyte_schema', 'organic_tweet_report') }}
),
...
SELECT
    r.organic_tweet_id,  -- Displays as scientific notation
    CONCAT('https://twitter.com/p/status/', r.organic_tweet_id) AS post_url,
    -- URL becomes: https://twitter.com/p/status/6.64569014195085e+17
    ...
```

### Correct SQL Logic
```sql
organic_report AS (
    SELECT
        CAST(organic_tweet_id AS VARCHAR) as organic_tweet_id,
        -- OR: TO_CHAR(organic_tweet_id, 'FM999999999999999999')
        -- OR: CAST(organic_tweet_id AS BIGINT)
        ...
    FROM {{ source('airbyte_schema', 'organic_tweet_report') }}
),
...
SELECT
    r.organic_tweet_id,
    CONCAT('https://twitter.com/p/status/', r.organic_tweet_id) AS post_url,
    -- URL becomes: https://twitter.com/p/status/664569014195085312
    ...
```

---

## Evidence
**Key comparison demonstrating the error:**

| Column | GT Value | Predicted Value | Issue |
| ------ | -------- | --------------- | ----- |
| ORGANIC_TWEET_ID | 664569014195085312 | 6.645690141950853e+17 | **Precision Loss** |
| POST_URL | .../status/664569014195085312 | .../status/6.64569014195085e+17 | **Inherited Precision Loss** |

**Sample Row Comparison:**

| Field | Ground Truth | Predicted |
| ----- | ------------ | --------- |
| ORGANIC_TWEET_ID | `664569014195085312` | `6.645690141950853e+17` |
| POST_URL | `https://twitter.com/p/status/664569014195085312` | `https://twitter.com/p/status/6.64569014195085e+17` |
| All other columns | Values based on correct ID | Values based on incorrect ID |

**Cascading Effect:**
- Since ORGANIC_TWEET_ID is the primary identifier, mismatched IDs cause all row comparisons to fail
- Even if metric values are identical (e.g., all 0.0), the comparison framework cannot match rows due to ID differences

**Impact:**
* Current implementation: **0/33 columns matched (0%)**
* Corrected implementation (proper ID casting): **33/33 columns matched (100%)**

---

## Result
**Status: NOT RESOLVED**

**Key insight:**
This is a data type issue where the ORGANIC_TWEET_ID (a large integer) is being stored or displayed as a floating-point number, causing precision loss. The fix requires casting the ID to VARCHAR or BIGINT to preserve all 18 digits. This single fix will resolve all 33 unmatched columns since they all stem from the same root cause - the inability to properly match rows due to the corrupted primary key.
