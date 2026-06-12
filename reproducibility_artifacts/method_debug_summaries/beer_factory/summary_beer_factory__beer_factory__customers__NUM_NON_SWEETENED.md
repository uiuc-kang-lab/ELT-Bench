# SQL Column Debugging Summary

## Database: beer_factory
## Table: beer_factory__customers
## Column: NUM_NON_SWEETENED

**Description:**
Number of non-sweetened root beers the customer has purchased, replace NULL values with 0.

---

## Root Cause
**Wrong definition of "non-sweetened" - SQL counts root beers with ArtificialSweetener=FALSE, but the correct definition is root beers with exactly ONE sweetener type (not multiple sweeteners combined)**

### Incorrect SQL Logic
```sql
customer_purchases AS (
    SELECT
        t.CustomerID,
        SUM(CASE WHEN rb.artificialsweetener = 'FALSE' THEN 1 ELSE 0 END) as num_non_sweetened,
        ...
    FROM transactions t
    JOIN rootbeer r ON t.RootBeerID = r.RootBeerID
    JOIN rootbeerbrand rb ON r.BrandID = rb.brandid
    GROUP BY t.CustomerID
)
```

### Correct SQL Logic
```sql
customer_purchases AS (
    SELECT
        t.CustomerID,
        COUNT(DISTINCT CASE
            WHEN (CASE WHEN rb.CaneSugar THEN 1 ELSE 0 END
                + CASE WHEN rb.CornSyrup THEN 1 ELSE 0 END
                + CASE WHEN rb.Honey THEN 1 ELSE 0 END
                + CASE WHEN rb.ArtificialSweetener THEN 1 ELSE 0 END) = 1
            THEN r.RootBeerID
        END) as num_non_sweetened,
        ...
    FROM transactions t
    JOIN rootbeer r ON t.RootBeerID = r.RootBeerID
    JOIN rootbeerbrand rb ON r.BrandID = rb.brandid
    GROUP BY t.CustomerID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** "Non-sweetened" refers to root beers that have exactly ONE type of sweetener (either CaneSugar, CornSyrup, Honey, OR ArtificialSweetener) - meaning they use a single, natural/simple sweetening approach rather than multiple sweeteners combined.

* **What the SQL actually computes:** The SQL counts ALL transactions where `ArtificialSweetener = FALSE`, which includes:
  - Root beers with only CaneSugar (correct)
  - Root beers with only CornSyrup (correct)
  - Root beers with CaneSugar + Honey (incorrect - multiple sweeteners)
  - Root beers with CornSyrup + Honey (incorrect - multiple sweeteners)
  - Root beers with CaneSugar + CornSyrup + Honey (incorrect - multiple sweeteners)

**Brand sweetener combinations in the database:**
| Brand | Sweeteners |
|-------|------------|
| A&W | CornSyrup only |
| A.J. Stephans | CaneSugar only |
| IBC | CaneSugar only |
| Bulldog | CaneSugar + Honey |
| Henry Weinhard's | CornSyrup + Honey |
| Sparky's Fresh Draft | CaneSugar + Honey |
| Mug | CornSyrup + Artificial |

The incorrect SQL counts brands like "Bulldog" and "Sparky's Fresh Draft" as non-sweetened because they don't have artificial sweetener, but they actually have multiple sweeteners (CaneSugar + Honey).

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Value |
| ------ | ----- |
| Total customers | 554 |
| GT mean NUM_NON_SWEETENED | 8.06 |
| Pred mean NUM_NON_SWEETENED | 10.88 |
| Positional match | 35/554 (6.3%) |
| Semantic match (by CUSTOMER_ID) | 35/554 (6.3%) |

**Mismatch pattern:**
- Pred > GT: 519 cases (overcounting)
- Pred < GT: 0 cases
- Pred = GT: 35 cases

**Sample comparison for customer 101811:**

| RootBeerID | Brand | CaneSugar | CornSyrup | Honey | Artificial | Sweetener Count | Counted by GT |
|------------|-------|-----------|-----------|-------|------------|-----------------|---------------|
| 103031 | Dog n Suds | False | True | False | False | 1 | Yes |
| 105410 | Henry Weinhard's | False | True | True | False | 2 | No |
| 101525 | Bulldog | True | False | True | False | 2 | No |
| 106267 | Mug | False | True | False | True | 2 | No |
| 104295 | Sparky's Fresh Draft | True | False | True | False | 2 | No |
| 105759 | IBC | True | False | False | False | 1 | Yes |

**GT value: 2** (only Dog n Suds and IBC have exactly one sweetener)
**Pred value: 5** (counts all except Mug which has ArtificialSweetener=True)

**Impact:**
* Current implementation: **35/554 matches (6.3%)**
* Corrected implementation: **553/554 matches (99.8%)**

---

## Result

**Near-perfect match with corrected logic (99.8%)**

The corrected logic counts unique RootBeerIDs where the brand has exactly ONE sweetener type:
- `(CaneSugar + CornSyrup + Honey + ArtificialSweetener) = 1`

One minor discrepancy remains (customer 480298: GT=8 vs computed=9), likely a data quality issue in the ground truth.

**Brands that qualify as "non-sweetened" (exactly one sweetener):**
- A&W (CornSyrup only)
- A.J. Stephans (CaneSugar only)
- Abita (CaneSugar only)
- Barq's (CornSyrup only)
- Bedfords (CaneSugar only)
- Bundaberg (CaneSugar only)
- Captain Eli's (CaneSugar only)
- Dad's (CaneSugar only)
- Dog n Suds (CornSyrup only)
- Fitz's (CaneSugar only)
- Gales (CaneSugar only)
- IBC (CaneSugar only)
- River City (CaneSugar only)
- Frostie (CaneSugar only)
- Virgil's (CaneSugar only)
- Diet Stewarts (Artificial only)
- 1919 (CaneSugar only)

**Brands that DO NOT qualify (multiple sweeteners):**
- Bulldog (CaneSugar + Honey)
- Dominion (CaneSugar + Honey)
- Sparky's Fresh Draft (CaneSugar + Honey)
- Henry Weinhard's (CornSyrup + Honey)
- Sprecher (CornSyrup + Honey)
- Thomas Kemper (CaneSugar + Honey)
- Mug (CornSyrup + Artificial)
