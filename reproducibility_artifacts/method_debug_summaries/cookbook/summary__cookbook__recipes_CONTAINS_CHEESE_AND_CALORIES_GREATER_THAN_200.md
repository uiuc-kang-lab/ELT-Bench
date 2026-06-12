# Column Mismatch Summary

## Database: cookbook
## Table: recipes
## Column: CONTAINS_CHEESE_AND_CALORIES_GREATER_THAN_200

**Description:**
Set to 1 if the recipe contains cheese and the calories are greater than 200, otherwise, set to 0

---

## Root Cause
**Semantic error: SQL uses LIKE '%cheese%' on ingredient name instead of using the ingredient category='cheese' to identify actual cheese ingredients**

### Incorrect SQL Logic
```sql
cheese_recipes AS (
    SELECT DISTINCT
        q.RECIPE_ID
    FROM {{ source('airbyte_schema', 'QUANTITY') }} q
    INNER JOIN {{ source('airbyte_schema', 'INGREDIENT') }} i
        ON q.INGREDIENT_ID = i.INGREDIENT_ID
    WHERE LOWER(i.NAME) LIKE '%cheese%'
)
```

### Correct SQL Logic
```sql
cheese_recipes AS (
    SELECT DISTINCT
        q.RECIPE_ID
    FROM {{ source('airbyte_schema', 'QUANTITY') }} q
    INNER JOIN {{ source('airbyte_schema', 'INGREDIENT') }} i
        ON q.INGREDIENT_ID = i.INGREDIENT_ID
    WHERE LOWER(i.CATEGORY) = 'cheese'
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Contains cheese" = the recipe uses an ingredient that is actual cheese
  * The Ingredient table has a `category` column that classifies ingredients
  * Ingredients with `category='cheese'` are actual cheese products (cheddar, mozzarella, parmesan, etc.)

* **What the SQL actually computes:**
  * The SQL uses `LIKE '%cheese%'` on the ingredient name
  * This incorrectly matches:
    * Dairy products: "cottage cheese", "cream cheese", "lowfat Swiss cheese" (category='dairy')
    * Pasta products: "dry cheese tortellini", "cheese-filled tortellini" (category='pasta/noodles')
    * Salad dressings: "blue cheese salad dressing" (category='salad dressings')
  * These are NOT actual cheese - they are products that contain "cheese" in their name but belong to different categories

**Schema verification:**
- `Ingredient.category`: "the category of the ingredient"
- `Ingredient.name`: "the name of the ingredient"

The category column provides proper classification:
- `category='cheese'`: 83 ingredients (actual cheese products)
- Ingredients with 'cheese' in name: 98 ingredients (includes dairy, pasta, dressings)

---

## Evidence

**Key comparison demonstrating the error:**

| Recipe ID | Title | Ingredient Matching 'cheese' in Name | Ingredient Category | Calories | Wrong Logic | Correct Logic | GT |
| --------- | ----- | ------------------------------------ | ------------------- | -------- | ----------- | ------------- | -- |
| 288.0 | It's The Berries Pie | 1% lowfat cottage cheese | dairy | 410.84 | 1 | 0 | 0 |
| 305.0 | Nectarine-Strawberry Shortcake Torte | light cream cheese | dairy | 336.6 | 1 | 0 | 0 |
| 531.0 | Lamb Tortellini Minestrone | dry cheese tortellini | pasta/noodles | 331.46 | 1 | 0 | 0 |
| 579.0 | Peach Pita Sandwiches | 1% lowfat cottage cheese | dairy | 538.58 | 1 | 0 | 0 |
| 599.0 | Noodle-Crusted Quiche Noel | 1% lowfat cottage cheese | dairy | 203.11 | 1 | 0 | 0 |
| 699.0 | Stuffed Baked Potato | lowfat creamed cottage cheese | dairy | 254.92 | 1 | 0 | 0 |
| 1104.0 | Turkey Pastrami and Swiss in Rye | lowfat Swiss cheese | dairy | 320.34 | 1 | 0 | 0 |
| 1348.0 | Kahlua Chocolate Cheesecake | cream cheese | dairy | 434.92 | 1 | 0 | 0 |
| 1410.0 | No-Bake Chocolate Cheesecake | cream cheese | dairy | 548.44 | 1 | 0 | 0 |

**Example demonstrating the difference:**
- Recipe 305 (Nectarine-Strawberry Shortcake Torte):
  - Uses ingredient 2048 ("light cream cheese", category='dairy')
  - Calories: 336.6
  - Wrong logic: `LIKE '%cheese%'` matches "light cream cheese" -> 1
  - Correct logic: `category='cheese'` does NOT match (category='dairy') -> 0
  - GT = 0

**Statistics:**
- Recipes with 'cheese' in ingredient name: 108
- Recipes with actual cheese (category='cheese'): 90
- All 9 mismatches are cases where LIKE '%cheese%' matches non-cheese ingredients

**Impact:**
* Current implementation: **1022/1031 matches (99.1%)**
* Corrected implementation: **1031/1031 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that the Ingredient table has a proper `category` classification. Products like "cottage cheese", "cream cheese", and "cheese tortellini" are categorized as 'dairy' or 'pasta/noodles', not as 'cheese'. Using `category='cheese'` correctly identifies only actual cheese ingredients.

**Misclassified ingredients by the wrong logic:**
- "1% lowfat cottage cheese" (category='dairy')
- "light cream cheese" (category='dairy')
- "cream cheese" (category='dairy')
- "lowfat creamed cottage cheese" (category='dairy')
- "lowfat Swiss cheese" (category='dairy')
- "dry cheese tortellini" (category='pasta/noodles')
