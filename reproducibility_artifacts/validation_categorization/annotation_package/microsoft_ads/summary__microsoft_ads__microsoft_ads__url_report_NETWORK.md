# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
## Column: NETWORK

**Description:**
The network associated with this record.

---

## Root Cause
**No semantic error: Values match 100%**

### Current SQL Logic
```sql
SELECT
    ...
    ap.network,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100%.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Ad network where the ad was displayed

* **What the SQL actually computes:**
  * Correctly passes through the network from source
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| NETWORK | Count |
| ------- | ----- |
| Bing and Yahoo! search | 279 |
| Audience | 22 |
| Syndicated search partners | 10 |
| AOL search | 1 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Distribution identical | Yes | Yes |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The NETWORK column is correctly implemented.
