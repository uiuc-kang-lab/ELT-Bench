# Column Mismatch Summary

## Database: food_inspection_2
## Table: businesses
## Column: PER_FAILED_INSPECTIONS

**Description:**
The percentage of failed inspections the facility has.

---

## Root Cause
**Incorrect output format: SQL returns decimal (0-1) instead of percentage (0-100)**

### Incorrect SQL Logic
```sql
CASE
    WHEN COUNT(DISTINCT i.inspection_id) > 0 THEN
        CAST(COUNT(DISTINCT CASE WHEN i.results = 'Fail' THEN i.inspection_id END) AS FLOAT) / COUNT(DISTINCT i.inspection_id)
    ELSE 0
END as per_failed_inspections
```

### Correct SQL Logic
```sql
CASE
    WHEN COUNT(DISTINCT i.inspection_id) > 0 THEN
        CAST(COUNT(DISTINCT CASE WHEN i.results = 'Fail' THEN i.inspection_id END) AS FLOAT) / COUNT(DISTINCT i.inspection_id) * 100
    ELSE 0
END as per_failed_inspections
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Percentage" indicates the value should be in the range 0-100
  * A facility with 1 fail out of 13 inspections should show 7.69%, not 0.0769

* **What the SQL actually computes:**
  * Returns the ratio as a decimal (0.0769)
  * Missing the multiplication by 100 to convert to percentage

---

## Evidence

**Key comparison demonstrating the error:**

| License No | Fail Count | Total Inspections | Wrong Logic (decimal) | Correct Logic (%) | Ground Truth |
| ---------- | ---------- | ----------------- | --------------------- | ----------------- | ------------ |
| 2 | 1 | 13 | 0.0769 | 7.69 | 7.69 |
| 40 | 2 | 8 | 0.2500 | 25.00 | 25.00 |
| 62 | 1 | 7 | 0.1429 | 14.29 | 14.29 |
| 85 | 1 | 5 | 0.2000 | 20.00 | 20.00 |
| 99 | 1 | 13 | 0.0769 | 7.69 | 7.69 |

**Impact:**
* Current implementation: **16201/31642 matches (51.2%)**
* Corrected implementation: **31642/31642 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix is straightforward: multiply the ratio by 100 to convert from decimal to percentage format. The current logic correctly identifies failed inspections (results = 'Fail') but fails to express the result as a percentage.

Note: The 51.2% match rate for the current implementation comes from facilities with 0 failed inspections, where 0.0 = 0.0% = 0 regardless of multiplication.
