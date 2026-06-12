## Database: chicago_crime
## Table: districts
## Column: NUM_CRIMES_JAN_2018

**Description:**
Number of crimes reported in January 2018 in the district, replace NULL values with 0.

---

## Root Cause
**Date format mismatch: SQL expects two-digit month/day but data uses single-digit format**

### Incorrect SQL Logic
```sql
WHERE TO_DATE(date, 'MM/DD/YYYY HH24:MI') >= '2018-01-01'
  AND TO_DATE(date, 'MM/DD/YYYY HH24:MI') < '2018-02-01'
```

### Correct SQL Logic
```sql
-- Option 1: Use flexible parsing
WHERE TRY_TO_TIMESTAMP(date) >= '2018-01-01'
  AND TRY_TO_TIMESTAMP(date) < '2018-02-01'

-- Option 2: Use correct format for single-digit month/day
WHERE TO_DATE(date, 'M/D/YYYY H:MI') >= '2018-01-01'
  AND TO_DATE(date, 'M/D/YYYY H:MI') < '2018-02-01'
```

---

## Why the Original Logic Is Wrong

* The crime data contains dates in the format `1/1/2018 2:46` (single-digit month, day, and hour)
* The SQL format string `MM/DD/YYYY HH24:MI` expects two-digit values with leading zeros (e.g., `01/01/2018 02:46`)
* This mismatch causes some date strings to fail parsing or parse incorrectly
* As a result, many valid January 2018 crimes are not counted
* Ground truth values are consistently higher than predicted values across all districts

---

## Evidence

**Key comparison demonstrating the error:**

| District | Wrong Logic | Correct Logic | Ground Truth |
| -------- | ----------- | ------------- | ------------ |
| Central (1) | 1246 | 1798 | 1798 |
| Ogden (10) | 930 | 1538 | 1538 |
| Harrison (11) | 1447 | 2321 | 2321 |
| Near West (12) | 916 | 1582 | 1582 |
| Austin (15) | 747 | 1247 | 1247 |

**Impact:**
* Current implementation: **0/22 matches (0%)**
* Corrected implementation: **22/22 matches (100%)**

---

## Result

:warning: **High Severity - Date Parsing Error**

**Key insight:**
Always verify the actual date format in source data before specifying a date format string. Use flexible date parsing functions like `TRY_TO_TIMESTAMP()` or ensure the format pattern matches exactly (e.g., `M/D/YYYY` for single-digit dates vs `MM/DD/YYYY` for zero-padded dates).
