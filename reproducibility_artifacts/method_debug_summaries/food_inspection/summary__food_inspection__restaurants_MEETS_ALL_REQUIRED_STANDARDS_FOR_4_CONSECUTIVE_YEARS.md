# Column Mismatch Summary

## Database: food_inspection
## Table: restaurants
## Column: MEETS_ALL_REQUIRED_STANDARDS_FOR_4_CONSECUTIVE_YEARS

**Description:**
Set to 1 if the restaurant meets all required standards for 4 consecutive years, otherwise, set to 0

---

## Root Cause
**Missing requirement for valid scored inspections: SQL only checks for inspections with no violations, but also requires at least one inspection with a valid (non-null) score in each year**

### Incorrect SQL Logic
```sql
-- Get all years with inspections but no violations
clean_years AS (
    SELECT
        yi.BUSINESS_ID,
        yi.inspection_year
    FROM yearly_inspections yi
    LEFT JOIN yearly_violations yv
        ON yi.BUSINESS_ID = yv.BUSINESS_ID
        AND yi.inspection_year = yv.violation_year
    WHERE yv.violation_year IS NULL
)
-- Then check for 4 consecutive clean years
```

### Correct SQL Logic
```sql
-- Get years with at least one SCORED inspection (non-null score) and no violations
clean_years AS (
    SELECT
        yi.BUSINESS_ID,
        yi.inspection_year
    FROM (
        SELECT BUSINESS_ID, YEAR(DATE) AS inspection_year
        FROM inspections
        WHERE SCORE IS NOT NULL  -- Must have at least one scored inspection
        GROUP BY BUSINESS_ID, YEAR(DATE)
    ) yi
    LEFT JOIN yearly_violations yv
        ON yi.BUSINESS_ID = yv.BUSINESS_ID
        AND yi.inspection_year = yv.violation_year
    WHERE yv.violation_year IS NULL
)
-- Then check for 4 consecutive clean years
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Restaurant must have 4 consecutive years where it "meets all required standards"
  * "Meeting standards" requires:
    1. Having at least one actual scored inspection in that year (not just "New Construction" or other non-scored visits)
    2. Having no violations recorded in that year

* **What the SQL actually computes:**
  * Only checks for any inspection record (regardless of whether it has a score)
  * Counts years with only "New Construction", "Non-inspection site visit", etc. as valid
  * These inspection types have NULL scores and don't represent actual compliance checks

**Key insight from source data:**
- Several inspection types have NULL scores: "New Construction", "Reinspection/Followup", "Non-inspection site visit", "New Ownership"
- These are administrative visits, not compliance inspections
- A year with only these types of inspections should NOT count as "meeting standards"

---

## Evidence

**Key comparison demonstrating the error:**

| Business ID | GT | Pred | Issue |
| ----------- | -- | ---- | ----- |
| 2871 | 0 | 1 | 2016 has only "New Construction" inspection (NULL score) |
| 3503 | 0 | 1 | 2016 has only "New Construction" inspection (NULL score) |
| 16286 | 0 | 1 | 2016 has only "New Construction" inspections (all NULL scores) |
| 71640 | 0 | 1 | 2013 has only "New Construction" inspections (NULL scores) |
| 75465 | 0 | 1 | 2013 & 2015 have only non-scored inspections |

**Detailed example - Business 2871:**
| Year | Inspection Type | Score | Violations |
| ---- | --------------- | ----- | ---------- |
| 2013 | Routine - Unscheduled | 100.0 | 0 |
| 2014 | New Construction | NULL | 0 |
| 2014 | New Construction | NULL | 0 |
| 2014 | Routine - Unscheduled | 100.0 | 0 |
| 2015 | Routine - Unscheduled | 100.0 | 0 |
| 2016 | New Construction | **NULL** | 0 |

- Wrong logic: Counts 2016 as a "clean year" because there's an inspection record with no violations
- Correct logic: 2016 doesn't count because it has no scored inspection
- Result: Only 3 consecutive years with valid inspections (2013-2015), not 4

**Impact:**
* Current implementation: **6349/6358 matches (99.9%)**
* Corrected implementation: **6354/6358 matches (99.9%)**

**Note:** 4 businesses (2002, 35340, 68196, 72153) have GT=1 but have violations in some years. These may be data quality issues in the ground truth, as the strict interpretation (requiring no violations AND scored inspections) achieves 99.9% match.

---

## Result

**Near-perfect match with corrected logic (99.9%)**

The key insight is that "meeting standards" requires an actual compliance inspection (with a score), not just any inspection record. Non-scored visits like "New Construction" or "New Ownership" are administrative and don't verify compliance.

**Businesses correctly excluded by corrected logic (GT=0, were incorrectly marked as 1):**
- Business 2871: 2016 only has New Construction (no scored inspection)
- Business 3503: 2016 only has New Construction (no scored inspection)
- Business 16286: 2016 only has New Construction inspections (no scored inspection)
- Business 71640: 2013 only has New Construction inspections (no scored inspection)
- Business 75465: 2013 and 2015 have no scored inspections
