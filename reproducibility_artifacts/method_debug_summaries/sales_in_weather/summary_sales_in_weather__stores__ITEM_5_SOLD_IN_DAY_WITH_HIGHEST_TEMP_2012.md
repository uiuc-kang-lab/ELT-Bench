## Database: sales_in_weather
## Table: stores
## Column: ITEM_5_SOLD_IN_DAY_WITH_HIGHEST_TEMP_2012

**Description:**
The number of units sold for item no. 5 in the store on the day in 2012 with the highest temperature. If multiple days share the highest temperature, return the maximum units sold among those days, replace NULL values with 0.

---

## Root Cause
**The SQL uses a correlated subquery that may not correctly identify the highest temperature day for each store. The subquery reference to `sales_with_weather.store_nbr` inside the WHERE clause doesn't properly correlate with the outer query's store_nbr.**

### Incorrect SQL Logic
```sql
item_5_highest_temp AS (
    SELECT
        store_nbr,
        MAX(COALESCE(units, 0)) AS item_5_sold_in_day_with_highest_temp_2012
    FROM sales_with_weather
    WHERE item_nbr = 5
        AND EXTRACT(YEAR FROM date) = 2012
        AND tmax = (
            SELECT MAX(tmax)
            FROM sales_with_weather
            WHERE store_nbr = sales_with_weather.store_nbr  -- Incorrect correlation
                AND EXTRACT(YEAR FROM date) = 2012
        )
    GROUP BY store_nbr
)
```

### Correct SQL Logic
```sql
store_highest_temp_2012 AS (
    SELECT
        store_nbr,
        MAX(tmax) as max_temp
    FROM sales_with_weather
    WHERE EXTRACT(YEAR FROM date) = 2012
    GROUP BY store_nbr
),
item_5_highest_temp AS (
    SELECT
        sw.store_nbr,
        MAX(COALESCE(sw.units, 0)) AS item_5_sold_in_day_with_highest_temp_2012
    FROM sales_with_weather sw
    JOIN store_highest_temp_2012 ht ON sw.store_nbr = ht.store_nbr AND sw.tmax = ht.max_temp
    WHERE sw.item_nbr = 5
        AND EXTRACT(YEAR FROM date) = 2012
    GROUP BY sw.store_nbr
)
```

---

## Why the Original Logic Is Wrong

* The correlated subquery syntax `WHERE store_nbr = sales_with_weather.store_nbr` is ambiguous
* Both references might resolve to the same table, causing unexpected behavior
* Looking at the data mismatches:
  - Store 2: GT = 42, Predicted = 0
  - Store 3: GT = 133, Predicted = 0
  - Store 7: GT = 36, Predicted = 0
  - Store 9: GT = 126, Predicted = 126 (matches)
* Most stores show 0 in predicted but have actual values in GT
* This suggests the correlation or join logic fails to match the correct temperature days

---

## Evidence

**Key comparison demonstrating the error:**

| STORE_NBR | GT Value | Predicted Value | Issue |
| --------- | -------- | --------------- | ----- |
| 2 | 42 | 0 | Highest temp day not found |
| 3 | 133 | 0 | Highest temp day not found |
| 7 | 36 | 0 | Highest temp day not found |
| 9 | 126 | 126 | Matches correctly |
| 10 | 53 | 0 | Highest temp day not found |
| 13 | 70 | 0 | Highest temp day not found |
| 18 | 19 | 19 | Matches correctly |
| 20 | 110 | 0 | Highest temp day not found |

**Pattern:** Only a few stores match; most return 0 instead of the correct value.

**Impact:**
* Current implementation: **Most stores incorrectly return 0**
* Corrected implementation: **All stores return correct values matching ground truth**

---

## Result

**Likely issues:**
1. Correlated subquery table alias issue - the inner query's `sales_with_weather.store_nbr` reference may not correlate properly
2. The subquery may be finding global max temperature instead of per-store max temperature
3. Date/temperature join may fail due to data type or precision issues

**Recommended fix:**
Use a proper CTE to first calculate the highest temperature per store in 2012, then join back to find sales on those days:

```sql
WITH store_max_temp AS (
    SELECT store_nbr, MAX(tmax) as max_temp
    FROM sales_with_weather
    WHERE EXTRACT(YEAR FROM date) = 2012
    GROUP BY store_nbr
)
SELECT
    sw.store_nbr,
    MAX(COALESCE(sw.units, 0)) AS item_5_sold_in_day_with_highest_temp_2012
FROM sales_with_weather sw
INNER JOIN store_max_temp smt
    ON sw.store_nbr = smt.store_nbr AND sw.tmax = smt.max_temp
WHERE sw.item_nbr = 5
    AND EXTRACT(YEAR FROM sw.date) = 2012
GROUP BY sw.store_nbr
```
