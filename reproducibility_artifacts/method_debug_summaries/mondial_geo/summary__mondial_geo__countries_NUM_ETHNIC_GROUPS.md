# Column Mismatch Summary

## Database: mondial_geo
## Table: countries
## Column: NUM_ETHNIC_GROUPS

**Description:**
The number of ethnic groups in the country, replace NULL values with 0.

---

## Root Cause
**No issue - SQL logic is correct**

### Current SQL Logic (Correct)
```sql
ethnic_groups AS (
    SELECT
        COUNTRY AS country_code,
        NAME AS ethnic_group_name,
        CAST(PERCENTAGE AS FLOAT) AS percentage,
        ROW_NUMBER() OVER (PARTITION BY COUNTRY ORDER BY CAST(PERCENTAGE AS FLOAT) DESC, NAME ASC) AS rn,
        COUNT(*) OVER (PARTITION BY COUNTRY) AS num_ethnic_groups
    FROM ETHNICGROUP
),

majority_ethnic_group AS (
    SELECT
        country_code,
        ethnic_group_name AS the_majority_ethnic_group,
        num_ethnic_groups
    FROM ethnic_groups
    WHERE rn = 1
)

SELECT
    COALESCE(meg.num_ethnic_groups, 0) AS num_ethnic_groups
FROM country_base cb
LEFT JOIN majority_ethnic_group meg ON cb.country_code = meg.country_code
```

---

## Why the Original Logic Is Correct

* **What the column description means:**
  * Count of distinct ethnic groups recorded for the country
  * NULL values should be replaced with 0

* **What the SQL actually computes:**
  * Uses COUNT(*) OVER (PARTITION BY COUNTRY) to count ethnic groups per country
  * LEFT JOINs with country_base to include countries without ethnic group data
  * Uses COALESCE to replace NULL with 0

---

## Evidence

**Impact:**
* Current implementation: **238/238 matches (100%)**

---

## Result

**Perfect match - no changes needed**

The SQL correctly:
1. Counts all ethnic groups per country using window function
2. Handles countries with no ethnic group data via LEFT JOIN
3. Uses COALESCE to replace NULL with 0 as required
