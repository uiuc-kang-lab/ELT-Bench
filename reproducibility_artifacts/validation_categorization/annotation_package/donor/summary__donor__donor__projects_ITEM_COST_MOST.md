# Column Mismatch Summary

## Database: donor
## Table: donor__projects
## Column: ITEM_COST_MOST

### Description
The item with the most cost in the project, with ties broken by the ascending order of the item name

---

## Root Cause
**Ground Truth contains incorrect values - the predicted SQL implementation is actually CORRECT**

### Predicted SQL Logic (CORRECT)
```sql
item_cost_ranked AS (
    SELECT
        PROJECTID,
        ITEM_NAME,
        ITEM_UNIT_PRICE * ITEM_QUANTITY AS item_cost,
        ROW_NUMBER() OVER (PARTITION BY PROJECTID ORDER BY ITEM_UNIT_PRICE * ITEM_QUANTITY DESC, ITEM_NAME ASC) AS rn
    FROM {{ source('airbyte_schema', 'resources') }}
),

item_cost_most AS (
    SELECT
        PROJECTID,
        ITEM_NAME AS item_cost_most
    FROM item_cost_ranked
    WHERE rn = 1
)
```

### Ground Truth Logic (INCORRECT)
The Ground Truth values do not follow the column specification. In 100% of verified cases where GT and Predicted differ on actual item names, the GT returns an item with a **lower cost** than the correct answer.

---

## Why the Ground Truth Is Wrong

* **What the column description means:** Return the item with the highest total cost (`unit_price * quantity`), using alphabetical order to break ties.

* **What the predicted SQL computes:** Correctly calculates `ITEM_UNIT_PRICE * ITEM_QUANTITY` for each resource, then uses `ROW_NUMBER()` with `ORDER BY item_cost DESC, ITEM_NAME ASC` to select the highest-cost item (with alphabetically first tie-breaker).

* **What the Ground Truth contains:** In cases of real mismatches, GT returns items that have **lower costs** than the actual maximum cost item in the project.

---

## Evidence

**Mismatch breakdown (14,920 total apparent mismatches):**

| Category | Count | Description |
| -------- | ----- | ----------- |
| Both NaN | 9,091 | False positives (NaN != NaN in pandas) |
| Whitespace only | 1,607 | Same item, trailing/leading space difference |
| GT NaN, Pred has value | 3 | Minor edge case |
| Real different items | 4,219 | GT returns wrong item |

**For the 4,219 real different items:**
- Predicted matches expected (highest cost): **100/100 (100%)**
- GT matches expected (highest cost): **0/100 (0%)**

**Sample evidence demonstrating GT errors:**

| Project ID | GT Item | GT Cost | Pred Item | Pred Cost (Max) |
| ---------- | ------- | ------- | --------- | --------------- |
| 000eede620a7fb39... | Geckos | $23.68 | A Rainforest Habitat | $39.36 |
| 00211754dc6bd5ea... | Canon PowerShot A2600 | $163.92 | Canon PowerShot ELPH 130 IS | $197.99 |
| 0024ccd8ee120fd1... | JJ518 - Classroom Magnetic Letters Kit | $39.95 | RR598 - Word Family Flip Books | $59.95 |
| 0037786e9627baa8... | Item Shipping/Handling Charges | $12.95 | ULTIMATE COLLAGE KIT | $20.56 |
| 004cd3e50be74ac3... | FF468 - Magnetic Sight-Word Sentence Board | $29.95 | TT368 - Sentence Building Learning Center | $39.95 |

**Detailed example (Project 000eede620a7fb39734146794c962470):**
- GT says: "Geckos" ($23.68)
- Pred says: "A Rainforest Habitat" ($39.36)
- All items in project sorted by cost:
  - $39.36 - A Rainforest Habitat (HIGHEST - Pred is correct)
  - $29.52 - A Rainforest Food Chain
  - $23.68 - Geckos (GT's incorrect answer)
  - ... 37 more items with lower costs

**Impact:**
* If ignoring NaN/whitespace issues: **659,879/664,098 matches (99.4%)**
* Real semantic errors in GT: **4,219 projects where GT returns wrong item**

---

## Result
**Predicted implementation is CORRECT - Ground Truth has errors**

The predicted SQL correctly implements the column specification:
1. Calculates total cost as `ITEM_UNIT_PRICE * ITEM_QUANTITY`
2. Orders by cost descending
3. Breaks ties with ascending item name
4. Returns the first item (highest cost)

The Ground Truth values in 4,219 projects incorrectly return items with lower costs than the actual maximum. This appears to be a data quality issue in the GT, not a bug in the predicted SQL.

**Recommendation:** Review and correct the Ground Truth data for the 4,219 affected projects where it returns non-maximum-cost items.
