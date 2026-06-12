# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
## Column: NETWORK

**Description:**
The network associated with this record.

---

## Root Cause
**Row ordering difference: Values are correct but appear in different row positions due to GROUP BY/ORDER BY differences**

### Current SQL Logic
```sql
SELECT
    ...
    ap.network,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100% when compared row-by-row in the original order.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Ad network where the ad was displayed
  * Values include: 'Bing and Yahoo! search', 'Audience', 'Syndicated search partners', 'AOL search'

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
| Bing and Yahoo! search | 279 | 279 |
| Audience | 22 | 22 |
| Syndicated search partners | 10 | 10 |
| AOL search | 1 | 1 |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The NETWORK column is correctly implemented. Both GT and predicted have identical value distributions.
