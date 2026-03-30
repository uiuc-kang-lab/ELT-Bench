# Column Mismatch Summary

## Database: food_inspection
## Table: restaurants
## Column: VIOLATION_PER_INSPECTION

**Description:**
The average number of violations per inspection the restaurant has.

---

## Root Cause
**Wrong counting method: SQL uses COUNT(DISTINCT date) instead of COUNT(*) for both violations and inspections, resulting in incorrect ratios**

### Incorrect SQL Logic
```sql
violation_stats AS (
    SELECT
        v.BUSINESS_ID,
        COUNT(DISTINCT v.DATE) AS total_violations,
        COUNT(DISTINCT i.DATE) AS total_inspections
    FROM violations v
    LEFT JOIN inspections i ON v.BUSINESS_ID = i.BUSINESS_ID
    GROUP BY v.BUSINESS_ID
)
-- Then: total_violations / total_inspections
```

### Correct SQL Logic
```sql
violation_counts AS (
    SELECT
        BUSINESS_ID,
        COUNT(*) AS total_violations
    FROM violations
    GROUP BY BUSINESS_ID
),
inspection_counts AS (
    SELECT
        BUSINESS_ID,
        COUNT(*) AS total_inspections
    FROM inspections
    GROUP BY BUSINESS_ID
)
-- Then: total_violations / total_inspections
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Total number of violations divided by total number of inspections
  * Simple ratio: `COUNT(violations) / COUNT(inspections)`

* **What the SQL actually computes:**
  * `COUNT(DISTINCT violation dates)` / `COUNT(DISTINCT inspection dates)`
  * This gives the ratio of unique violation days to unique inspection days
  * Completely different meaning - loses information about multiple violations on the same day

**The fundamental errors:**
1. Uses `COUNT(DISTINCT DATE)` instead of `COUNT(*)` for violations
2. Uses `COUNT(DISTINCT DATE)` instead of `COUNT(*)` for inspections
3. The JOIN creates a Cartesian product issue when counting

---

## Evidence

**Key comparison demonstrating the error:**

| Business ID | Total Violations | Total Inspections | Unique Viol Dates | Unique Insp Dates | Wrong Logic | Correct Logic | Ground Truth |
| ----------- | ---------------- | ----------------- | ----------------- | ----------------- | ----------- | ------------- | ------------ |
| 10 | 10 | 6 | 3 | 6 | 0.50 | 1.67 | 1.67 |
| 24 | 17 | 5 | 5 | 5 | 1.00 | 3.40 | 3.40 |
| 31 | 7 | 5 | 3 | 5 | 0.60 | 1.40 | 1.40 |
| 45 | 5 | 4 | 3 | 4 | 0.75 | 1.25 | 1.25 |
| 48 | 5 | 3 | 3 | 3 | 1.00 | 1.67 | 1.67 |

**Detailed example - Business 10:**
- Has 10 total violations
- Has 6 total inspections
- Has 3 unique violation dates (multiple violations on same day)
- Has 6 unique inspection dates
- Wrong calculation: 3 / 6 = 0.50
- Correct calculation: 10 / 6 = 1.67
- Ground Truth: 1.67

**Impact:**
* Current implementation: **2298/6358 matches (36.1%)**
* Corrected implementation: **6358/6358 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "violations per inspection" is a straightforward ratio of total counts, not a ratio of unique dates. A restaurant may receive multiple violations during a single inspection visit, and all of these should be counted individually.

**Test results from different interpretations:**
| Method | Description | Match Rate |
| ------ | ----------- | ---------- |
| Current | DISTINCT dates from violations table | 36.1% |
| Method 2 | Total violations / Total inspections | **100%** |
| Method 3 | Unique violation dates / Total inspections | 37.1% |
| Method 4 | Total violations / Unique inspection dates | 83.2% |
