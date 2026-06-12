# Column Mismatch Summary

## Database: music_platform_2
## Table: music_platform__categories
## Column: LATEST_REVIEW_PODCAST_TITLE

**Description:**
The title of the podcast with the latest review in the category, with ties broken by the ascending order of the podcast title.

---

## Root Cause
**Incorrect exclusion of reviews with Arabic numeral dates**

### Incorrect SQL Logic
```sql
reviews AS (
    SELECT
        PODCAST_ID,
        RATING,
        CREATED_AT
    FROM {{ source('airbyte_schema', 'REVIEWS') }}
    WHERE CREATED_AT NOT LIKE '%٢%' AND CREATED_AT NOT LIKE '%١%'  -- Wrongly excludes Arabic dates
),

latest_review_podcast AS (
    SELECT
        cp.CATEGORY,
        cp.podcast_title AS latest_review_podcast_title
    FROM (
        SELECT
            cp.CATEGORY,
            cp.podcast_title,
            r.CREATED_AT,
            ROW_NUMBER() OVER (PARTITION BY cp.CATEGORY ORDER BY r.CREATED_AT DESC, cp.podcast_title ASC) AS rn
        FROM category_podcasts cp
        INNER JOIN reviews r ON cp.PODCAST_ID = r.PODCAST_ID
    ) cp
    WHERE rn = 1
)
```

### Correct SQL Logic
```sql
reviews AS (
    SELECT
        PODCAST_ID,
        RATING,
        CREATED_AT
    FROM {{ source('airbyte_schema', 'REVIEWS') }}
    -- Remove the WHERE clause that filters out Arabic numerals
),

latest_review_podcast AS (
    SELECT
        cp.CATEGORY,
        cp.podcast_title AS latest_review_podcast_title
    FROM (
        SELECT
            cp.CATEGORY,
            cp.podcast_title,
            r.CREATED_AT,
            ROW_NUMBER() OVER (PARTITION BY cp.CATEGORY ORDER BY r.CREATED_AT DESC, cp.podcast_title ASC) AS rn
        FROM category_podcasts cp
        INNER JOIN reviews r ON cp.PODCAST_ID = r.PODCAST_ID
    ) cp
    WHERE rn = 1
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Find the podcast with the latest (most recent) review in each category
  * Use string sorting on created_at timestamp to determine "latest"
  * Break ties by ascending podcast title

* **What the SQL actually computes:**
  * The SQL filters out reviews that have Arabic numerals in their created_at field
  * This filter: `WHERE CREATED_AT NOT LIKE '%٢%' AND CREATED_AT NOT LIKE '%١%'`
  * This excludes 2 reviews that have dates encoded with Arabic numerals

* **The Unicode sorting behavior:**
  * Arabic numerals have higher Unicode values than ASCII digits
    - ASCII '2' = Unicode 50
    - Arabic '٢' = Unicode 1634
  * When doing string sorting (ORDER BY DESC), Arabic numeral dates sort AFTER regular ASCII dates
  * So '٢٠٢٠-١٢-٢٤' (2020-12-24 in Arabic) is considered "later" than '2022-09-05' in string comparison

* **Impact on comedy category:**
  * "The Joe Rogan Experience" has 2 reviews with Arabic-encoded dates (`٢٠٢٠-١٢-٢٤`)
  * These dates sort as "latest" due to their high Unicode values
  * The SQL excludes these reviews, making "Zane and Heath: Unfiltered" (2022-09-05) appear latest instead

---

## Evidence

**Key comparison demonstrating the error:**

| Category | Wrong Logic (excludes Arabic) | Correct Logic (includes Arabic) | Ground Truth |
| -------- | ----------------------------- | ------------------------------- | ------------ |
| comedy | Zane and Heath: Unfiltered | The Joe Rogan Experience | The Joe Rogan Experience |

**Arabic date review details:**
- The Joe Rogan Experience has 2 reviews with Arabic dates: `٢٠٢٠-١٢-٢٤T١١:٥٥:٠٨-07:00`
- This translates to December 24, 2020 but sorts after 2022 dates due to Unicode ordering
- Zane and Heath's latest review: `2022-09-05T19:54:19-07:00`
- In string sorting: `٢٠٢٠... > 2022...` (Arabic chars have higher Unicode values)

**Reviews with Arabic dates in dataset:**
- Total: 2 reviews (both for "The Joe Rogan Experience")
- Sample date: `٢٠٢٠-١٢-٢٤T١١:٥٥:٠٨-07:00` (Arabic numerals for 2020-12-24T11:55:08)

**Impact:**
* Current implementation: **109/110 matches (99.09%)**
* Corrected implementation: **110/110 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The SQL unnecessarily filters out reviews with Arabic numeral dates. While these dates may represent data quality issues (being encoded incorrectly), the GT includes them and relies on string sorting behavior. Removing the `WHERE CREATED_AT NOT LIKE '%٢%' AND CREATED_AT NOT LIKE '%١%'` filter produces a perfect match with the ground truth.

**Categories affected:**
- comedy: "The Joe Rogan Experience" (GT) vs "Zane and Heath: Unfiltered" (Pred)
