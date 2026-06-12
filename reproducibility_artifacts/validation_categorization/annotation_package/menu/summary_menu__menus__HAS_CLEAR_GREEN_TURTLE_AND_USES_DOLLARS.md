## Database: menu
## Table: menu__menus
## Column: HAS_CLEAR_GREEN_TURTLE_AND_USES_DOLLARS

**Description:**
Set to 1 if the menu has the dish "Clear green turtle" and uses dollars as their currency, 0 otherwise.

---

## Root Cause
**The SQL uses case-sensitive string matching, failing to match dish names with different capitalization like "Clear Green Turtle".**

### Incorrect SQL Logic
```sql
clear_turtle_check AS (
    SELECT
        mi.menu_id,
        MAX(CASE
            WHEN mi.dish_name = 'Clear green turtle' AND m.currency = 'Dollars' THEN 1
            ELSE 0
        END) AS has_clear_turtle_dollars
    FROM menu_items mi
    LEFT JOIN menu_base m ON mi.menu_id = m.menu_id
    GROUP BY mi.menu_id
)
```

### Correct SQL Logic
```sql
clear_turtle_check AS (
    SELECT
        mi.menu_id,
        MAX(CASE
            WHEN LOWER(mi.dish_name) = 'clear green turtle' AND m.currency = 'Dollars' THEN 1
            ELSE 0
        END) AS has_clear_turtle_dollars
    FROM menu_items mi
    LEFT JOIN menu_base m ON mi.menu_id = m.menu_id
    GROUP BY mi.menu_id
)
```

---

## Why the Original Logic Is Wrong

* The SQL checks for exact match `dish_name = 'Clear green turtle'` (lowercase "green turtle")
* The database contains variations like "Clear Green Turtle" (capitalized)
* Case-sensitive comparison causes menus with the capitalized version to be marked as 0 instead of 1
* The fix is to use case-insensitive comparison via `LOWER()` function

---

## Evidence

**Key comparison demonstrating the error:**

| MENU_ID | GT Value | Predicted Value | Issue |
| ------- | -------- | --------------- | ----- |
| 32311.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 32999.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 33137.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 33165.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 33234.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 33941.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 34777.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |
| 35029.0 | 1 | 0 | Has "Clear Green Turtle" (capitalized) |

**Dish name variations in database:**
- "Clear green turtle" (id=11) - matches
- "Clear Green Turtle" (id=383252) - does NOT match due to case

**Impact:**
* Current implementation: **17,519/17,527 matches (99.95%)**
* Corrected implementation: **17,527/17,527 matches (100%)**

---

## Result

**8 Mismatches**: All 8 mismatches are menus that have the dish "Clear Green Turtle" (with capital G and T) instead of "Clear green turtle" (lowercase).

**Key insight:**
The description says to check for the dish "Clear green turtle" - this appears to be case-sensitive in the description, but the ground truth implementation treats it as case-insensitive. A case-insensitive comparison using `LOWER()` would match both variations and produce correct results.
