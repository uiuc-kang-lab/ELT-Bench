# Column Mismatch Summary

## Database: coinmarketcap
## Table: coinmarket__coins
## Column: HIGHEST_PRICE

**Description:**
Highest price of the coin.

---

## Root Cause
**Wrong column used: SQL uses MAX(HIGH) instead of MAX(PRICE)**

### Incorrect SQL Logic
```sql
highest_price_per_coin AS (
    SELECT
        COIN_ID,
        MAX(HIGH) AS highest_price
    FROM historical_data
    GROUP BY COIN_ID
)
```

### Correct SQL Logic
```sql
highest_price_per_coin AS (
    SELECT
        COIN_ID,
        MAX(PRICE) AS highest_price
    FROM historical_data
    GROUP BY COIN_ID
)
```

---

## Why the Original Logic Is Wrong

* The SQL uses `MAX(HIGH)` from the historical data
* The `HIGH` column represents the highest price **within a single day/period** (intraday high)
* The `PRICE` column represents the actual trading price at a point in time
* The column description says "Highest price of the coin" which refers to the maximum `PRICE` value, not the maximum `HIGH` value

**Schema context from `Historical.csv`:**
- `high`: "highest price" - this is the intraday high for that record's time period
- `price`: "how much is a coin" - this is the actual price at that time

The difference:
- `HIGH` captures momentary intraday peaks that may not reflect actual traded prices
- `PRICE` captures the actual price used in transactions

---

## Evidence

**Key comparison demonstrating the error:**

| Coin ID | Coin Name | Wrong Logic (MAX HIGH) | Correct Logic (MAX PRICE) | Ground Truth |
| ------- | --------- | ---------------------- | ------------------------- | ------------ |
| 1       | Bitcoin   | 64,863.10              | 63,503.46                 | 63,503.46    |
| 2       | Litecoin  | 412.96                 | 386.45                    | 386.45       |
| 3       | Namecoin  | 16.30                  | 11.60                     | 11.60        |
| 4       | Terracoin | 1.89                   | 1.71                      | 1.71         |
| 5       | Peercoin  | 9.92                   | 9.05                      | 9.05         |

**Impact:**
* Current implementation: **650/8,927 matches (7.3%)**
* Corrected implementation: **8,927/8,927 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The `HIGH` column in historical data represents intraday highs (peak prices during a trading period), while `PRICE` represents the actual recorded price. When asking for "highest price," the ground truth uses the maximum of the `PRICE` column, not the intraday `HIGH` values which can be anomalous spikes.
