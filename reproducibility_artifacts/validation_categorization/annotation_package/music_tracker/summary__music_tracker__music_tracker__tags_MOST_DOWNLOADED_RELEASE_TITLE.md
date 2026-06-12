# Column Mismatch Summary

## Database: music_tracker
## Table: music_tracker__tags
## Column: MOST_DOWNLOADED_RELEASE_TITLE

### Description
The title of the most downloaded release of the tag, with ties broken by the ascending order of the release title.

---

## Root Cause
**No error found - Current implementation is CORRECT**

The current SQL implementation correctly identifies the most downloaded release title for each tag, with proper tie-breaking by ascending alphabetical order of the release title.

### Current SQL Logic (Correct)
```sql
-- Find most downloaded release per tag
most_downloaded AS (
    SELECT
        tag,
        group_name,
        total_snatched,
        ROW_NUMBER() OVER (PARTITION BY tag ORDER BY total_snatched DESC, group_name ASC) as rn
    FROM joined_data
),

most_downloaded_filtered AS (
    SELECT
        tag,
        group_name as most_downloaded_release_title
    FROM most_downloaded
    WHERE rn = 1
)
```

---

## Why the Implementation Is Correct

The current implementation correctly:

1. **Joins tags with torrents**: Uses `tags.id = torrents.id` which correctly links tags to their associated releases
2. **Ranks by downloads**: `ORDER BY total_snatched DESC` correctly prioritizes releases with more downloads
3. **Handles ties correctly**: `group_name ASC` breaks ties alphabetically in ascending order as specified
4. **Selects top result**: `WHERE rn = 1` picks the most downloaded release per tag

**Schema semantics from `source_schemas`:**
- `torrents.totalSnatched`: Number of times the release has been downloaded
- `torrents.groupName`: Release title
- `tags.id`: Release identifier which matches `torrents.id`

---

## Evidence

**Verification results:**

| Metric | Value |
| ------ | ----- |
| Total tags | 3,678 |
| Matches | 3,678 |
| Match rate | 100.0% |

**Sample comparisons showing correct results:**

| Tag | Most Downloaded Release (GT) | Most Downloaded Release (Pred) |
| --- | ---------------------------- | ------------------------------ |
| 1950s | greatest hits of the millennium | greatest hits of the millennium |
| 1960s | greatest hits of the millennium | greatest hits of the millennium |
| 1970s | greatest hits of the millennium | greatest hits of the millennium |
| 1980s | thriller | thriller |
| 1990s | enter the wu-tang (36 chambers) | enter the wu-tang (36 chambers) |

**Impact:**
* Current implementation: **3,678/3,678 matches (100%)**

---

## Result
✅ **Perfect match - No correction needed**

The SQL implementation correctly computes the most downloaded release title for each tag. The logic properly:
- Identifies releases by joining tags to torrents on the `id` field
- Ranks releases by `totalSnatched` (download count) in descending order
- Breaks ties using alphabetical order of the release title (ascending)
- Selects the top-ranked release for each tag

**Note:** There is 1 tag with NULL value in both ground truth and predicted, which is handled correctly (NULL matches NULL).
