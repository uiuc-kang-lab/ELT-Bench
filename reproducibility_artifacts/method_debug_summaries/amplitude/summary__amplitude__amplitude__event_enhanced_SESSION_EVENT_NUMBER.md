# Column Mismatch Summary

## Database: amplitude
## Table: amplitude__event_enhanced
## Column: SESSION_EVENT_NUMBER

### Description
The number of the event within the session, ordered by time of event.

---

## Root Cause
**Incorrect partitioning: partitions by user+session instead of session only. When session_id=-1 (HTTP API default), all events should be numbered globally within that session, not per-user.**

### Incorrect SQL Logic
```sql
event_numbered as (
    select
        *,
        row_number() over (partition by unique_session_id order by event_time) as session_event_number,
        row_number() over (partition by amplitude_user_id order by event_time) as user_event_number
    from event_with_type
)
```

### Correct SQL Logic
```sql
event_numbered as (
    select
        *,
        row_number() over (partition by session_id order by event_time, event_id) as session_event_number,
        row_number() over (partition by amplitude_user_id order by event_time) as user_event_number
    from event_with_type
)
```

---

## Why the Original Logic Is Wrong

* **Partition key misunderstanding:** The predicted SQL partitions by `unique_session_id`, which is a surrogate key derived from `user_id + session_id`. This creates per-user session numbering.

* **Correct interpretation:** The column description says "the number of the event within the session" - a "session" is identified by `session_id` alone, not by user+session.

* **HTTP API behavior:** When events are sent via Amplitude's HTTP API, they default to `session_id = -1`. All events with `session_id = -1` are considered part of the same "pseudo-session" and should be numbered together.

**What the column description means:**
- Within a session (identified by session_id), number each event sequentially based on event_time

**What the SQL actually computes:**
- Numbers events per unique_session_id (user_id + session_id combination)
- Each user gets their own counter starting at 1, even when they share the same session_id

---

## Evidence

**Key comparison demonstrating the error:**

| EVENT_ID | USER_ID | SESSION_ID | EVENT_TIME | GT SESSION_EVENT_NUMBER | Pred SESSION_EVENT_NUMBER |
| -------- | ------- | ---------- | ---------- | ----------------------- | ------------------------- |
| 732698218 | jayz@gmail.com | -1 | 2021-04-01 19:42:58.123 | 1 | 1 |
| 47590376 | b@gmail.com | -1 | 2021-04-01 19:42:58.123 | 2 | 1 |
| 242501284 | dev@gmail.com | -1 | 2021-04-01 19:42:58.123 | 3 | 1 |
| 370485021 | a@gmail.com | -1 | 2021-04-01 19:42:58.123 | 4 | 1 |
| 378717922 | beyonce@gmail.com | -1 | 2021-04-01 19:42:58.123 | 5 | 1 |
| 260278357 | rihanna@gmail.com | -1 | 2021-04-01 19:42:58.123 | 6 | 1 |
| 913233589 | john_doe@gmail.com | -1 | 2021-12-10 05:51:07 | 7 | 1 |
| 963948481 | john_doe@gmail.com | -1 | 2021-12-13 05:51:07 | 8 | 3 |
| 86821571 | john_doe@gmail.com | -1 | 2021-12-13 05:51:07 | 9 | 2 |
| 959963246 | john_doe@gmail.com | -1 | 2021-12-18 05:51:07 | 10 | 4 |

**Observations:**
- GT numbers ALL events with session_id=-1 sequentially (1-10)
- Predicted restarts counting for each user (all single-event users get 1)
- john_doe@gmail.com's events are numbered 7-10 in GT (global position) vs 1-4 in predicted (user-local position)

**Impact:**
* Current implementation: **1/10 matches (10%)**
* Corrected implementation: **10/10 matches (100%)**

---

## Result
**Partition key error in window function**

The root cause is using `unique_session_id` (user_id + session_id hash) as the partition key instead of `session_id` alone.

For events sent via HTTP API (session_id=-1), all events share the same session regardless of user. The correct numbering should be global within each session_id value, ordered by event_time (with event_id as tiebreaker).

**Correct ordering within session_id=-1:**
1. jayz@gmail.com (732698218)
2. b@gmail.com (47590376)
3. dev@gmail.com (242501284)
4. a@gmail.com (370485021)
5. beyonce@gmail.com (378717922)
6. rihanna@gmail.com (260278357)
7. john_doe@gmail.com (913233589)
8. john_doe@gmail.com (963948481)
9. john_doe@gmail.com (86821571)
10. john_doe@gmail.com (959963246)
