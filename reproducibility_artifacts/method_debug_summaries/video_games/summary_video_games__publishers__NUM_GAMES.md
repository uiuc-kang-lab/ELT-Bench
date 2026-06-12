# Column Mismatch Summary

## Database: video_games
## Table: publishers
## Column: NUM_GAMES

### Description (from data_model.yaml)
> The number of games published by the publisher, replace NULL values with 0.

---

## Root Cause
**The SQL uses COUNT(DISTINCT game_id) which should be correct, but the join logic through GAME_PLATFORM may be inadvertently filtering out some game_publisher records, resulting in undercounted games for certain publishers.**

### Predicted SQL Logic
```sql
WITH publisher_games AS (
    SELECT
        p.ID AS publisher_id,
        p.PUBLISHER_NAME AS publisher_name,
        gp.ID AS game_publisher_id,
        g.ID AS game_id,
        g.GAME_NAME AS game_name,
        g.GENRE_ID AS genre_id,
        gpl.RELEASE_YEAR AS release_year
    FROM VG_PUBLISHER p
    LEFT JOIN GAME_PUBLISHER gp ON p.ID = gp.PUBLISHER_ID
    LEFT JOIN GAME g ON gp.GAME_ID = g.ID
    LEFT JOIN GAME_PLATFORM gpl ON gp.ID = gpl.GAME_PUBLISHER_ID
)
SELECT
    publisher_id,
    publisher_name,
    COALESCE(COUNT(DISTINCT game_id), 0) AS num_games
FROM publisher_games
GROUP BY publisher_id, publisher_name
```

### Correct SQL Logic
```sql
-- Remove the GAME_PLATFORM join if it's causing filtering issues
-- Or ensure the join logic does not exclude valid game_publisher records
WITH publisher_games AS (
    SELECT
        p.ID AS publisher_id,
        p.PUBLISHER_NAME AS publisher_name,
        g.ID AS game_id
    FROM VG_PUBLISHER p
    LEFT JOIN GAME_PUBLISHER gp ON p.ID = gp.PUBLISHER_ID
    LEFT JOIN GAME g ON gp.GAME_ID = g.ID
)
SELECT
    publisher_id,
    publisher_name,
    COALESCE(COUNT(DISTINCT game_id), 0) AS num_games
FROM publisher_games
GROUP BY publisher_id, publisher_name
```

---

## Why the Original Logic Is Wrong

* The join chain includes GAME_PLATFORM which may filter out some game_publisher records
* Some game_publisher entries may not have corresponding entries in GAME_PLATFORM
* The differences range from 1 to 6 games per publisher, suggesting systematic undercounting
* NULL game_ids from failed joins may not be handled correctly in the count

---

## Evidence

**Sample Discrepancies:**

| Publisher | GT Value | Predicted Value | Difference |
|-----------|----------|-----------------|------------|
| 5pb | 46 | 45 | -1 |
| Acclaim Entertainment | 119 | 118 | -1 |
| Atari | 267 | 263 | -4 |
| Nintendo | 662 | 659 | -3 |
| Namco Bandai Games | 774 | 768 | -6 |
| Nordcurrent | 5 | 1 | -4 |
| Magical Company | 1 | 0 | -1 |

**Impact:**
* Multiple publishers have incorrect game counts
* The errors affect both large publishers (Nintendo, Atari) and small ones (5pb, Nordcurrent)
* The pattern suggests some games are being excluded from the count

---

## Result

**GAME COUNT MISMATCH**: The predicted values consistently undercount games for publishers. The root cause is likely the join logic which either:
1. Excludes games that don't have GAME_PLATFORM entries
2. Incorrectly handles NULL values from failed joins
3. Has missing or orphan records in the GAME_PUBLISHER table

**Key insight:**
The systematic undercounting across multiple publishers (differences of 1-6 games) suggests a structural issue with the join path rather than individual data quality problems. Review the necessity of the GAME_PLATFORM join and verify all game_publisher records are being included in the count.
