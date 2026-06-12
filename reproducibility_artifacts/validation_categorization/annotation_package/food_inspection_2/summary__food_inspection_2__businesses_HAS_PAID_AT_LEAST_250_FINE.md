# Column Mismatch Summary

## Database: food_inspection_2
## Table: businesses
## Column: HAS_PAID_AT_LEAST_250_FINE

**Description:**
Set to 1 if the facility has paid at least $250 in fines, otherwise, set to 0

---

## Root Cause
**Wrong aggregation: SQL checks if SUM of fines >= 250, but the correct logic checks if any SINGLE fine >= 250**

### Incorrect SQL Logic
```sql
CASE
    WHEN COALESCE(SUM(v.fine), 0) >= 250 THEN 1
    ELSE 0
END as has_paid_at_least_250_fine
```

### Correct SQL Logic
```sql
CASE
    WHEN MAX(v.fine) >= 250 THEN 1
    ELSE 0
END as has_paid_at_least_250_fine
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Paid at least $250 in fines" means having received at least one fine of $250 or more
  * The phrase refers to a single fine payment meeting the threshold, not cumulative fines

* **What the SQL actually computes:**
  * Sums ALL fines for the facility and checks if total >= 250
  * A facility with 25 x $100 fines would incorrectly return 1 (sum = $2500)
  * The correct interpretation: only count if MAX(fine) >= 250

**Fine value analysis:**
- Fine values in the data: 0, 100, 250, 500
- GT=1 facilities: MAX fine is always >= 250 (250 or 500)
- GT=0 facilities: MAX fine is always < 250 (0 or 100)

---

## Evidence

**Key comparison demonstrating the error:**

| License No | Total Fine (SUM) | Max Single Fine | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ---------------- | --------------- | ----------- | ------------- | ------------ |
| 115 | 2,500 | 100 | 1 | 0 | 0 |
| 126 | 400 | 100 | 1 | 0 | 0 |
| 218 | 900 | 100 | 1 | 0 | 0 |
| 271 | 600 | 100 | 1 | 0 | 0 |
| 316 | 600 | 100 | 1 | 0 | 0 |

**Detailed example - License 115:**
- Has 25 violations, each with a $100 fine
- Total fine: 25 x $100 = $2,500
- Max single fine: $100
- Wrong logic: SUM($2,500) >= 250 → 1
- Correct logic: MAX($100) >= 250 → 0
- Ground Truth: 0

**Fine distribution by GT value:**
| Metric | GT=1 Facilities | GT=0 Facilities |
| ------ | --------------- | --------------- |
| Max single fine (min) | 250 | 0 |
| Max single fine (max) | 500 | 100 |
| Total fine (mean) | 3,556 | 311 |

**Impact:**
* Current implementation: **26387/31642 matches (83.4%)**
* Corrected implementation: **31642/31642 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "paid at least $250 in fines" refers to having at least one individual fine payment of $250 or more, not a cumulative total. This is semantically consistent with how fines are typically reported - each violation results in a specific fine amount, and the question is whether any single fine met the $250 threshold.

**Facilities that correctly have HAS_PAID_AT_LEAST_250_FINE = 1:**
- Facilities with at least one fine of $250 or $500
