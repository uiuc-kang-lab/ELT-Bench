# Column Mismatch Summary

## Database: movie_3
## Table: films
## Column: RENTAL_REVENUE

**Description:**
The rental revenue of the film, replace NULL values with 0.

---

## Root Cause
**SQL sums actual payment amounts, but GT calculates rental_rate × rental_duration for each rental**

### Incorrect SQL Logic
```sql
rental_stats AS (
    SELECT
        i.film_id,
        COUNT(DISTINCT r.rental_id) AS num_rented_times,
        COALESCE(SUM(p.amount), 0) AS rental_revenue
    FROM {{ source('airbyte_schema', 'inventory') }} i
    LEFT JOIN {{ source('airbyte_schema', 'rental') }} r ON i.inventory_id = r.inventory_id
    LEFT JOIN {{ source('airbyte_schema', 'payment') }} p ON r.rental_id = p.rental_id
    GROUP BY i.film_id
)
```

### Correct SQL Logic
```sql
rental_stats AS (
    SELECT
        i.film_id,
        COUNT(DISTINCT r.rental_id) AS num_rented_times,
        COALESCE(SUM(f.rental_rate * f.rental_duration), 0) AS rental_revenue
    FROM {{ source('airbyte_schema', 'inventory') }} i
    LEFT JOIN {{ source('airbyte_schema', 'rental') }} r ON i.inventory_id = r.inventory_id
    LEFT JOIN {{ source('airbyte_schema', 'film') }} f ON i.film_id = f.film_id
    GROUP BY i.film_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "The rental revenue of the film"
* **What the SQL computes**: Sum of actual payment amounts (`payment.amount`)
* **What the GT expects**: Sum of (rental_rate × rental_duration) for each rental

The key insight is that "rental revenue" in the GT is calculated as the standard rental fee based on the film's rate and duration, not the actual payment amount which may differ due to:
- Discounts or promotions
- Actual days rented (which may be less than rental_duration)
- Late fees or other adjustments

The GT formula is: `SUM(rental_rate × rental_duration)` for all rentals of the film.

---

## Evidence

**Key comparison demonstrating the error:**

| Film ID | Title | Rentals | rental_rate | rental_duration | GT (rate×duration) | PRED (payment sum) |
| ------- | ----- | ------- | ----------- | --------------- | ------------------ | ------------------ |
| 1 | ACADEMY DINOSAUR | 23 | 0.99 | 6 | 136.62 | 36.77 |
| 2 | ACE GOLDFINGER | 7 | 4.99 | 3 | 104.79 | 52.93 |
| 3 | ADAPTATION HOLES | 12 | 2.99 | 7 | 251.16 | 37.88 |
| 4 | AFFAIR PREJUDICE | 23 | 2.99 | 5 | 343.85 | 91.77 |
| 10 | ALADDIN CALENDAR | 23 | 4.99 | 6 | 688.62 | 131.77 |

**Calculation example for Film 1:**
- 23 rentals × 0.99 (rental_rate) × 6 (rental_duration) = 136.62
- SQL returns: 36.77 (sum of actual payments)

**Payment vs Expected analysis:**
- Payment amounts do NOT always equal rental_rate × rental_duration
- Payment/RentalRate ratio ranges from 0 to 8.07
- Only 8,727 out of 16,049 payments equal the film's rental_rate

**Impact:**
* Current implementation: **43/1000 matches (4.3%)**
* Corrected implementation: **1000/1000 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The GT calculates rental revenue as the theoretical revenue based on standard pricing (rental_rate × rental_duration), not the actual collected payments. This represents what the film "should" generate in revenue per rental based on its pricing structure.

**Films with zero rental revenue (42 films):**
These are films that have no rental records in the database.
