# Column Mismatch Summary

## Database: movie_3
## Table: customers
## Column: HAS_RENTED_THE_FILM_WITH_THE_HIGHEST_REPLACEMENT_COST

**Description:**
Set to 1 if the customer has rented the film with the highest replacement cost, 0 otherwise.

---

## Root Cause
**SQL uses LIMIT 1 to get only ONE film with max cost, but there are 53 films tied at max replacement_cost (29.99)**

### Incorrect SQL Logic
```sql
highest_replacement_cost_film AS (
    SELECT film_id
    FROM {{ source('airbyte_schema', 'film') }}
    ORDER BY replacement_cost DESC
    LIMIT 1
),

customer_rental_stats AS (
    SELECT
        c.customer_id,
        ...
        MAX(CASE
            WHEN i.film_id = (SELECT film_id FROM highest_replacement_cost_film) THEN 1
            ELSE 0
        END) AS has_rented_highest_cost_film
    ...
)
```

### Correct SQL Logic
```sql
highest_replacement_cost AS (
    SELECT MAX(replacement_cost) AS max_cost
    FROM {{ source('airbyte_schema', 'film') }}
),

highest_replacement_cost_films AS (
    SELECT film_id
    FROM {{ source('airbyte_schema', 'film') }}
    WHERE replacement_cost = (SELECT max_cost FROM highest_replacement_cost)
),

customer_rental_stats AS (
    SELECT
        c.customer_id,
        ...
        MAX(CASE
            WHEN i.film_id IN (SELECT film_id FROM highest_replacement_cost_films) THEN 1
            ELSE 0
        END) AS has_rented_highest_cost_film
    ...
)
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "the customer has rented the film with the highest replacement cost"
* **What the SQL computes**: Checks if customer rented a SINGLE arbitrarily chosen film with max cost
* **What the GT expects**: Checks if customer rented ANY film that has the highest replacement cost

The phrase "the film with the highest replacement cost" should include ALL films tied at the maximum value (29.99), not just one randomly selected film.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | SQL Logic (LIMIT 1) | Correct Logic (ALL max-cost films) |
| ------ | ------------------- | ---------------------------------- |
| Films checked | 1 (film_id=34, ARABIA DOGMA) | 53 films at $29.99 |
| Inventory items | ~5 | 246 |
| Rentals of these films | ~13 | 868 |
| Customers with flag=1 | 13 | 468 |

**Sample of 53 films with max replacement_cost ($29.99):**
- ARABIA DOGMA (34)
- BALLROOM MOCKINGBIRD (52)
- BLINDNESS GUN (81)
- BONNIE HOLOCAUST (85)
- CHARIOTS CONSPIRACY (138)
- ... (48 more films)

**Impact:**
* Current implementation: **144/599 matches (24.0%)**
* Corrected implementation: **599/599 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
When there are ties for the maximum value, the SQL must consider ALL tied records, not just one arbitrary selection. Using `LIMIT 1` without a deterministic `ORDER BY` returns an unpredictable single film, missing 52 other films with the same maximum replacement cost.

**Customers who rented at least one max-cost film (468 total):**
These customers rented any of the 53 films priced at the maximum replacement cost of $29.99.
