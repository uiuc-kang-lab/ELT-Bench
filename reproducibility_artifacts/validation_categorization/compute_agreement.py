#!/usr/bin/env python3
"""
Three-Way Inter-Annotator Agreement Analysis
eng1 vs eng2 vs eng3

Calculates:
1. Pairwise Cohen's Kappa (all 3 pairs)
2. Fleiss' Kappa (all 3 annotators together)
Both for high-level (Agent/Benchmark) and exact categories
"""

import re
import argparse
from collections import defaultdict
import math

COLUMN_MAPPING = {
    'citeseer__citeseer_paper_ML_AND_CITED_BUTZ01ALGORITHMIC': 'citeseer__citeseer_paper__ML_AND_CITED_BUTZ01ALGORITHMIC',
    'app_store__apps_NUM_REVIEWS_WITH_NEUTRAL_ATTITUDE': 'app_store__apps__NUM_REVIEWS_WITH_NEUTRAL_ATTITUDE',
    'marketo__email_sends_STEP_ID': 'marketo__marketo__email_sends__STEP_ID',
    'qualtrics__qualtrics__contact_MAILING_LIST_IDS': 'qualtrics__qualtrics__contact__MAILING_LIST_IDS',
    'book_publishing_company__book_publishers_MOST_EXPENSIVE_BOOK': 'book_publishing_company__book_publishers__MOST_EXPENSIVE_BOOK',
    'mailchimp__mailchimp__automation_activities_MEMBER_ID': 'mailchimp__mailchimp__automation_activities__MEMBER_ID',
    'regional_sales__regional_sales__customers_HIGHEST_NET_PROFIIT_FOR_ORDER': 'regional_sales__regional_sales__customers__HIGHEST_NET_PROFIIT_FOR_ORDER',
    'xero__xero__general_ledger_CONTACT_NAME': 'xero__xero__general_ledger__CONTACT_NAME',
    'apple_store__source_type_report__IMPRESSIONS': 'apple_store__apple_store__source_type_report__IMPRESSIONS',
    'financial__clients_NUM_WITHDRAWALS_IN_CASH_TRANSACTIONS': 'financial__clients__NUM_WITHDRAWALS_IN_CASH_TRANSACTIONS',
    'sales__sales__customers_ABOVE_AVERAGE_BOUGHT_QUANTITY': 'sales__sales__customers__ABOVE_AVERAGE_BOUGHT_QUANTITY',
    'social_media__countries_NUMBER_OF_LIKES': 'social_media__countries__NUMBER_OF_LIKES',
    'european_football_2__teams__NUM_WON_2010': 'european_football_2__teams__NUM_WON_2010',
    'qualtrics__qualtrics__contact_CREATED_AT': 'qualtrics__qualtrics__contact__CREATED_AT',
    'superstore__products_HAS_A_PROFIT_GREATER_THAN_98_PER_OF_THE_AVERAGE_PROFIT_OF_ALL_PRODUCTS_IN_THE_EAST_REGION': 'superstore__products__HAS_A_PROFIT_GREATER_THAN_98_PER_OF_THE_AVERAGE_PROFIT_OF_ALL_PRODUCTS_IN_THE_EAST_REGION',
    'app_store__apps_NUM_NAN_OR_NULL_COMMENT_REVIEWS': 'app_store__apps__NUM_NAN_OR_NULL_COMMENT_REVIEWS',
    'books__authors_AUTHOR_ID': 'books__authors__AUTHOR_ID',
    'apple_store__source_type_report__DATE_DAY': 'apple_store__apple_store__source_type_report__DATE_DAY',
    'book_publishing_company__book_publishers_MOST_YTD_SALE_TITLE': 'book_publishing_company__book_publishers__MOST_YTD_SALE_TITLE',
    'apple_store__source_type_report__FIRST_TIME_DOWNLOADS': 'apple_store__apple_store__source_type_report__FIRST_TIME_DOWNLOADS',
    'marketo__email_sends_COUNT_DELIVERIES': 'marketo__marketo__email_sends__COUNT_DELIVERIES',
    'sales_in_weather__stores__NUM_ITEMS_SOLD_DURING_A_SNOWY_DAY': 'sales_in_weather__stores__NUM_ITEMS_SOLD_DURING_A_SNOWY_DAY',
    'amplitude__amplitude__event_enhanced_CLIENT_EVENT_TIME': 'amplitude__amplitude__event_enhanced__CLIENT_EVENT_TIME',
    'youtube_analytics__youtube__video_report_AVERAGE_VIEW_DURATION_PERCENTAGE': 'youtube_analytics__youtube__video_report__AVERAGE_VIEW_DURATION_PERCENTAGE',
    'facebook_ads__facebook_ads__ad_set_report_CONVERSIONS': 'facebook_ads__facebook_ads__ad_set_report__CONVERSIONS',
    'shakespeare__shakespeare__works_NUM_CHARACTERS': 'shakespeare__shakespeare__works__NUM_CHARACTERS',
    'youtube_analytics__youtube__demographics_report_VIEWS_PERCENTAGE': 'youtube_analytics__youtube__demographics_report__VIEWS_PERCENTAGE',
    'social_media__countries_PERCENTAGE_OF_MALE_USERS': 'social_media__countries__PERCENTAGE_OF_MALE_USERS',
    'microsoft_ads__microsoft_ads__ad_report_SPEND': 'microsoft_ads__microsoft_ads__ad_report__SPEND',
    'regional_sales__regional_sales__customers_AVG_PRICE_OF_ORDER_AFTER_DISCOUNT': 'regional_sales__regional_sales__customers__AVG_PRICE_OF_ORDER_AFTER_DISCOUNT',
    'microsoft_ads__microsoft_ads__account_report_CONVERSIONS': 'microsoft_ads__microsoft_ads__account_report__CONVERSIONS',
    'ice_hockey_draft__players_DIFF_GOALS_BEWTEEN_RS_AND_PF': 'ice_hockey_draft__players__DIFF_GOALS_BEWTEEN_RS_AND_PF',
    'hockey__hockey__goalies_NUMBER_OF_SEASONS_PLAYED': 'hockey__hockey__goalies__NUMBER_OF_SEASONS_PLAYED',
    'twitter_organic__tweets__APP_CLICKS': 'twitter_organic__twitter_organic__tweets__APP_CLICKS',
    'apple_store__source_type_report__INSTALLATIONS': 'apple_store__apple_store__source_type_report__INSTALLATIONS',
    'mailchimp__mailchimp__automation_activities_ACTIVITY_ID': 'mailchimp__mailchimp__automation_activities__ACTIVITY_ID',
    'microsoft_ads__microsoft_ads__url_report_CAMPAIGN_NAME': 'microsoft_ads__microsoft_ads__url_report__CAMPAIGN_NAME',
    'movies_4__person_PERSON_NAME': 'movies_4__movies4__person__PERSON_NAME',
    'cars__countries_FASTEST_CAR': 'cars__countries__FASTEST_CAR',
    'microsoft_ads__microsoft_ads__ad_report_CONVERSIONS': 'microsoft_ads__microsoft_ads__ad_report__CONVERSIONS',
    'books__publishers_TITLE_OF_THE_OLDEST_BOOK': 'books__publishers__TITLE_OF_THE_OLDEST_BOOK',
    'twitter_organic__tweets__TWEET_TEXT': 'twitter_organic__twitter_organic__tweets__TWEET_TEXT',
    'twitter_organic__tweets__VIDEO_CONTENT_STARTS': 'twitter_organic__twitter_organic__tweets__VIDEO_CONTENT_STARTS',
    'car_retails__car_retails__products_AVERAGE_ACTUAL_PROFIT': 'car_retails__car_retails__products__AVERAGE_ACTUAL_PROFIT',
    'menu__menus__DISH_WITH_HIGHEST_PRICE': 'menu__menus__DISH_WITH_HIGHEST_PRICE',
    'movies_4__production_company_CATEGORY_RUNNING_TIME_PER_MOVIE_2016': 'movies_4__movies4__production_company__CATEGORY_RUNNING_TIME_PER_MOVIE_2016',
    'regional_sales__regional_sales__products_TOTAL_NET_PROFIT': 'regional_sales__regional_sales__products__TOTAL_NET_PROFIT',
    'apple_store__platform_version_report__ACTIVE_DEVICES_LAST_30_DAYS': 'apple_store__apple_store__platform_version_report__ACTIVE_DEVICES_LAST_30_DAYS',
    'microsoft_ads__microsoft_ads__ad_group_report_ALL_CONVERSIONS': 'microsoft_ads__microsoft_ads__ad_group_report__ALL_CONVERSIONS',
    'amplitude__amplitude__event_enhanced_SESSION_STARTED_AT_DAY': 'amplitude__amplitude__event_enhanced__SESSION_STARTED_AT_DAY',
}

def parse_args():
    parser = argparse.ArgumentParser(description='Three-Way Inter-Annotator Agreement Analysis')
    parser.add_argument('--eng1', required=True, help='Path to eng1 annotations (.txt)')
    parser.add_argument('--eng2', required=True, help='Path to eng2 annotations (.txt)')
    parser.add_argument('--eng3', required=True, help='Path to eng3 annotations (.txt)')
    parser.add_argument('--categorization', required=True, help='Path to categorization.md reference')
    return parser.parse_args()

def parse_annotation_txt(file_path):
    """Parse .txt annotation file"""
    annotations = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '|' in line:
                col, cat = line.split('|')
                col = col.strip()
                mapped_col = COLUMN_MAPPING.get(col, col)
                annotations[mapped_col] = cat.strip()
    return annotations

def parse_categorization_md(file_path):
    """Parse categorization file"""
    column_to_category = {}
    current_category = None

    category_map = {
        'Ambiguous Data Model Description': '1',
        'Semantic Interpretation Errors - Logic (Flawed SQL)': '2',
        'INNER vs LEFT JOIN Issues': '3',
        'Missing Join': '4.1',
        'Wrong Table or Column': '4.2',
        'False Positives - Actual Match': '5.1',
        'Actual Match': '5.1',
        'False Positives - Format Mismatch': '5.2',
        'Format Mismatch': '5.2',
        'False Positives - Duplicated Rows in GT': '5.3',
        'Duplicated Rows in GT': '5.3',
        'False Positives - NULL Mismatch': '5.4',
        'NULL Mismatch': '5.4',
        'False Positives - Row Ordering': '5.5',
        'Row Ordering': '5.5',
        'False Positives - Other': '5.6',
        'Semantic Interpretation Errors - Domain Knowledge': '6',
        'NULL Handling Issues': '7',
        'Key Generation Issues (impacts row ordering issues under false positives)': '8',
        'Key Generation Issues': '8',
        'Unknown Calculation (Poor Data Sources or GT Values)': '9',
        'Unknown Calculation Errors': '9',
    }

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('###') or line.startswith('####'):
            current_category = line.lstrip('#').strip().rstrip(':')
            continue
        match = re.match(r'^\d+\.\s+(.+)$', line)
        if match and current_category:
            column_name = match.group(1).strip()
            category_num = category_map.get(current_category, current_category)
            column_to_category[column_name] = category_num

    return column_to_category

def map_to_high_level(category):
    """Map category to Agent vs Benchmark"""
    agent_categories = {'1', '2', '3', '4.1', '4.2', '6', '7', '8'}
    benchmark_categories = {'5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '9'}

    if category in agent_categories:
        return 'Agent'
    elif category in benchmark_categories:
        return 'Benchmark'
    else:
        return 'Unknown'

def cohen_kappa(annotations1, annotations2, level='exact'):
    """Calculate Cohen's Kappa between two annotators"""
    common_cols = set(annotations1.keys()) & set(annotations2.keys())
    if not common_cols:
        return 0, 0, 0, 0

    if level == 'high_level':
        data1 = {col: map_to_high_level(annotations1[col]) for col in common_cols}
        data2 = {col: map_to_high_level(annotations2[col]) for col in common_cols}
    else:
        data1 = {col: annotations1[col] for col in common_cols}
        data2 = {col: annotations2[col] for col in common_cols}

    agreements = sum(1 for col in common_cols if data1[col] == data2[col])
    total = len(common_cols)
    po = agreements / total

    categories = set(data1.values()) | set(data2.values())
    pe = 0
    for cat in categories:
        p1 = sum(1 for col in common_cols if data1[col] == cat) / total
        p2 = sum(1 for col in common_cols if data2[col] == cat) / total
        pe += p1 * p2

    kappa = (po - pe) / (1 - pe) if (1 - pe) != 0 else 0

    return kappa, po, pe, total

def fleiss_kappa(all_annotations, level='exact'):
    """Calculate Fleiss' Kappa for multiple annotators"""
    common_cols = set(all_annotations[0].keys())
    for ann in all_annotations[1:]:
        common_cols &= set(ann.keys())

    if not common_cols:
        return 0, 0, 0, 0

    common_cols = sorted(common_cols)
    n = len(common_cols)
    k = len(all_annotations)

    if level == 'high_level':
        mapped_annotations = []
        for ann in all_annotations:
            mapped_annotations.append({col: map_to_high_level(ann[col]) for col in common_cols})
    else:
        mapped_annotations = all_annotations

    all_cats = set()
    for ann in mapped_annotations:
        for col in common_cols:
            all_cats.add(ann[col])
    all_cats = sorted(all_cats)

    rating_matrix = []
    for col in common_cols:
        ratings = {}
        for cat in all_cats:
            ratings[cat] = sum(1 for ann in mapped_annotations if ann[col] == cat)
        rating_matrix.append(ratings)

    P_values = []
    for ratings in rating_matrix:
        sum_sq = sum(n_ij ** 2 for n_ij in ratings.values())
        P_i = (sum_sq - k) / (k * (k - 1))
        P_values.append(P_i)

    P_bar = sum(P_values) / n

    p_j_values = []
    for cat in all_cats:
        count = sum(ratings[cat] for ratings in rating_matrix)
        p_j = count / (n * k)
        p_j_values.append(p_j ** 2)
    P_e = sum(p_j_values)

    kappa = (P_bar - P_e) / (1 - P_e) if (1 - P_e) != 0 else 0

    return kappa, P_bar, P_e, n

def interpret_kappa(kappa):
    """Interpret kappa value using Landis & Koch scale"""
    if kappa < 0:
        return "Poor (worse than chance)"
    elif kappa < 0.20:
        return "Slight"
    elif kappa < 0.40:
        return "Fair"
    elif kappa < 0.60:
        return "Moderate"
    elif kappa < 0.80:
        return "Substantial"
    else:
        return "Almost Perfect"


# Load all three annotators and reference categorization
args = parse_args()
print("Loading annotations...")
eng1 = parse_annotation_txt(args.eng1)
eng2 = parse_annotation_txt(args.eng2)
eng3 = parse_annotation_txt(args.eng3)
cat_ref = parse_categorization_md(args.categorization)

print(f"eng1: {len(eng1)} annotations")
print(f"eng2: {len(eng2)} annotations")
print(f"eng3: {len(eng3)} annotations")
print(f"categorization.md: {len(cat_ref)} annotations")
print()

# Find common columns across all three annotators
common_eng = set(eng1.keys()) & set(eng2.keys()) & set(eng3.keys())
print(f"Common columns across eng1/eng2/eng3: {len(common_eng)}")

# Find common columns across all three annotators AND categorization.md
common_all = common_eng & set(cat_ref.keys())
print(f"Common columns across eng1/eng2/eng3/categorization.md: {len(common_all)}")
print()

# Create filtered datasets with only common columns (eng annotators only)
eng1_common = {col: eng1[col] for col in common_eng}
eng2_common = {col: eng2[col] for col in common_eng}
eng3_common = {col: eng3[col] for col in common_eng}

# Create filtered datasets including categorization.md
eng1_all = {col: eng1[col] for col in common_all}
eng2_all = {col: eng2[col] for col in common_all}
eng3_all = {col: eng3[col] for col in common_all}
cat_all = {col: cat_ref[col] for col in common_all}

def print_cohen(label, ann1, ann2, level):
    kappa, po, pe, n = cohen_kappa(ann1, ann2, level=level)
    print(f"{label}:")
    print(f"  Observed agreement: {po:.4f} ({po*100:.1f}%)")
    print(f"  Expected agreement: {pe:.4f} ({pe*100:.1f}%)")
    print(f"  Cohen's κ:          {kappa:.4f} - {interpret_kappa(kappa)}")
    print(f"  Common columns:     {n}")
    print()

def print_fleiss(label, annotations_list, level):
    kappa, P_bar, P_e, n = fleiss_kappa(annotations_list, level=level)
    print(f"{label}:")
    print(f"  Mean observed agreement (P̄): {P_bar:.4f} ({P_bar*100:.1f}%)")
    print(f"  Expected agreement (Pe):     {P_e:.4f} ({P_e*100:.1f}%)")
    print(f"  Fleiss' κ:                   {kappa:.4f} - {interpret_kappa(kappa)}")
    print(f"  Items rated:                 {n}")
    print()

# ── Pairwise Cohen's Kappa among annotators ──
print("=" * 80)
print("PAIRWISE COHEN'S KAPPA - HIGH-LEVEL (Agent vs Benchmark)")
print("=" * 80)
print()

print_cohen("eng1 vs eng2", eng1_common, eng2_common, 'high_level')
print_cohen("eng1 vs eng3", eng1_common, eng3_common, 'high_level')
print_cohen("eng2 vs eng3", eng2_common, eng3_common, 'high_level')

print("=" * 80)
print("PAIRWISE COHEN'S KAPPA - EXACT CATEGORY")
print("=" * 80)
print()

print_cohen("eng1 vs eng2", eng1_common, eng2_common, 'exact')
print_cohen("eng1 vs eng3", eng1_common, eng3_common, 'exact')
print_cohen("eng2 vs eng3", eng2_common, eng3_common, 'exact')

# ── Fleiss' Kappa among the three annotators ──
print("=" * 80)
print("FLEISS' KAPPA - THREE ANNOTATORS (eng1/eng2/eng3)")
print("=" * 80)
print()

print_fleiss("HIGH-LEVEL (Agent vs Benchmark)", [eng1_common, eng2_common, eng3_common], 'high_level')
print_fleiss("EXACT CATEGORY", [eng1_common, eng2_common, eng3_common], 'exact')

# ── Cohen's Kappa: each annotator vs categorization.md ──
print("=" * 80)
print("PAIRWISE COHEN'S KAPPA vs CATEGORIZATION.MD - HIGH-LEVEL (Agent vs Benchmark)")
print("=" * 80)
print()

print_cohen("eng1 vs categorization.md", eng1_all, cat_all, 'high_level')
print_cohen("eng2 vs categorization.md", eng2_all, cat_all, 'high_level')
print_cohen("eng3 vs categorization.md", eng3_all, cat_all, 'high_level')

print("=" * 80)
print("PAIRWISE COHEN'S KAPPA vs CATEGORIZATION.MD - EXACT CATEGORY")
print("=" * 80)
print()

print_cohen("eng1 vs categorization.md", eng1_all, cat_all, 'exact')
print_cohen("eng2 vs categorization.md", eng2_all, cat_all, 'exact')
print_cohen("eng3 vs categorization.md", eng3_all, cat_all, 'exact')

# ── Fleiss' Kappa: all three annotators + categorization.md ──
print("=" * 80)
print("FLEISS' KAPPA - ALL FOUR (eng1/eng2/eng3/categorization.md)")
print("=" * 80)
print()

print_fleiss("HIGH-LEVEL (Agent vs Benchmark)", [eng1_all, eng2_all, eng3_all, cat_all], 'high_level')
print_fleiss("EXACT CATEGORY", [eng1_all, eng2_all, eng3_all, cat_all], 'exact')

print("=" * 80)
print("INTERPRETATION GUIDE")
print("=" * 80)
print("""
Landis & Koch (1977) scale:
  < 0.00  = Poor (worse than chance)
  0.00-0.20 = Slight
  0.21-0.40 = Fair
  0.41-0.60 = Moderate
  0.61-0.80 = Substantial
  0.81-1.00 = Almost Perfect

Fleiss' Kappa measures agreement among multiple raters on categorical data.
It's similar to Cohen's Kappa but generalized for more than 2 raters.

High-level agreement (Agent vs Benchmark) is typically higher because:
  - Only 2 categories vs 12 detailed categories
  - Lower chance agreement baseline
  - More fundamental distinction

Exact category agreement is more stringent:
  - Requires agreeing on specific error type
  - Higher chance agreement due to more categories
  - Tests fine-grained taxonomy reliability
""")

print("=" * 80)
