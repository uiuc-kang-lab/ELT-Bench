# Column Mismatch Summary

## Database: software_company
## Table: geo
## Column: PER_ELDERLY_CUSTOMER_NEVER_MARRIED

**Description:**
The percentage of elderly customers who have never been married in the place.

---

## Root Cause
**Two errors: (1) Wrong age threshold (>= 65 instead of > 65), and (2) Wrong denominator (elderly customers instead of all customers)**

### Incorrect SQL Logic
```sql
elderly_never_married AS (
    SELECT
        c.geoid,
        COUNT(CASE WHEN c.age >= 65 AND c.marital_status = 'Never-married' THEN 1 END) * 100.0 /
        NULLIF(COUNT(CASE WHEN c.age >= 65 THEN 1 END), 0) AS per_elderly_customer_never_married
    FROM customers c
    GROUP BY c.geoid
)
```

### Correct SQL Logic
```sql
elderly_never_married AS (
    SELECT
        c.geoid,
        COUNT(CASE WHEN c.age > 65 AND c.marital_status = 'Never-married' THEN 1 END) * 100.0 /
        NULLIF(COUNT(*), 0) AS per_elderly_customer_never_married
    FROM customers c
    GROUP BY c.geoid
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The percentage of elderly customers who have never been married"
  * This is interpreted as: what percentage of ALL customers are both elderly AND never-married
  * Elderly is defined as age > 65 (strictly greater than)

* **What the SQL actually computes:**
  * Wrong interpretation: "Among elderly customers (age >= 65), what percentage are never-married"
  * Uses age >= 65 instead of age > 65
  * Uses elderly count as denominator instead of total customer count

* **Two distinct errors:**
  1. **Age threshold error**: `age >= 65` includes 65-year-olds, but GT uses `age > 65`
  2. **Denominator error**: Divides by elderly count, but should divide by total customer count

---

## Evidence

**Key comparison demonstrating the error:**

| GEOID | Total Customers | >65 Count | >65 Never-Married | Wrong Logic | Correct Logic | Ground Truth |
| ----- | --------------- | --------- | ----------------- | ----------- | ------------- | ------------ |
| 0     | 29              | 9         | 6                 | 66.67%      | 20.69%        | 20.69%       |
| 10    | 39              | 13        | 4                 | 30.77%      | 10.26%        | 10.26%       |
| 100   | 97              | 24        | 12                | 48.00%      | 12.37%        | 12.37%       |
| 101   | 76              | 23        | 5                 | 21.74%      | 6.58%         | 6.58%        |
| 8     | 24              | 6         | 2                 | 42.86%      | 8.33%         | 8.33%        |

**Formula verification:**
- GEOID 0: Wrong = 6/9 * 100 = 66.67%, Correct = 6/29 * 100 = 20.69%
- GEOID 8: Wrong = 2/6 * 100 = 33.33%*, Correct = 2/24 * 100 = 8.33%

*Note: The wrong calculation also uses >= 65 (7 elderly), while correct uses > 65 (6 elderly)

**Impact:**
* Current implementation: **~42% matches** (due to wrong formula)
* Corrected implementation: **200/200 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insights:**
1. The term "elderly" in this context means age > 65 (strictly greater than), not age >= 65
2. The phrase "percentage of elderly customers who have never been married" means "what percentage of ALL customers are elderly AND never-married" (not "among elderly, what percentage are never-married")

**Correct interpretation:**
- Numerator: Count of customers with age > 65 AND marital_status = 'Never-married'
- Denominator: Count of ALL customers (not just elderly ones)
