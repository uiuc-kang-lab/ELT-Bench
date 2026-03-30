# Column Mismatch Summary

## Database: food_inspection
## Table: restaurants
## Column: NUM_OF_INSPECTIONS_BECAUSE_OF_COMPLAINT

**Description:**
The number of inspections the restaurant has because of a complaint, replace NULL values with 0.

---

## Root Cause
**Over-inclusive filter: SQL uses `LIKE '%COMPLAINT%'` which also matches "Complaint Reinspection/Followup" inspections, but these are follow-ups, not original complaint inspections**

### Incorrect SQL Logic
```sql
complaint_inspections AS (
    SELECT
        BUSINESS_ID,
        COUNT(*) AS num_of_inspections_because_of_complaint
    FROM inspections
    WHERE UPPER(TYPE) LIKE '%COMPLAINT%'
    GROUP BY BUSINESS_ID
)
```

### Correct SQL Logic
```sql
complaint_inspections AS (
    SELECT
        BUSINESS_ID,
        COUNT(*) AS num_of_inspections_because_of_complaint
    FROM inspections
    WHERE TYPE = 'Complaint'
    GROUP BY BUSINESS_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count inspections that were initiated **because of a complaint**
  * These are original complaint-driven inspections, not follow-up visits

* **What the SQL actually computes:**
  * Uses `LIKE '%COMPLAINT%'` which matches:
    * `Complaint` (1,474 records) - correct
    * `Complaint Reinspection/Followup` (124 records) - incorrect
  * Total: 1,598 records instead of 1,474

**Inspection type values in source data:**
| Type | Count | Should Include? |
| ---- | ----- | --------------- |
| Routine - Unscheduled | 13,007 | No |
| Reinspection/Followup | 4,758 | No |
| New Ownership | 1,739 | No |
| New Construction | 1,662 | No |
| **Complaint** | **1,474** | **Yes** |
| Non-inspection site visit | 728 | No |
| Structural Inspection | 153 | No |
| **Complaint Reinspection/Followup** | **124** | **No** |
| Foodborne Illness Investigation | 73 | No |
| ... | ... | ... |

---

## Evidence

**Key comparison demonstrating the error:**

| Business ID | Wrong Logic (LIKE '%COMPLAINT%') | Correct Logic (= 'Complaint') | Ground Truth |
| ----------- | -------------------------------- | ----------------------------- | ------------ |
| 10 | 1 | 0 | 0 |
| 56 | 2 | 1 | 1 |
| 393 | 2 | 1 | 1 |
| 496 | 2 | 1 | 1 |
| 505 | 2 | 1 | 1 |

**Example - Business 10:**
- Has 6 inspections total
- One inspection type is "Complaint Reinspection/Followup" (a follow-up visit)
- Wrong logic counts this as 1 complaint inspection
- Correct logic: 0 (no original "Complaint" type inspection)

**Impact:**
* Current implementation: **6260/6358 matches (98.5%)**
* Corrected implementation: **6358/6358 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "Complaint Reinspection/Followup" is a follow-up visit after an original complaint inspection, not a new complaint inspection itself. Only inspections with type exactly equal to "Complaint" should be counted.
