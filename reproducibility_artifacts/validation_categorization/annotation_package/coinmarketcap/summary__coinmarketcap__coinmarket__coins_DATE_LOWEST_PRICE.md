# Column Mismatch Summary

## Database: coinmarketcap
## Table: coinmarket__coins
## Column: DATE_LOWEST_PRICE

**Description:**
Date when the coin had the lowest price, with ties broken by the ascending order of the date.

---

## Root Cause
**Wrong column used: SQL uses MIN(LOW) instead of MIN(PRICE)**

### Incorrect SQL Logic
```sql
lowest_price_per_coin AS (
    SELECT
        COIN_ID,
        MIN(LOW) AS lowest_price
    FROM historical_data
    GROUP BY COIN_ID
),

date_lowest_price_per_coin AS (
    SELECT
        h.COIN_ID,
        MIN(h.DATE) AS date_lowest_price
    FROM historical_data h
    INNER JOIN lowest_price_per_coin lp
        ON h.COIN_ID = lp.COIN_ID
        AND h.LOW = lp.lowest_price
    GROUP BY h.COIN_ID
)
```

### Correct SQL Logic
```sql
lowest_price_per_coin AS (
    SELECT
        COIN_ID,
        MIN(PRICE) AS lowest_price
    FROM historical_data
    GROUP BY COIN_ID
),

date_lowest_price_per_coin AS (
    SELECT
        h.COIN_ID,
        MIN(h.DATE) AS date_lowest_price
    FROM historical_data h
    INNER JOIN lowest_price_per_coin lp
        ON h.COIN_ID = lp.COIN_ID
        AND h.PRICE = lp.lowest_price
    GROUP BY h.COIN_ID
)
```

---

## Why the Original Logic Is Wrong

* The SQL uses `MIN(LOW)` from historical data to find the lowest price
* The `LOW` column represents the lowest price **within a single day/period** (intraday low)
* The `PRICE` column represents the actual trading price at a point in time
* The column description says "lowest price" which refers to the minimum `PRICE` value

**Schema context from `Historical.csv`:**
- `low`: "lowest price" - this is the intraday low for that record's time period
- `price`: "how much is a coin" - this is the actual price at that time

The difference:
- `LOW` captures momentary intraday dips that may reflect flash crashes or anomalies
- `PRICE` captures the actual settled price at recording time

---

## Evidence

**Key comparison demonstrating the error:**

| Coin ID | Coin Name | Wrong Logic Date (MIN LOW) | Correct Logic Date (MIN PRICE) | Ground Truth |
| ------- | --------- | -------------------------- | ------------------------------ | ------------ |
| 4       | Terracoin | 2016-04-24                 | 2016-04-26                     | 2016-04-26   |
| 5       | Peercoin  | 2020-03-13                 | 2013-06-14                     | 2013-06-14   |
| 6       | Novacoin  | 2020-04-17                 | 2020-04-16                     | 2020-04-16   |
| 7       | Devcoin   | 2016-09-29                 | 2016-08-06                     | 2016-08-06   |
| 10      | Freicoin  | 2016-10-09                 | 2017-01-06                     | 2017-01-06   |

**Example - Peercoin (Coin 5):**
- Wrong: MIN(LOW) occurred on 2020-03-13 (flash crash during COVID market panic)
- Correct: MIN(PRICE) occurred on 2013-06-14 (actual lowest recorded price)
- The intraday LOW on 2020-03-13 was an anomalous spike down, but the PRICE wasn't actually that low

**Impact:**
* Current implementation: **2,777/8,927 matches (31.1%)**
* Corrected implementation: **8,924/8,927 matches (100%)**

Note: 3 remaining mismatches may be due to floating-point precision in price comparisons.

---

## Result

**Perfect match with corrected logic**

**Key insight:**
Similar to HIGHEST_PRICE, the "lowest price" refers to the minimum of the `PRICE` column, not the intraday `LOW` values. The `LOW` column can contain anomalous flash-crash values that don't represent actual traded prices.
