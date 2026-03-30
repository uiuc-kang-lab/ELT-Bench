# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__video_report
## Column: VIDEO_DURATION_SECONDS

**Description:**
The total duration of the video in seconds.

---

## Root Cause
**Format mismatch: SQL returns ISO 8601 duration string instead of numeric seconds**

### Incorrect SQL Logic
```sql
video AS (
    SELECT
        id AS video_id,
        content_details_duration AS video_duration_seconds  -- Returns 'PT31M28S'
    FROM {{ source('airbyte_schema', 'video') }}
)
```

### Correct SQL Logic
```sql
video AS (
    SELECT
        id AS video_id,
        -- Parse ISO 8601 duration to seconds
        COALESCE(
            EXTRACT(HOUR FROM PARSE_DURATION(content_details_duration)) * 3600 +
            EXTRACT(MINUTE FROM PARSE_DURATION(content_details_duration)) * 60 +
            EXTRACT(SECOND FROM PARSE_DURATION(content_details_duration)),
            0
        ) AS video_duration_seconds
    FROM {{ source('airbyte_schema', 'video') }}
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The duration should be a numeric value in seconds
  * Example: A 31-minute 28-second video should be 1888 seconds

* **What the SQL actually computes:**
  * Directly passes through the `content_details_duration` column from source
  * This column contains ISO 8601 duration format strings (e.g., 'PT31M28S')
  * No conversion to seconds is performed

* **Schema insight:**
  * Source `video` table has `content_details_duration` in ISO 8601 format
  * Example: 'PT49M19S' = 49 minutes 19 seconds = 2959 seconds
  * Example: 'PT31M28S' = 31 minutes 28 seconds = 1888 seconds

---

## Evidence

**Key comparison demonstrating the error:**

| Video ID | Pred (ISO 8601) | GT (Seconds) | Parsed |
| -------- | --------------- | ------------ | ------ |
| 1IXX_cSR1qc | PT31M28S | 1888.0 | 1888 |
| t91FEgxdojg | PT49M19S | 2959.0 | 2959 |

**Impact:**
* Current implementation: **0/454 matches (0%)** - all values are strings instead of numbers
* Corrected implementation: **454/454 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The source data stores video duration in ISO 8601 format (PTxHxMxS). The SQL must parse this format and convert to numeric seconds to match the expected output format.
