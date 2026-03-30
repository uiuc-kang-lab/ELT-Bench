# Column Mismatch Summary

## Database: cookbook
## Table: recipes
## Column: NUM_INGREDIENTS

**Description:**
Number of ingredients in the recipe, replace NULL values with 0.

---

## Root Cause
**Aggregation error: SQL uses COUNT(DISTINCT INGREDIENT_ID) instead of COUNT(*) to count all ingredient entries including duplicates**

### Incorrect SQL Logic
```sql
ingredient_counts AS (
    SELECT
        RECIPE_ID,
        COUNT(DISTINCT INGREDIENT_ID) AS num_ingredients
    FROM {{ source('airbyte_schema', 'QUANTITY') }}
    GROUP BY RECIPE_ID
)
```

### Correct SQL Logic
```sql
ingredient_counts AS (
    SELECT
        RECIPE_ID,
        COUNT(*) AS num_ingredients
    FROM {{ source('airbyte_schema', 'QUANTITY') }}
    GROUP BY RECIPE_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Number of ingredients in the recipe" = count of all ingredient entries in the Quantity table for each recipe
  * Some recipes use the same ingredient multiple times (e.g., sugar used twice with different amounts/preparations)
  * Each entry in the Quantity table represents a separate ingredient usage

* **What the SQL actually computes:**
  * COUNT(DISTINCT INGREDIENT_ID) counts only unique ingredients
  * This misses cases where the same ingredient appears multiple times in a recipe
  * For example, recipe 214 uses ingredient 3334 (sugar) twice - once for 0.25 cup and once for 0.67 cup divided

**Schema verification:**
- `Quantity.quantity_id`: "the unique identifier for the quantity"
- `Quantity.recipe_id`: "the unique identifier for the recipe the quantity is being used for"
- `Quantity.ingredient_id`: "the unique identifier for the ingredient being used"

Each row in Quantity represents a distinct ingredient usage, even if the same ingredient_id appears multiple times.

---

## Evidence

**Key comparison demonstrating the error:**

| Recipe ID | Title | COUNT(DISTINCT) | COUNT(*) | Ground Truth |
| --------- | ----- | --------------- | -------- | ------------ |
| 214.0 | Raspberry Chiffon Pie | 8 | 9 | 9 |
| 225.0 | Blueberry Cobbler | 10 | 13 | 13 |
| 226.0 | Apple Upside Down Cake | 11 | 12 | 12 |
| 238.0 | Chewy Chocolate Hazelnut Cookies | 10 | 11 | 11 |
| 542.0 | Mediterranean Beef Stew | 12 | 13 | 13 |

**Example demonstrating the difference:**
- Recipe 214 (Raspberry Chiffon Pie):
  - Has 9 rows in Quantity table
  - Uses ingredient 3334 (sugar) twice with different amounts
  - COUNT(DISTINCT INGREDIENT_ID) = 8 (misses duplicate)
  - COUNT(*) = 9 (correct)
  - GT = 9

**Statistics:**
- Recipes with duplicate ingredients: 30 out of 1031
- Total mismatches: 30/1031 (2.9%)

**Impact:**
* Current implementation: **1001/1031 matches (97.1%)**
* Corrected implementation: **1031/1031 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that the Quantity table tracks each ingredient usage separately, even when the same ingredient appears multiple times in a recipe. Using COUNT(*) correctly counts all ingredient entries, while COUNT(DISTINCT INGREDIENT_ID) incorrectly collapses duplicate ingredient uses into a single count.

**Recipes with duplicate ingredient entries (sample):**
- Recipe 214: Sugar (ingredient 3334) used twice
- Recipe 225: Multiple duplicate ingredients
- Recipe 226: Multiple duplicate ingredients
