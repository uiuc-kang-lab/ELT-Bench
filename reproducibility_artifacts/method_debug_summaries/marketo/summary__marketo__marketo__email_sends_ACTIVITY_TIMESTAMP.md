# Column Mismatch Summary

## Database: marketo
## Table: marketo__email_sends
## Column: ACTIVITY_TIMESTAMP

**Description:**
The timestamp of the email send activity.

---

## Root Cause
**FALSE POSITIVE - GT truncated timestamps to date-only format while Pred preserved full timestamps from source**

### Source Data Format
```
activity_date: 2020-05-10 19:21:10.000
activity_date: 2020-05-11 13:17:32.000
activity_date: 2020-05-11 18:00:04.000
```

### GT Format (Truncated to Date)
```
ACTIVITY_TIMESTAMP: 2020-05-10
ACTIVITY_TIMESTAMP: 2020-05-11
ACTIVITY_TIMESTAMP: 2020-05-11
```

### Pred Format (Full Timestamp - Matches Source)
```
ACTIVITY_TIMESTAMP: 2020-05-10 19:21:10.000
ACTIVITY_TIMESTAMP: 2020-05-11 13:17:32.000
ACTIVITY_TIMESTAMP: 2020-05-11 18:00:04.000
```

---

## Why This Is a False Positive

* **Source data**: Full timestamps with time component (e.g., `2020-05-10 19:21:10.000`)
* **GT**: Truncated to date-only (e.g., `2020-05-10`)
* **Pred**: Preserved full timestamp from source (e.g., `2020-05-10 19:21:10.000`)

**Applying the rule:**
- GT introduced a format change (truncation to date) that wasn't in the source
- Pred correctly preserved the source format
- Therefore, this is a **FALSE POSITIVE**, not a genuine error

---

## Evidence

**Key comparison by ACTIVITY_ID:**

| ACTIVITY_ID | Source (activity_date) | GT ACTIVITY_TIMESTAMP | Pred ACTIVITY_TIMESTAMP |
| ----------- | ---------------------- | --------------------- | ----------------------- |
| 87850624 | 2020-05-10 19:21:10.000 | 2020-05-10 | 2020-05-10 19:21:10.000 |
| 87967313 | 2020-05-10 22:06:25.000 | 2020-05-10 | 2020-05-10 22:06:25.000 |
| 88376718 | 2020-05-11 13:17:32.000 | 2020-05-11 | 2020-05-11 13:17:32.000 |
| 88383528 | 2020-05-11 14:08:51.000 | 2020-05-11 | 2020-05-11 14:08:51.000 |
| 88461515 | 2020-05-11 18:00:04.000 | 2020-05-11 | 2020-05-11 18:00:04.000 |

**Impact:**
* Position-based comparison: **0/100 matches (0%)** due to date vs timestamp format
* Day-level comparison: **100/100 matches (100%)**

---

## Result

**FALSE POSITIVE**
