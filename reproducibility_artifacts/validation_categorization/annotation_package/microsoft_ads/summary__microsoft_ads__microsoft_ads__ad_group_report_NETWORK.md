# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_group_report
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
    agp.network,
    ...
FROM ad_group_performance agp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100% when compared row-by-row.

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
| Bing and Yahoo! search | 109 |
| Syndicated search partners | 73 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 182 | 182 |
| Bing and Yahoo! search | 109 | 109 |
| Syndicated search partners | 73 | 73 |

**Impact:**
* Current implementation: **182/182 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The NETWORK column is correctly implemented.
