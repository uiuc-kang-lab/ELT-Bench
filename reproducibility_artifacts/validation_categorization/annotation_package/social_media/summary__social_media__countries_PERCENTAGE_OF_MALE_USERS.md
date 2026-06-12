# Column Mismatch Summary

## Database: social_media
## Table: countries
## Column: PERCENTAGE_OF_MALE_USERS

**Description:**
The percentage of male Twitter users from the country.

---

## Root Cause
**Wrong calculation: Using distinct user percentage instead of tweet percentage**

### Incorrect SQL Logic
```sql
country_aggregates AS (
    SELECT
        COUNTRY,
        ROUND(
            100.0 * COUNT(DISTINCT CASE WHEN GENDER = 'Male' THEN USERID END) /
            NULLIF(COUNT(DISTINCT USERID), 0),
            2
        ) AS percentage_of_male_users
    FROM joined_data
    GROUP BY COUNTRY
)
```

### Correct SQL Logic
```sql
country_aggregates AS (
    SELECT
        COUNTRY,
        ROUND(
            100.0 * COUNT(CASE WHEN GENDER = 'Male' THEN 1 END) /
            NULLIF(COUNT(*), 0),
            6
        ) AS percentage_of_male_users
    FROM joined_data
    GROUP BY COUNTRY
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Percentage of male Twitter users from the country"
  * This is ambiguous, but GT shows it means: percentage of tweets from male users

* **What the SQL actually computes:**
  * Percentage of distinct male users among all distinct users who tweeted from that country
  * This counts each user once regardless of how many tweets they made

* **The difference:**
  * GT formula: (count of tweets by males) / (total tweets) * 100
  * Current formula: (count of distinct male users) / (count of distinct users) * 100

---

## Evidence

**Key comparison demonstrating the error:**

| Country | GT (tweet %) | Pred (user %) | Tweets | Distinct Users | Male Tweets | Male Users |
| ------- | ------------ | ------------- | ------ | -------------- | ----------- | ---------- |
| Albania | 85.71% | 50.0% | 7 | 2 | 6 | 1 |
| Bangladesh | 27.37% | 53.45% | 190 | 58 | 52 | 31 |
| Brazil | 35.52% | 64.63% | 1402 | 441 | 498 | 285 |
| China | 89.15% | 37.37% | 866 | 99 | 772 | 37 |
| India | 59.81% | 58.94% | 6822 | 2231 | 4079 | 1315 |

**Formula verification:**
- Albania: GT = 6/7 * 100 = 85.71%, Pred = 1/2 * 100 = 50.0%
- Bangladesh: GT = 52/190 * 100 = 27.37%, Pred = 31/58 * 100 = 53.45%
- Brazil: GT = 498/1402 * 100 = 35.52%, Pred = 285/441 * 100 = 64.63%

**Testing both formulas against GT:**
- Matches with distinct users formula: 56/151 (37.1%)
- Matches with tweet percentage formula: **151/151 (100%)**

**Impact:**
* Current implementation: **79/175 matches (45.1%)**
* Corrected implementation: **175/175 matches (100%)**

---

## Result

**Wrong aggregation level: counting distinct users instead of tweets**

The column description "percentage of male Twitter users" is ambiguous. The ground truth shows it means the percentage of tweets that came from male users, not the percentage of distinct users who are male. The fix requires changing `COUNT(DISTINCT CASE WHEN...)` to `COUNT(CASE WHEN...)`.
