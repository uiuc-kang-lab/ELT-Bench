# Error Classification Annotation Protocol

**Purpose:** Classify column-level SQL generation errors to distinguish between Agent errors (fixable through better SQL generation) and Benchmark errors (requiring benchmark improvements).

**Task:** Read debug files and assign each column to exactly ONE category from the taxonomy below.

**Time estimate:** ~2-3 hours for 50 columns

---

## Instructions

### Step 1: Read the Debug File
Each debug file (`.md` format) contains:
- Database, table, and column name
- Column description from the schema
- Root cause explanation
- Incorrect SQL vs Correct SQL comparison
- Evidence showing the mismatch

### Step 2: Identify the Root Cause
Focus on the **fundamental reason** for the error, not just the symptom. Ask:
- Is this a mistake in the AI agent's SQL logic?
- Or is this a problem with the benchmark (ambiguous specs, wrong ground truth, evaluation issues)?

### Step 3: Assign to ONE Category
Choose the single best-fitting category from the taxonomy below.

### Step 4: Record Your Classification
For each column, record:
```
<database>__<table>__<COLUMN_NAME> | <Category Number or Name>
```

Example:
```
sales__customers__ABOVE_AVERAGE_BOUGHT_QUANTITY | 2
```

---

## Error Taxonomy

### AGENT ERRORS (Mistakes in SQL Generation)

These errors can be fixed by improving the AI agent's SQL generation logic.

---

#### **Category 1: Ambiguous Data Model Description**

**When to use:** The schema documentation is unclear, misleading, or insufficient, making it impossible to determine the correct interpretation.

**Key indicators:**
- Multiple reasonable interpretations exist
- Description doesn't specify critical details
- Terminology is vague or contradictory

**Examples:**
- "Number of wins" - could mean race victories OR total championship points
- "Snowy day" - could mean weather code contains 'SN' OR actual snowfall > 0
- "International shipping" - could mean different countries OR specifically non-USA

**What this is NOT:**
- If the agent simply misread a clear description → Category 2 (Logic Error)
- If the agent used the wrong column but description was clear → Category 4.2 (Wrong Table/Column)

---

#### **Category 2: Semantic Interpretation Errors — Logic (Flawed SQL)**

**When to use:** The SQL is syntactically correct but logically flawed. The agent made a mistake in translation or calculation logic.

**Key indicators:**
- Wrong aggregation (COUNT instead of SUM, wrong GROUP BY scope)
- Incorrect formula or calculation
- Boolean logic inversions (AND/OR mistakes)
- Wrong window function (incorrect PARTITION BY or ORDER BY)
- Type mismatch (using true/false when data stores 0/1)
- Wrong filter conditions
- Over-restrictive or under-restrictive WHERE clauses

**Examples:**
- Counting distinct products when should sum quantities
- Finding max of individual sales instead of max of aggregated totals
- Using `type='VYDAJ' AND operation='VYBER'` when only `operation='VYBER'` is needed
- Calculating average including zero-purchase customers when should only include actual purchases

**What this is NOT:**
- If values match exactly → Category 5.1 (False Positive - Actual Match)
- If it's specifically a JOIN type issue → Category 3 (JOIN Issues)
- If it's specifically a NULL handling issue → Category 7 (NULL Handling)

---

#### **Category 3: INNER vs LEFT JOIN Issues**

**When to use:** Wrong JOIN type causes missing or extra rows.

**Key indicators:**
- INNER JOIN excludes rows when lookup tables have missing data
- Should use LEFT JOIN to preserve all main table rows
- FULL OUTER JOIN creates unwanted combinations
- Implicit filtering through JOIN conditions

**Examples:**
- Joining to advertiser table with INNER JOIN drops campaigns for missing advertisers
- Report data lost because dimension table doesn't have complete lookup data
- Using JOIN when LEFT JOIN would preserve all source records

**What this is NOT:**
- Missing JOIN entirely → Category 4.1 (Missing Join)
- Using wrong table in JOIN → Category 4.2 (Wrong Table/Column)

---

#### **Category 4: Wrong Data Source**

##### **Category 4.1: Missing Join**

**When to use:** Required JOIN operations are completely omitted, making necessary data inaccessible.

**Key indicators:**
- Query needs data from another table but doesn't join to it
- Missing relationship prevents accessing required columns
- Data exists but isn't connected

**Example:**
- Need user information but only query posts table, don't join to users

---

##### **Category 4.2: Wrong Table or Column**

**When to use:** The agent references incorrect source tables or selects wrong columns.

**Key indicators:**
- Using wrong table entirely
- Querying from summary table when should use base table
- Including extraneous JOINs not needed
- Selecting wrong column from otherwise correct table
- Starting from reviews table instead of apps table (missing apps with no reviews)

**Examples:**
- Using `user_reviews` table only, missing apps without reviews
- Using `codesum` column when should use `snowfall` column
- Querying wrong history table

**What this is NOT:**
- If the JOIN type is wrong → Category 3 (JOIN Issues)
- If a JOIN is missing → Category 4.1 (Missing Join)

---

### BENCHMARK ERRORS (Problems with Benchmark Design)

These errors require fixing the benchmark, ground truth, or evaluation methodology.

---

#### **Category 5: False Positives**

The agent's SQL is correct or produces semantically equivalent results, but evaluation flags it as wrong.

##### **Category 5.1: Actual Match**

**When to use:** Generated and ground truth results are functionally identical; the discrepancy is an evaluation artifact.

**Key indicators:**
- Values match exactly when compared properly
- No logical differences
- Likely an issue in stage 2 evaluation script

**Example:**
- All values match to 16 decimal places but still flagged

---

##### **Category 5.2: Format Mismatch**

**When to use:** SQL logic is correct but produces results in an alternative valid format.

**Key indicators:**
- Values as 0-1 vs 0-100% (both valid for percentages)
- Date format differences
- String formatting differences
- Precision differences (2 decimals vs 4 decimals)

**Examples:**
- Agent: 0.456, GT: 45.6% (both represent 45.6%)
- Agent: "2023-01-15", GT: "Jan 15, 2023"

---

##### **Category 5.3: Duplicated Rows in GT**

**When to use:** The generated SQL is correct; mismatches arise from erroneous duplicate rows in the ground truth.

**Key indicator:**
- Ground truth has duplicate rows that shouldn't exist
- Agent produces correct unique rows

---

##### **Category 5.4: NULL Mismatch**

**When to use:** SQL is logically sound but uses different NULL handling than GT, and the schema documentation is silent on which approach is correct.

**Key indicators:**
- Agent uses `COALESCE(col, 0)`, GT preserves NULLs (or vice versa)
- No specification in schema about NULL handling
- Both approaches are defensible

**What this is NOT:**
- If schema says "replace NULL with 0" and agent doesn't → Category 7 (NULL Handling)
- If agent filters out NULLs incorrectly → Category 7 (NULL Handling)

---

##### **Category 5.5: Row Ordering**

**When to use:** SQL logic is correct but final result ordering differs.

**Key indicators:**
- All values match when joined on key column
- Only difference is row order
- Missing or different ORDER BY clause
- Primary key generation causes different ordering

**Examples:**
- Numeric ordering vs string ordering of IDs
- Missing ORDER BY when GT assumes specific order

---

##### **Category 5.6: Other False Positive**

**When to use:** Miscellaneous false positive issues not covered by 5.1-5.5.

---

#### **Category 6: Semantic Interpretation Errors — Domain Knowledge**

**When to use:** The agent lacks domain-specific knowledge that's not explicitly documented in the schema.

**Key indicators:**
- Requires understanding of business context
- Industry-specific terminology misunderstood
- Domain conventions assumed but not stated

**Examples:**
- "Winnings" in racing context: agent thinks it's race victories, but domain experts know it's championship points
- "International shipping": agent thinks it's different countries, but in this business context it specifically means non-USA
- Business-specific definitions not in schema

**What this is NOT:**
- If schema description is genuinely ambiguous → Category 1 (Ambiguous Description)
- If it's a calculation error → Category 2 (Logic Error)

---

#### **Category 7: NULL Handling Issues**

**When to use:** The agent doesn't correctly handle NULL values when requirements ARE specified (explicitly or implicitly through context).

**Key indicators:**
- Schema says "replace NULL with 0" but agent doesn't
- Agent filters out NULLs with `WHERE price IS NOT NULL` when shouldn't
- Missing `NULLS FIRST` or `NULLS LAST` when GT assumes specific NULL ordering
- NULL treated as failing grade when no such rule documented

**Examples:**
- Description says "replace NULL values with 0" but agent doesn't
- Agent filters `WHERE price IS NOT NULL`, causing menus with all-NULL prices to return empty
- Should use `NULLS LAST` to handle NULLs in ordering

**What this is NOT:**
- If schema is silent on NULL handling and both approaches valid → Category 5.4 (NULL Mismatch)

---

#### **Category 8: Key Generation Issues**

**When to use:** The primary key of the result table is generated differently by agent compared to GT, causing row identification/ordering problems.

**Key indicators:**
- Agent creates surrogate key differently than GT
- Key generation logic differs
- Results in row ordering mismatches even though data is correct

**Example:**
- Agent uses hash-based key, GT uses sequential ID
- Different UUID generation strategies

---

#### **Category 9: Unknown Calculation Errors**

**When to use:** GT uses calculations or business rules that cannot be derived from the query specification or schema.

**Key indicators:**
- GT values don't match any reasonable interpretation
- Arbitrary or undocumented business rules in GT
- Agent result is very close (e.g., 99.8%) but not exact due to edge cases
- No documentation explains how GT value was calculated

**Examples:**
- GT shows 156.7 but no interpretation of schema yields this value
- GT applies undocumented discount rules
- GT calculation includes hidden assumptions not in spec

---

## Annotation Tips

### Prioritization Rules

When multiple categories could apply, use this priority:

1. **False Positives (5.x) first** - If values actually match or are equivalent, it's not a real error
2. **Ambiguous Description (1) vs Logic Error (2)** - If a reasonable person could interpret it differently → Category 1; if description is clear but agent misunderstood → Category 2
3. **Specific categories over general** - Use specific categories (3, 4.1, 4.2, 7, 8) when they apply, rather than broad Category 2
4. **Root cause over symptom** - e.g., if agent uses wrong column BECAUSE description was ambiguous → Category 1, not 4.2

### Common Pitfalls

- **Don't confuse symptom with cause:** "Used wrong column" might be Category 4.2, but if the description was ambiguous about which column to use, it's Category 1
- **Check for false positives:** Always verify if values actually differ or it's just formatting/ordering
- **Be consistent:** If you see similar cases, classify them the same way

---

## Files to Annotate

**Location:** `/Users/ype/Downloads/ELT-Bench-elt-bench-verified/reproducibility_artifacts/method_debug_summaries/`

**File list:** See `sampled_files.txt` for the complete list of 50 files to annotate.

### The 50 Files:

1. `./citeseer/summary__citeseer__citeseer_paper_ML_AND_CITED_BUTZ01ALGORITHMIC.md`
2. `./app_store/summary__app_store__apps_NUM_REVIEWS_WITH_NEUTRAL_ATTITUDE.md`
3. `./marketo/summary__marketo__email_sends_STEP_ID.md`
4. `./qualtrics/summary__qualtrics__qualtrics__contact_MAILING_LIST_IDS.md`
5. `./book_publishing_company/summary__book_publishing_company__book_publishers_MOST_EXPENSIVE_BOOK.md`
6. `./mailchimp/summary__mailchimp__mailchimp__automation_activities_MEMBER_ID.md`
7. `./regional_sales/summary__regional_sales__regional_sales__customers_HIGHEST_NET_PROFIIT_FOR_ORDER.md`
8. `./xero/summary__xero__xero__general_ledger_CONTACT_NAME.md`
9. `./apple_store/summary_apple_store__source_type_report__IMPRESSIONS.md`
10. `./financial/summary__financial__clients_NUM_WITHDRAWALS_IN_CASH_TRANSACTIONS.md`
11. `./sales/summary__sales__sales__customers_ABOVE_AVERAGE_BOUGHT_QUANTITY.md`
12. `./social_media/summary__social_media__countries_NUMBER_OF_LIKES.md`
13. `./european_football_2/summary_european_football_2__teams__NUM_WON_2010.md`
14. `./qualtrics/summary__qualtrics__qualtrics__contact_CREATED_AT.md`
15. `./superstore/summary__superstore__products_HAS_A_PROFIT_GREATER_THAN_98_PER_OF_THE_AVERAGE_PROFIT_OF_ALL_PRODUCTS_IN_THE_EAST_REGION.md`
16. `./app_store/summary__app_store__apps_NUM_NAN_OR_NULL_COMMENT_REVIEWS.md`
17. `./books/summary__books__authors_AUTHOR_ID.md`
18. `./apple_store/summary_apple_store__source_type_report__DATE_DAY.md`
19. `./book_publishing_company/summary__book_publishing_company__book_publishers_MOST_YTD_SALE_TITLE.md`
20. `./apple_store/summary_apple_store__source_type_report__FIRST_TIME_DOWNLOADS.md`
21. `./marketo/summary__marketo__email_sends_COUNT_DELIVERIES.md`
22. `./sales_in_weather/summary_sales_in_weather__stores__NUM_ITEMS_SOLD_DURING_A_SNOWY_DAY.md`
23. `./amplitude/summary__amplitude__amplitude__event_enhanced_CLIENT_EVENT_TIME.md`
24. `./youtube_analytics/summary__youtube_analytics__youtube__video_report_AVERAGE_VIEW_DURATION_PERCENTAGE.md`
25. `./facebook_ads/summary__facebook_ads__facebook_ads__ad_set_report_CONVERSIONS.md`
26. `./shakespeare/summary__shakespeare__shakespeare__works_NUM_CHARACTERS.md`
27. `./youtube_analytics/summary__youtube_analytics__youtube__demographics_report_VIEWS_PERCENTAGE.md`
28. `./social_media/summary__social_media__countries_PERCENTAGE_OF_MALE_USERS.md`
29. `./microsoft_ads/summary__microsoft_ads__microsoft_ads__ad_report_SPEND.md`
30. `./regional_sales/summary__regional_sales__regional_sales__customers_AVG_PRICE_OF_ORDER_AFTER_DISCOUNT.md`
31. `./microsoft_ads/summary__microsoft_ads__microsoft_ads__account_report_CONVERSIONS.md`
32. `./ice_hockey_draft/summary__ice_hockey_draft__players_DIFF_GOALS_BEWTEEN_RS_AND_PF.md`
33. `./hockey/summary__hockey__hockey__goalies_NUMBER_OF_SEASONS_PLAYED.md`
34. `./twitter_organic/summary_twitter_organic__tweets__APP_CLICKS.md`
35. `./apple_store/summary_apple_store__source_type_report__INSTALLATIONS.md`
36. `./mailchimp/summary__mailchimp__mailchimp__automation_activities_ACTIVITY_ID.md`
37. `./microsoft_ads/summary__microsoft_ads__microsoft_ads__url_report_CAMPAIGN_NAME.md`
38. `./movies_4/summary__movies_4__person_PERSON_NAME.md`
39. `./cars/summary__cars__countries_FASTEST_CAR.md`
40. `./microsoft_ads/summary__microsoft_ads__microsoft_ads__ad_report_CONVERSIONS.md`
41. `./books/summary__books__publishers_TITLE_OF_THE_OLDEST_BOOK.md`
42. `./twitter_organic/summary_twitter_organic__tweets__TWEET_TEXT.md`
43. `./twitter_organic/summary_twitter_organic__tweets__VIDEO_CONTENT_STARTS.md`
44. `./car_retails/summary__car_retails__car_retails__products_AVERAGE_ACTUAL_PROFIT.md`
45. `./menu/summary_menu__menus__DISH_WITH_HIGHEST_PRICE.md`
46. `./movies_4/summary__movies_4__production_company_CATEGORY_RUNNING_TIME_PER_MOVIE_2016.md`
47. `./regional_sales/summary__regional_sales__regional_sales__products_TOTAL_NET_PROFIT.md`
48. `./apple_store/summary_apple_store__platform_version_report__ACTIVE_DEVICES_LAST_30_DAYS.md`
49. `./microsoft_ads/summary__microsoft_ads__microsoft_ads__ad_group_report_ALL_CONVERSIONS.md`
50. `./amplitude/summary__amplitude__amplitude__event_enhanced_SESSION_STARTED_AT_DAY.md`

---

## Output Format

Create a file named `annotations_<your_name>.txt` with one line per column:

```
database__table__COLUMN | Category
```

**Example:**
```
citeseer__citeseer_paper_ML_AND_CITED_BUTZ01ALGORITHMIC | 4.2
app_store__apps_NUM_REVIEWS_WITH_NEUTRAL_ATTITUDE | 4.2
marketo__email_sends_STEP_ID | 5.1
qualtrics__qualtrics__contact_MAILING_LIST_IDS | 4.2
book_publishing_company__book_publishers_MOST_EXPENSIVE_BOOK | 7
...
```

You can use either:
- Category number: `2`, `4.1`, `5.2`, etc.
- Category name: `Logic Error`, `Missing Join`, `Format Mismatch`, etc.

---

## Questions?

If you encounter edge cases or unclear situations:
1. Document your reasoning
2. Make your best judgment based on the root cause
3. Be consistent with similar cases
4. Note any particularly difficult cases in a separate file

Your annotations will be compared with other annotators to measure inter-annotator agreement.
