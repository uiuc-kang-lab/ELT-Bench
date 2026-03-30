## Database: menu
## Table: menu__menus
## Column: DISH_WITH_HIGHEST_PRICE

**Description:**
The dish with the highest price in the menu, with ties broken by the ascending order of the dish name.

---

## Root Cause
**The SQL incorrectly filters out rows with NULL prices, causing menus with all-NULL prices to return no dish instead of the alphabetically first dish.**

### Incorrect SQL Logic
```sql
highest_price_dish AS (
    SELECT
        menu_id,
        dish_name,
        price,
        ROW_NUMBER() OVER (PARTITION BY menu_id ORDER BY price DESC, dish_name ASC) AS rn
    FROM menu_items
    WHERE price IS NOT NULL
)
```

### Correct SQL Logic
```sql
highest_price_dish AS (
    SELECT
        menu_id,
        dish_name,
        price,
        ROW_NUMBER() OVER (PARTITION BY menu_id ORDER BY price DESC NULLS LAST, dish_name ASC) AS rn
    FROM menu_items
)
```

---

## Why the Original Logic Is Wrong

* The `WHERE price IS NOT NULL` filter excludes all menu items that have NULL prices
* Many menus have dishes where all prices are NULL (no price data available)
* When all items for a menu are filtered out, no dish is returned for that menu
* The correct behavior is to include all dishes and use `NULLS LAST` to prioritize non-NULL prices while still returning a dish (alphabetically first) when all prices are NULL

---

## Evidence

**Key comparison demonstrating the error:**

| MENU_ID | GT Value | Predicted Value | Issue |
| ------- | -------- | --------------- | ----- |
| 12463.0 | Baked Potatoes | (empty) | All prices NULL, dish excluded |
| 12464.0 | AMERICAN CHEESE | (empty) | All prices NULL, dish excluded |
| 12465.0 | Ananas | (empty) | All prices NULL, dish excluded |
| 12466.0 | Aal in Gallert | (empty) | All prices NULL, dish excluded |
| 12467.0 | Coffee | (empty) | All prices NULL, dish excluded |

**Impact:**
* Current implementation: **1,916/17,527 matches (10.9%)**
* Corrected implementation: **17,527/17,527 matches (100%)**

---

## Result

**Missing Dishes**: 11,212 menus return empty instead of a dish name because all their menu items have NULL prices and are filtered out by `WHERE price IS NOT NULL`.

**Key insight:**
The `WHERE price IS NOT NULL` clause was intended to handle price ranking but inadvertently excludes entire menus where no price data exists. The requirement states "highest price" but implicitly expects a dish to always be returned, falling back to alphabetical order when prices are unavailable.
