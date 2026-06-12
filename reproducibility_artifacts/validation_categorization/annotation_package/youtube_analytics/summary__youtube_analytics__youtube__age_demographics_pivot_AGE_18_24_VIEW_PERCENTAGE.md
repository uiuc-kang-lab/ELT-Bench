# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__age_demographics_pivot
## Column: AGE_18_24_VIEW_PERCENTAGE

**Description:**
Total number of views percent attributed to the age range 18 - 24 years old.

---

## Root Cause
**Wrong aggregation function: SQL uses MAX() but GT uses SUM()/100**

### Incorrect SQL Logic
```sql
pivoted_demographics AS (
    SELECT
        date_day,
        video_id,
        MAX(CASE WHEN age_group = 'AGE_18_24' THEN views_percentage ELSE NULL END) AS AGE_18_24_view_percentage
    FROM channel_demographics
    GROUP BY date_day, video_id
)
```

### Correct SQL Logic
```sql
pivoted_demographics AS (
    SELECT
        date_day,
        video_id,
        SUM(CASE WHEN age_group = 'AGE_18_24' THEN views_percentage ELSE 0 END) / 100 AS AGE_18_24_view_percentage
    FROM channel_demographics
    GROUP BY date_day, video_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Total number of views percent" implies summing all percentage contributions
  * The source table `channel_demographics` has multiple rows per video+date+age_group (different countries and genders)
  * Each row represents a percentage contribution that should be aggregated

* **What the SQL actually computes:**
  * Uses `MAX()` which only takes the highest single value among all country/gender combinations
  * This loses all other percentage contributions for the same age group

* **Schema insight:**
  * `channel_demographics` has granular data: one row per (date, video_id, age_group, country_code, gender)
  * The `views_percentage` values are in percent form (12.5 = 12.5%)
  * GT divides by 100 to convert to decimal form (0.125 = 12.5%)

---

## Evidence

**Key comparison demonstrating the error:**

| Video | Age Group | Source Rows | MAX (Wrong) | SUM/100 (Correct) | GT |
| ----- | --------- | ----------- | ----------- | ----------------- | -- |
| THK0DyoSVTs | AGE_18_24 | (no data) | NULL | 0.0 | 0.0 |
| t91FEgxdojg | AGE_18_24 | 12.5 | 12.5 | 0.125 | 0.125 |

**Calculation breakdown for t91FEgxdojg, AGE_18_24:**
- 1 source row
- SUM = 12.5
- SUM/100 = 0.125 (matches GT exactly)
- MAX = 12.5 (wrong - not divided by 100)

**Impact:**
* Current implementation: **0/2 matches (0%)**
* Corrected implementation: **2/2 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The source data (`channel_demographics`) contains granular view percentages broken down by country and gender. To get the "total" view percentage for an age group, all these individual percentages must be summed, then divided by 100 to convert from percentage points to decimal form.
