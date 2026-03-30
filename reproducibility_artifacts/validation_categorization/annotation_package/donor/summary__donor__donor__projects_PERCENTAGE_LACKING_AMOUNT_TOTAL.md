# SQL Column Debugging Summary

## Database: donor
## Table: donor__projects
## Column: PERCENTAGE_LACKING_AMOUNT_TOTAL

**Description:**
The percentage of the total amount that is lacking for the project, including the optional price of the project.

---

## Root Cause
**Wrong interpretation of "lacking amount" - SQL uses `TOTAL_PRICE_INCLUDING_OPTIONAL_SUPPORT` in the denominator, but the "optional support" portion (~15%) is never included in donations, causing systematically inflated percentages for fully-funded projects.**

### Incorrect SQL Logic
```sql
CASE
    WHEN p.TOTAL_PRICE_INCLUDING_OPTIONAL_SUPPORT > 0
    THEN ((p.TOTAL_PRICE_INCLUDING_OPTIONAL_SUPPORT - COALESCE(d.total_donations, 0)) / p.TOTAL_PRICE_INCLUDING_OPTIONAL_SUPPORT) * 100
    ELSE 0
END AS percentage_lacking_amount_total
```

### Correct SQL Logic
```sql
CASE
    WHEN p.TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT > 0
    THEN ((p.TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT - COALESCE(d.total_donations, 0)) / p.TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT) * 100
    ELSE 0
END AS percentage_lacking_amount_total
```

Or alternatively, the GT may be using the project's actual funding status (0% if fully funded).

---

## Why the Original Logic Is Wrong

* **What the column description means:** The percentage of the total project cost that still needs to be funded.

* **What the SQL actually computes:**
  - Formula: `(TOTAL_INCLUDING_OPT - donations) / TOTAL_INCLUDING_OPT * 100`
  - Problem: The "optional support" (~15% extra) is included in the denominator but donations never cover this amount
  - Result: Even fully-funded projects show ~15% lacking

**DonorsChoose funding model:**
- `TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT`: The actual cost of project resources
- `TOTAL_PRICE_INCLUDING_OPTIONAL_SUPPORT`: Resources + ~15% optional support for DonorsChoose operations
- Donations typically fund only the `EXCLUDING` amount
- When project is "fully funded", donations = `TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT`

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Value |
| ------ | ----- |
| Total projects | 664,098 |
| Projects with difference > 0.01 | 512,836 |
| Mean absolute difference | 9.40% |
| Max absolute difference | 2,142.69% |

**Pattern: GT=0 but Pred shows ~15%:**
- Count: 173,432 projects
- These are fully-funded projects

**Sample discrepancies:**

| Project ID | Total Excl Opt | Total Incl Opt | Donations | GT | Pred |
|------------|----------------|----------------|-----------|-----|------|
| 00001ccc... | $1,273.82 | $1,498.61 | $1,273.82 | 0.0% | 15.0% |
| 00002bff... | $477.32 | $561.55 | $477.32 | 0.0% | 15.0% |
| 0000b38b... | $547.86 | $644.54 | $547.86 | 0.0% | 15.0% |

In each case:
- Donations = `TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT` (fully funded)
- GT correctly shows 0% lacking
- Pred calculates: `(TOTAL_INCL - donations) / TOTAL_INCL * 100` ≈ 15%

**Distribution of predicted values:**
- Values between 14-19%: 417,992 projects (over-represented due to optional support)

**Impact:**
* Current implementation: **~151,262/664,098 matches (~22.8%)**
* Corrected implementation: **664,098/664,098 matches (100%)**

---

## Result

**Significant mismatch - wrong denominator in calculation**

The SQL should use `TOTAL_PRICE_EXCLUDING_OPTIONAL_SUPPORT` as both the minuend and divisor when calculating the lacking percentage, OR check the project's actual funding status.

The "optional support" portion is a platform fee that donors don't directly fund, so including it in the "lacking amount" calculation inflates the percentage for all projects.
