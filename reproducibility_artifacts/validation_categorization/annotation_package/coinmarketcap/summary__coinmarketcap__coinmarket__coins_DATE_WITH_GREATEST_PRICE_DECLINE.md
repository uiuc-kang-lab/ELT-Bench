# Column Mismatch Summary

## Database: coinmarketcap
## Table: coinmarket__coins
## Column: DATE_WITH_GREATEST_PRICE_DECLINE

**Description:**
The date of transactions with the greatest decline in percent change in 1 hour, with ties broken by the descending order of the date.

---

## Root Cause
**Unable to determine correct logic - GT values do not match any tested interpretation of the column description**

### Current SQL Logic
```sql
greatest_decline_per_coin AS (
    SELECT
        COIN_ID,
        MIN(PERCENT_CHANGE_1H) AS greatest_decline
    FROM historical_data
    GROUP BY COIN_ID
),

date_greatest_decline_per_coin AS (
    SELECT
        h.COIN_ID,
        MAX(h.DATE) AS date_with_greatest_price_decline
    FROM historical_data h
    INNER JOIN greatest_decline_per_coin gd
        ON h.COIN_ID = gd.COIN_ID
        AND h.PERCENT_CHANGE_1H = gd.greatest_decline
    GROUP BY h.COIN_ID
)
```

### Tested Alternative Logic (None Match)
Multiple interpretations were tested:
1. MIN(PERCENT_CHANGE_1H) with MAX(DATE) tie-break: **0.3% match**
2. MIN(PERCENT_CHANGE_24H) with MAX(DATE) tie-break: **2.3% match**
3. Day-over-day price change: **2.0% match**
4. Daily (close-open)/open: **1.9% match**
5. Change of PERCENT_CHANGE_1H (derivative): **0.1% match**

---

## Why the Original Logic May Be Wrong

The description "greatest decline in percent change in 1 hour" is ambiguous:
- **Current interpretation**: Most negative `PERCENT_CHANGE_1H` value
- **Alternative**: Change OF `PERCENT_CHANGE_1H` from one period to next (derivative)
- **Alternative**: `PERCENT_CHANGE_24H` (24-hour change instead of 1-hour)

However, **none of these interpretations achieve more than 2.3% match rate**.

**Analysis of GT dates reveals:**
- Many GT dates have NULL values for `PERCENT_CHANGE_1H`
- GT dates often do NOT correspond to the minimum percent change value
- Some GT dates have POSITIVE percent changes, not declines

**Example - Bitcoin (Coin 1):**
- GT date: 2013-07-03
- `PERCENT_CHANGE_1H` on GT date: NULL
- `PERCENT_CHANGE_24H` on GT date: -14.44%
- Actual MIN `PERCENT_CHANGE_1H`: -15.89% on 2015-08-18
- Actual MIN `PERCENT_CHANGE_24H`: -37.14% on 2020-03-12

---

## Evidence

**Tested interpretations vs Ground Truth:**

| Interpretation | Match Rate |
| -------------- | ---------- |
| MIN PERCENT_CHANGE_1H, MAX date | 27/8,927 (0.3%) |
| MIN PERCENT_CHANGE_1H, MIN date | 38/8,927 (0.4%) |
| MIN PERCENT_CHANGE_24H, MAX date | 201/8,927 (2.3%) |
| MIN PERCENT_CHANGE_24H, MIN date | 207/8,927 (2.3%) |
| MIN day-over-day price change | 176/8,927 (2.0%) |
| MIN daily (close-open)/open | 170/8,927 (1.9%) |
| First date per coin | 723/8,927 (8.1%) |
| First date with NULL PERCENT_CHANGE_1H | 1,649/8,927 (18.5%) |

**Sample GT dates that don't match any pattern:**

| Coin ID | GT Date | PERCENT_CHANGE_1H | MIN PERCENT_CHANGE_1H Date |
| ------- | ------- | ----------------- | -------------------------- |
| 1       | 2013-07-03 | NULL | 2015-08-18 |
| 133     | 2014-03-03 | +87.69 (positive!) | Different date |
| 140     | 2014-03-11 | +18.11 (positive!) | Different date |

**Impact:**
* Current implementation: **27/8,927 matches (0.3%)**
* Best tested interpretation: **207/8,927 matches (2.3%)**

---

## Result

**Unable to find correct logic**

The ground truth values for this column do not follow any discernible pattern based on the column description. Possible explanations:
1. The GT was computed using a different data source
2. The column description doesn't accurately describe the GT calculation
3. There may be additional business logic not captured in the description

**Recommendation:**
- Review the original GT generation code/methodology
- Verify the column description matches the intended calculation
- Check if there's a different interpretation of "decline in percent change"
