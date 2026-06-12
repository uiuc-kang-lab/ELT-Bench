# Column Mismatch Summary

## Database: food_inspection_2
## Table: employees
## Column: INSPECTION_PASS_RATE

**Description:**
The inspection pass rate of the employee

---

## Root Cause
**Two errors: (1) SQL includes "Pass w/ Conditions" which should be excluded, and (2) SQL returns decimal instead of percentage**

### Incorrect SQL Logic
```sql
CASE
    WHEN COUNT(DISTINCT i.inspection_id) > 0 THEN
        CAST(COUNT(DISTINCT CASE WHEN i.results IN ('Pass', 'Pass w/ Conditions') THEN i.inspection_id END) AS FLOAT) / COUNT(DISTINCT i.inspection_id)
    ELSE 0
END as inspection_pass_rate
```

### Correct SQL Logic
```sql
CASE
    WHEN COUNT(DISTINCT i.inspection_id) > 0 THEN
        CAST(COUNT(DISTINCT CASE WHEN i.results = 'Pass' THEN i.inspection_id END) AS FLOAT) / COUNT(DISTINCT i.inspection_id) * 100
    ELSE NULL
END as inspection_pass_rate
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The pass rate should count ONLY inspections with result exactly 'Pass'
  * The result should be expressed as a percentage (0-100), not a decimal (0-1)
  * Employees with no inspections should have NULL, not 0

* **What the SQL actually computes:**
  * Counts both 'Pass' AND 'Pass w/ Conditions' as passing
  * Returns the result as a decimal (e.g., 0.71) instead of percentage (e.g., 71.0)
  * Returns 0 for employees with no inspections instead of NULL

**Inspection results distribution:**
| Result | Count |
| ------ | ----- |
| Pass | 84,792 |
| Fail | 27,845 |
| Pass w/ Conditions | 13,567 |
| Out of Business | 13,243 |
| No Entry | 3,762 |
| Not Ready | 618 |

---

## Evidence

**Key comparison demonstrating the error:**

| Employee ID | Wrong Logic (decimal, includes PwC) | Correct Logic (%, Pass only) | Ground Truth |
| ----------- | ----------------------------------- | ---------------------------- | ------------ |
| 103705 | 0.7165 | 63.64 | 63.64 |
| 104633 | 0.7024 | 62.04 | 62.04 |
| 106581 | 0.7018 | 62.44 | 62.44 |
| 111559 | 0.6842 | 60.58 | 60.58 |
| 112202 | 0.6802 | 58.87 | 58.87 |

**Detailed example - Employee 103705:**
- Total inspections: 1,111
- 'Pass': 707
- 'Pass w/ Conditions': 89
- 'Fail': 280
- 'Out of Business': 35

Wrong calculation: (707 + 89) / 1111 = 0.7165 (71.65% as decimal)
Correct calculation: 707 / 1111 * 100 = 63.64%

**Impact:**
* Current implementation: **48/75 matches (64.0%)**
* Corrected implementation: **75/75 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insights are:
1. "Pass rate" counts only exact 'Pass' results, not 'Pass w/ Conditions'
2. The rate must be expressed as a percentage (multiplied by 100)
3. Employees with no inspections should have NULL values, not 0
