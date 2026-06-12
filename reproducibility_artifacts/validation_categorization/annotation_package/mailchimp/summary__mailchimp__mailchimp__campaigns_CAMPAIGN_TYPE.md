# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaigns
## Column: CAMPAIGN_TYPE

**Description:**
The type of campaign sent. Possible values:regular, plaintext, absplit, variate, rss.

---

## Root Cause
**Data format mismatch: GT value has extra quotes around it ('"regular"' vs 'regular')**

### Incorrect SQL Logic
```sql
SELECT
    type AS campaign_type,
    ...
FROM campaign
```

### Correct SQL Logic
```sql
SELECT
    '"' || type || '"' AS campaign_type,  -- Add surrounding quotes to match GT format
    ...
FROM campaign
-- OR the GT data format may be incorrect and needs to be fixed upstream
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The type of campaign: regular, plaintext, absplit, variate, or rss

* **What the SQL actually computes:**
  * Correctly reads the `type` column value: `regular`
  * GT has the value wrapped in quotes: `"regular"`

**This appears to be a data quality issue in the GT file rather than a SQL logic error.** The GT value includes the surrounding double quotes as part of the string.

---

## Evidence

**Key comparison demonstrating the difference:**

| Campaign ID | GT campaign_type | Predicted campaign_type |
| ----------- | ---------------- | ----------------------- |
| c2b4c1c0d9 | "regular" | regular |

**Analysis:**
- GT value: `'"regular"'` (string includes quotes)
- Pred value: `'regular'` (string without quotes)
- The quotes are part of the GT data string, not CSV field delimiters

**Impact:**
* Current implementation: **0/1 matches (0%)**
* If GT format is intentional (add quotes): **1/1 matches (100%)**
* If GT format is error (should be fixed upstream): No SQL change needed

---

## Result

**Possible data quality issue in ground truth**

This mismatch may indicate the GT file has incorrect formatting (embedded quotes). If the quotes are intentional, the SQL should add them; otherwise, the GT data should be corrected.
