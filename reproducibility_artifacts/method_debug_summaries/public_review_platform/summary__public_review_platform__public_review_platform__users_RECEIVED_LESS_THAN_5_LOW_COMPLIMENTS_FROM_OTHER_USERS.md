# Column Mismatch Summary

## Database: public_review_platform
## Table: public_review_platform__users
## Column: RECEIVED_LESS_THAN_5_LOW_COMPLIMENTS_FROM_OTHER_USERS

### Description
Set to 1 if the user has received less than 5 low compliments from other users, 0 otherwise.

---

## Root Cause
**Two errors: Wrong filter column and missing lower bound condition**

The query incorrectly:
1. Filters on `COMPLIMENTS.COMPLIMENT_TYPE = 'low'` (which doesn't exist) instead of `USERS_COMPLIMENTS.NUMBER_OF_COMPLIMENTS = 'Low'`
2. Uses `count < 5` instead of `count > 0 AND count < 5` - users with 0 low compliments should get 0, not 1

### Incorrect SQL Logic
```sql
low_compliments AS (
    SELECT
        uc.USER_ID,
        COUNT(*) AS low_compliments_count
    FROM {{ source('airbyte_schema', 'USERS_COMPLIMENTS') }} uc
    JOIN {{ source('airbyte_schema', 'COMPLIMENTS') }} c
        ON uc.COMPLIMENT_ID = c.COMPLIMENT_ID
    WHERE c.COMPLIMENT_TYPE = 'low'  -- ERROR: 'low' is not a compliment_type
    GROUP BY uc.USER_ID
)

-- In final SELECT:
CASE
    WHEN COALESCE(lc.low_compliments_count, 0) < 5 THEN 1  -- ERROR: includes users with 0 compliments
    ELSE 0
END AS received_less_than_5_low_compliments_from_other_users
```

### Correct SQL Logic
```sql
low_compliments AS (
    SELECT
        uc.USER_ID,
        COUNT(*) AS low_compliments_count
    FROM {{ source('airbyte_schema', 'USERS_COMPLIMENTS') }} uc
    WHERE uc.NUMBER_OF_COMPLIMENTS = 'Low'  -- Filter on NUMBER_OF_COMPLIMENTS column
    GROUP BY uc.USER_ID
)

-- In final SELECT:
CASE
    WHEN COALESCE(lc.low_compliments_count, 0) > 0
     AND COALESCE(lc.low_compliments_count, 0) < 5 THEN 1  -- Must have received SOME but less than 5
    ELSE 0
END AS received_less_than_5_low_compliments_from_other_users
```

---

## Why the Original Logic Is Wrong

### Error 1: Wrong column for "low"
* **What the column description means**: Count users who received compliments categorized as "Low" quantity
* **What the SQL actually computes**: Tries to filter on `COMPLIMENT_TYPE = 'low'` which doesn't exist

**Schema semantics from `source_schemas`:**
- `COMPLIMENTS.compliment_type`: Types are 'cool', 'cute', 'funny', 'hot', 'list', 'more', 'note', 'photos', 'plain', 'profile', 'writer' - there is NO 'low' type
- `USERS_COMPLIMENTS.number_of_compliments`: Values are 'Low', 'Medium', 'High', 'Uber' - this is where "low" refers to

### Error 2: Condition logic for "received less than 5"
* **What the column description means**: Users who HAVE received low compliments, but fewer than 5 of them
* **What the SQL computes**: Users with fewer than 5, including users with 0 (who never received any low compliments)

The phrase "received less than 5 low compliments" implies the user HAS received some low compliments. Users with 0 low compliments didn't "receive less than 5" - they received none.

---

## Evidence

**Key comparison demonstrating the error:**

| Low Compliment Count | Wrong Logic (GT Expected) | Correct Logic | Ground Truth |
| -------------------- | ------------------------- | ------------- | ------------ |
| 0 | 1 | 0 | 0 |
| 1 | 1 | 1 | 1 |
| 2 | 1 | 1 | 1 |
| 3 | 1 | 1 | 1 |
| 4 | 1 | 1 | 1 |
| 5 | 0 | 0 | 0 |
| 6+ | 0 | 0 | 0 |

**Distribution of low compliment counts:**
- 0 low compliments: 44,245 users (GT=0)
- 1-4 low compliments: 19,759 users (GT=1)
- 5+ low compliments: 6,813 users (GT=0)

**Impact:**
* Current implementation: **19,759/70,817 matches (27.9%)**
* Corrected implementation: **70,817/70,817 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Users where `RECEIVED_LESS_THAN_5_LOW_COMPLIMENTS_FROM_OTHER_USERS = 1`:**
* Users who have received between 1 and 4 'Low' category compliments (19,759 users total)
* Sample user_ids: 3, 19, 45, 53, 102, 115, 120, 146, 151, 157...

**Users where `RECEIVED_LESS_THAN_5_LOW_COMPLIMENTS_FROM_OTHER_USERS = 0`:**
* Users with 0 low compliments (44,245 users) - never received any
* Users with 5+ low compliments (6,813 users) - received 5 or more
