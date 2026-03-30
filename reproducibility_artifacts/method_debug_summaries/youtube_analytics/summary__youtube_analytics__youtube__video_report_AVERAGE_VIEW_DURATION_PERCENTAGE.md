# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__video_report
## Column: AVERAGE_VIEW_DURATION_PERCENTAGE

**Description:**
Average duration of views represented as a percent of the entire length of the video.

---

## Root Cause
**Two issues: (1) Missing aggregation of multiple source rows, (2) Values not divided by 100 to convert to decimal**

### Incorrect SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    cb.average_view_duration_percentage  -- No aggregation, raw percentage value
FROM channel_basic cb
```

### Correct SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    -- Weighted average by views, then divide by 100
    SUM(cb.average_view_duration_percentage * cb.views) / NULLIF(SUM(cb.views), 0) / 100
        AS average_view_duration_percentage
FROM channel_basic cb
GROUP BY cb.date_day, cb.video_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Average view duration as a percentage of total video length
  * Should be aggregated per (date, video) combination
  * GT has values like 0.020853 (2.0853% of video watched)

* **What the SQL actually computes:**
  * Returns raw rows from source without aggregation
  * Values are in percentage points (1.56 = 1.56%)
  * Multiple rows exist per (date, video) due to different country/subscription dimensions

* **Schema insight:**
  * Source `channel_basic` has multiple rows per (date, video_id) with different dimensions
  * GT has 454 rows (one per date+video), Pred has 1000 rows (not aggregated)
  * Source values are in percentage points, GT expects decimal form

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Video | Source Row 1 | Source Row 2 | Pred (no agg) | GT |
| ---- | ----- | ------------ | ------------ | ------------- | -- |
| 2021-07-27 | -serQUrgefU | 1.5614 | 2.6091 | 1.5614, 2.6091 | 0.020853 |

**Calculation for GT value:**
- Source row 1: 1.5614%, 1 view, 8.9 seconds
- Source row 2: 2.6091%, 1 view, 14.872 seconds
- Total views: 2
- Weighted avg: (1.5614*1 + 2.6091*1) / 2 = 2.08525
- Divided by 100: 0.0208525 (matches GT: 0.020853)

**Impact:**
* Current implementation: **0/454 matches (0%)** - multiple rows and wrong scale
* Corrected implementation: **454/454 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The source data has multiple rows per (date, video) representing different demographic dimensions. GT aggregates these using a weighted average (by views) and then divides by 100 to convert from percentage points to decimal form.
