# Column Mismatch Summary

## Database: citeseer
## Table: citeseer_paper
## Column: ML_AND_CITED_BUTZ01ALGORITHMIC

**Description:**
Set to 1 if the paper is classified as ML and cited butz01algorithmic; otherwise, set to 0.

---

## Root Cause
**Table misinterpretation: "cited butz01algorithmic" means the paper CITES another paper named butz01algorithmic (via cites table), not that the paper has a word_cited_id='butz01algorithmic' in the content table**

### Incorrect SQL Logic
```sql
content_agg AS (
    SELECT
        paper_id,
        COUNT(word_cited_id) AS num_cited_word,
        MAX(CASE WHEN word_cited_id = 'word1002' THEN 1 ELSE 0 END) AS cited_word1002,
        MAX(CASE WHEN word_cited_id = 'butz01algorithmic' THEN 1 ELSE 0 END) AS cited_butz01algorithmic
    FROM {{ source('airbyte_schema', 'content') }}
    GROUP BY paper_id
)
...
CASE
    WHEN p.class_label = 'ML' AND COALESCE(c.cited_butz01algorithmic, 0) = 1 THEN 1
    ELSE 0
END AS ML_and_cited_butz01algorithmic
```

### Correct SQL Logic
```sql
paper_citations AS (
    SELECT
        citing_paper_id,
        MAX(CASE WHEN cited_paper_id = 'butz01algorithmic' THEN 1 ELSE 0 END) AS cites_butz01algorithmic
    FROM {{ source('airbyte_schema', 'cites') }}
    GROUP BY citing_paper_id
)
...
CASE
    WHEN p.class_label = 'ML' AND COALESCE(pc.cites_butz01algorithmic, 0) = 1 THEN 1
    ELSE 0
END AS ML_and_cited_butz01algorithmic
FROM paper_base p
LEFT JOIN paper_citations pc ON p.paper_id = pc.citing_paper_id
```

---

## Why the Original Logic Is Wrong

* The SQL looks for 'butz01algorithmic' as a `word_cited_id` in the `content` table
* The `content` table contains word tokens associated with papers (word_cited_id values are like 'word1002', 'word1163', etc.)
* There is **no** 'butz01algorithmic' entry in the content table as a word_cited_id
* The correct interpretation: "cited butz01algorithmic" means the paper **cites** another paper named 'butz01algorithmic'
* The `cites` table tracks paper-to-paper citations where `citing_paper_id` cites `cited_paper_id`

**Schema context:**
- `content` table: Maps papers to word tokens (paper_id, word_cited_id) - words like 'word1002', 'word1163'
- `cites` table: Maps paper citations (cited_paper_id, citing_paper_id) - where citing_paper_id cites cited_paper_id

---

## Evidence

**Key comparison demonstrating the error:**

| Paper ID | Class Label | butz01algorithmic in content | CITES butz01algorithmic | Wrong Logic | Correct Logic | Ground Truth |
| -------- | ----------- | ---------------------------- | ----------------------- | ----------- | ------------- | ------------ |
| 538003   | ML          | False                        | True                    | 0           | 1             | 1            |

**Source data verification:**
- Content table: 0 papers have word_cited_id='butz01algorithmic'
- Cites table: 1 paper cites butz01algorithmic (paper 538003 citing butz01algorithmic)

**Impact:**
* Current implementation: **3311/3312 matches (99.97%)**
* Corrected implementation: **3312/3312 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Paper where `ML_AND_CITED_BUTZ01ALGORITHMIC = 1`:**
* **538003** - ML paper that cites butz01algorithmic

**Key insight:**
The phrase "cited butz01algorithmic" in the column description means the paper contains a citation TO the paper named 'butz01algorithmic', found in the `cites` table where `cited_paper_id = 'butz01algorithmic'`. The SQL incorrectly searched for it as a word token in the `content` table, but 'butz01algorithmic' is a paper identifier (appearing in the cites table), not a word token (which have format like 'word1002').
