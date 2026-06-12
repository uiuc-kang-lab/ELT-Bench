# Column Mismatch Summary

## Database: movies_4
## Table: movies4__person
## Column: PERCENTAGE_OF_MOVIE_VOTE_AVERAGE_OVER_5

**Description:**
The percentage of movies, in which the person worked as a crew member, that have a vote average over 5.0.

---

## Root Cause
**GENUINE ERROR - Two issues in Pred SQL:**

1. **NULL↔0 handling** (56,360 persons): Pred returns 0 for persons without crew records, GT returns NULL - this is a FALSE POSITIVE (eval script handles this)
2. **Missing DISTINCT** (614 persons): Pred counts crew records instead of unique movies

---

## Issue 1: NULL↔0 Handling (FALSE POSITIVE - 56,360 persons)

Persons without any crew records:
- GT: NULL (53,348 persons)
- Pred: 0.0
- **Status**: Matched by eval script's NULL↔0 equivalence

---

## Issue 2: Missing DISTINCT (GENUINE ERROR - 614 persons)

### The Problem
A person can have multiple crew roles in the same movie (e.g., Producer AND Co-Producer). The Pred SQL counts each crew record instead of unique movies.

### Example: Person 1001817
```
movie_crew records:
  Movie 176 (Saw) - Production Manager
  Movie 176 (Saw) - Co-Producer        <- Same movie, different role
  Movie 11090 (The Animal) - Unit Production Manager

Movies and their vote_average:
  Movie 176: vote_average = 7.2 (> 5.0)
  Movie 11090: vote_average = 4.6 (<= 5.0)
```

### GT Logic (CORRECT)
GT counts unique movies:
```sql
COUNT(DISTINCT movie_id)  -- 2 unique movies
-- Movies > 5.0: 1 (only Movie 176)
-- Percentage: 1/2 = 50%
```

### Pred Logic (INCORRECT)
Pred counts crew records:
```sql
COUNT(movie_id)  -- 3 crew records (Movie 176 counted twice)
-- Records with vote_avg > 5.0: 2 (both Movie 176 records)
-- Percentage: 2/3 = 66.67%
```

---

## Evidence

**Sample persons with calculation errors:**

| Person ID | Unique Movies | Crew Records | GT | Pred | GT Calc | Pred Calc |
|-----------|---------------|--------------|-----|------|---------|-----------|
| 1001817 | 2 | 3 | 50.00% | 66.67% | 1/2 | 2/3 |
| 1008052 | 8 | 10 | 87.50% | 90.00% | 7/8 | 9/10 |
| 1017340 | 5 | 6 | 60.00% | 50.00% | 3/5 | 3/6 |
| 10122 | 12 | 13 | 83.33% | 84.62% | 10/12 | 11/13 |

**Verification:**
```python
# For Person 1001817:
# GT: 1 movie > 5.0 out of 2 unique movies = 50%
# Pred: 2 records > 5.0 out of 3 records = 66.67%
```

**Impact:**
* NULL↔0 cases: 56,360/56,360 matched (eval script handles this)
* DISTINCT bug cases: 614 persons have wrong percentages
* Overall: **104,224/104,838 matches (99.41%)** after NULL↔0 equivalence

---

## Result

**GENUINE ERROR** (for the 614 calculation mismatches)

The Pred SQL is missing `DISTINCT` when counting movies:
```sql
-- Incorrect (current):
COUNT(movie_id) AS total_movies
SUM(CASE WHEN vote_average > 5.0 THEN 1 ELSE 0 END) AS movies_over_5

-- Correct:
COUNT(DISTINCT movie_id) AS total_movies
COUNT(DISTINCT CASE WHEN vote_average > 5.0 THEN movie_id END) AS movies_over_5
```

**Category**: Should be moved from "False Positives - NULL Mismatch" to "Semantic Interpretation Errors - Logic (Flawed SQL)"
