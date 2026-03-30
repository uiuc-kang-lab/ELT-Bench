## Database: retail_complains
## Table: Clients
## Column: PERCENTAGE_OF_COMPLAINT_CALLS_GOT_CONSENT

**Description:**
The percentage of complaint calls that got consent.

---

## Root Cause
**The SQL counts ALL complaints in the denominator, but the ground truth only counts complaints where consent information exists (non-NULL). NULL consent values should be excluded from both numerator and denominator.**

### Incorrect SQL Logic
```sql
consent_percentage AS (
    SELECT
        e.CLIENT_ID,
        ROUND(
            100.0 * SUM(CASE WHEN e.CONSUMER_CONSENT_PROVIDED = 'Consent provided' THEN 1 ELSE 0 END) /
            NULLIF(COUNT(*), 0),  -- Counts ALL complaints including NULL consent
            2
        ) AS consent_pct
    FROM {{ source('airbyte_schema', 'EVENTS') }} e
    GROUP BY e.CLIENT_ID
)
```

### Correct SQL Logic
```sql
consent_percentage AS (
    SELECT
        e.CLIENT_ID,
        ROUND(
            100.0 * SUM(CASE WHEN e.CONSUMER_CONSENT_PROVIDED = 'Consent provided' THEN 1 ELSE 0 END) /
            NULLIF(SUM(CASE WHEN e.CONSUMER_CONSENT_PROVIDED IS NOT NULL THEN 1 ELSE 0 END), 0),
            6
        ) AS consent_pct
    FROM {{ source('airbyte_schema', 'EVENTS') }} e
    GROUP BY e.CLIENT_ID
)
```

---

## Why the Original Logic Is Wrong

* The description says "percentage of complaint calls that got consent"
* Ground truth interpretation: Only count complaints where consent was asked/recorded (non-NULL CONSUMER_CONSENT_PROVIDED)
* Predicted interpretation: Count all complaints regardless of consent status
* This causes significant differences:
  - If client has 4 complaints but only 2 had consent recorded, GT calculates 2/2 = 100% (if both consented)
  - Predicted calculates 2/4 = 50%
* Ground truth returns NULL when no complaints have consent information recorded
* Predicted returns 0 in those cases

---

## Evidence

**Key comparison demonstrating the error:**

| CLIENT_ID | GT Value | Predicted Value | Issue |
| --------- | -------- | --------------- | ----- |
| C00000001 | NULL | 0.0 | No complaints with consent info, should be NULL |
| C00000003 | 50.0 | 25.0 | 2x difference due to counting all vs only those with consent |
| C00000004 | 100.0 | 25.0 | 4x difference |
| C00000005 | 66.666667 | 28.57 | Different calculation base |
| C00000006 | 33.333333 | 16.67 | Different calculation base |

**Impact:**
* Current implementation: **Incorrect percentages due to wrong denominator calculation**
* Corrected implementation: **Correct percentages matching ground truth**

---

## Result

**Key differences in interpretation:**

| Scenario | Ground Truth | Predicted |
| -------- | ------------ | --------- |
| Client with 4 complaints, 2 have consent info, 1 consented | 1/2 = 50% | 1/4 = 25% |
| Client with no consent info recorded | NULL | 0% |
| Client with 2 complaints, both have consent, both consented | 2/2 = 100% | 2/2 = 100% |

**Fix requirements:**
1. Only count complaints where CONSUMER_CONSENT_PROVIDED IS NOT NULL in denominator
2. Return NULL when no complaints have consent information (not 0)
3. Use higher precision for rounding (6 decimal places to match GT format)
