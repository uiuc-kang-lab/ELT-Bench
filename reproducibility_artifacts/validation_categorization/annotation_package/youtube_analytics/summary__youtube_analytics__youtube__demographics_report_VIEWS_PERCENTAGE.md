# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__demographics_report
## Column: VIEWS_PERCENTAGE

**Description:**
Total percent of views the user makes up for the video.

---

## Root Cause
**Scale mismatch: SQL returns percentage points but GT expects decimal (divided by 100)**

### Incorrect SQL Logic
```sql
SELECT
    cd.date_day,
    cd.video_id,
    cd.age_group,
    cd.country_code,
    cd.gender,
    cd.views_percentage  -- Returns 0.3003 (percentage points)
FROM channel_demographics cd
```

### Correct SQL Logic
```sql
SELECT
    cd.date_day,
    cd.video_id,
    cd.age_group,
    cd.country_code,
    cd.gender,
    cd.views_percentage / 100 AS views_percentage  -- Returns 0.003003 (decimal)
FROM channel_demographics cd
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Total percent of views" should be expressed as a decimal fraction
  * 0.003003 means 0.3003% of total views

* **What the SQL actually computes:**
  * Passes through raw `views_percentage` from source without conversion
  * Returns percentage points (0.3003 = 0.3003%)
  * GT expects decimal form (0.003003 = 0.3003%)

* **Schema insight:**
  * Source `channel_demographics.views_percentage` is in percentage points
  * GT divides by 100 to convert to decimal form

---

## Evidence

**Key comparison demonstrating the error:**

| Video | Age | Country | Gender | Pred (points) | GT (decimal) | Ratio |
| ----- | --- | ------- | ------ | ------------- | ------------ | ----- |
| THK0DyoSVTs | AGE_13_17 | GB | MALE | 0.3003 | 0.003003 | 100 |
| THK0DyoSVTs | AGE_13_17 | IL | MALE | 0.9009 | 0.009009 | 100 |
| THK0DyoSVTs | AGE_65_ | FI | MALE | 0.6006 | 0.006006 | 100 |
| t91FEgxdojg | AGE_18_24 | NO | MALE | 12.5 | 0.125 | 100 |

**Calculation:**
- All Pred values are exactly 100x GT values
- Fix: Divide by 100

**Impact:**
* Current implementation: **0/11 matches (0%)**
* Corrected implementation: **11/11 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The source data stores view percentages in percentage point form (0.3003 = 0.3003%). The GT expects decimal form (0.003003 = 0.3003%). Simply dividing by 100 converts from percentage points to decimal and achieves a perfect match.
