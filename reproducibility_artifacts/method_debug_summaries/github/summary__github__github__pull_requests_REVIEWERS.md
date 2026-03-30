# Column Mismatch Summary

## Database: github
## Table: github__pull_requests
## Column: REVIEWERS

### Description
List of Users who reviewed the pull request

---

## Root Cause
**Ordering mismatch: Alphabetical ordering vs chronological (first review timestamp) ordering**

### Incorrect SQL Logic
```sql
pr_reviews AS (
    SELECT
        pr.issue_id,
        LISTAGG(DISTINCT u.login, ', ') WITHIN GROUP (ORDER BY u.login) AS reviewers,
        COUNT(DISTINCT prr.id) AS number_of_reviews
    FROM {{ source('airbyte_schema', 'pull_request') }} pr
    LEFT JOIN {{ source('airbyte_schema', 'pull_request_review') }} prr ON pr.id = prr.pull_request_id
    LEFT JOIN {{ source('airbyte_schema', 'users') }} u ON prr.user_id = u.id
    GROUP BY pr.issue_id
)
```

### Correct SQL Logic
```sql
pr_reviews AS (
    WITH first_reviews AS (
        SELECT
            pr.issue_id,
            u.login,
            MIN(prr.submitted_at) AS first_review_at
        FROM {{ source('airbyte_schema', 'pull_request') }} pr
        LEFT JOIN {{ source('airbyte_schema', 'pull_request_review') }} prr ON pr.id = prr.pull_request_id
        LEFT JOIN {{ source('airbyte_schema', 'users') }} u ON prr.user_id = u.id
        WHERE u.login IS NOT NULL
        GROUP BY pr.issue_id, u.login
    )
    SELECT
        issue_id,
        LISTAGG(login, ', ') WITHIN GROUP (ORDER BY first_review_at) AS reviewers,
        COUNT(login) AS number_of_reviews
    FROM first_reviews
    GROUP BY issue_id
)
```

---

## Why the Original Logic Is Wrong

The current implementation orders reviewers **alphabetically** by their login name using `ORDER BY u.login`. However, the ground truth expects reviewers to be ordered **chronologically** by the timestamp of their first review (`submitted_at`).

**What the column description means:**
- "List of Users who reviewed the pull request" - the list should represent reviewers in the order they participated

**What the SQL actually computes:**
- Lists reviewers in alphabetical order by login name, ignoring the temporal sequence of reviews

**Schema semantics from `source_schemas`:**
- `pull_request_review.submitted_at`: "Timestamp of when the request for review was submitted"
- This timestamp indicates when each reviewer first participated, which should determine ordering

---

## Evidence

**Key comparison demonstrating the error:**

| Issue ID | Wrong Logic (alphabetical) | Correct Logic (chronological) | Ground Truth |
| -------- | -------------------------- | ----------------------------- | ------------ |
| 600302582 | 4bc4fc..., fb122a... | fb122a..., 4bc4fc... | fb122a..., 4bc4fc... |
| 677204748 | 9a977c..., df3d04... | df3d04..., 9a977c... | df3d04..., 9a977c... |
| 733448638 | df3d04..., fb122a... | df3d04..., fb122a... | fb122a..., df3d04... |

**Detailed example - Issue 600302582:**
- User `fb122a...` first reviewed on: **2019-02-05 04:59:39**
- User `4bc4fc...` first reviewed on: **2019-02-25 08:44:48**
- Alphabetically: `4bc4fc...` < `fb122a...` (wrong order)
- Chronologically: `fb122a...` < `4bc4fc...` (correct order matching GT)

**Impact:**
* Current implementation: **164/167 matches (98.2%)**
* Corrected implementation (chronological order): **~166/167 matches (99.4%)**
* Set comparison (ignoring order): **167/167 matches (100%)**

**Note:** Issue 733448638 shows GT order `fb122a..., df3d04...` which doesn't match chronological order (`df3d04...` reviewed first). This suggests there may be an additional ordering factor (possibly requested reviewers having priority), but the primary issue is the alphabetical vs chronological difference.

---

## Result
**Partial match with corrected logic (chronological ordering)**

The core issue is that the SQL uses `ORDER BY u.login` (alphabetical) when it should use `ORDER BY MIN(prr.submitted_at)` (chronological by first review timestamp).

**Pull requests where REVIEWERS values differ (alphabetical vs chronological):**
- Issue 600302582: 2 reviewers, order flipped
- Issue 677204748: 2 reviewers, order flipped
- Issue 733448638: 2 reviewers, order differs (may involve additional ordering rules)

**Key insight:**
When a pull request has multiple reviewers, the order in which they appear in the comma-separated list matters. The ground truth orders reviewers by when they first submitted a review (earliest first), while the predicted SQL incorrectly orders them alphabetically by login name.
