import snowflake.connector
import pandas as pd
import os
import numpy as np
import json
import argparse
from pathlib import Path

CURRENT_PATH = Path(__file__).parent


def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def check_corretness(df_gt, df):

    matched_cols = []
    unmatched_cols = []
    missed_cols = []

    def vectors_match(v1, v2, tol=1e-2):
        if len(v1) != len(v2):
            return False
        count = 0
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if float(b) > float(a) * 1.01 or float(b) < float(a) * 0.99:
                    return False
            elif a != b:
                return False
            count += 1
        return True
    
    tolerance = 1e-7

    for gold_col in df_gt.columns:
        if gold_col in df.columns:
            if not vectors_match(df_gt[gold_col], df[gold_col], tolerance):
                unmatched_cols.append(gold_col)
            else:
                matched_cols.append(gold_col)
        else:
            missed_cols.append(gold_col)
    if len(missed_cols) == 0 and len(unmatched_cols) == 0:
        return True
    else:
        return False


def evaluate_stage2(folder, snowflake_config, db):
    tables = [f.name for f in os.scandir(f'{CURRENT_PATH}/{db}') if f.is_file() and f.name.endswith('.sql')]
    success_count = 0
    for table in tables:
        table = table.split('.')[0]
        try:
            if not os.path.exists(f'{CURRENT_PATH}/agent_results/{folder}/{db}/{table}.csv'):       
                conn = snowflake.connector.connect(**snowflake_config)
                with open(f'{CURRENT_PATH}/{db}/{table}.sql', 'r') as f:
                    query = f.read()
                df = pd.read_sql(query, conn)
                os.makedirs(f'./agent_results/{folder}/{db}', exist_ok=True)
                df.to_csv(f'{CURRENT_PATH}/agent_results/{folder}/{db}/{table}.csv', index=False)
                conn.close()
            df = pd.read_csv(f'{CURRENT_PATH}/agent_results/{folder}/{db}/{table}.csv')
            df_gt = pd.read_csv(f'{CURRENT_PATH}/gt/{db}/{table}.csv')
            if check_corretness(df_gt, df):
                success_count += 1
        except Exception as e:
            continue
    return success_count, len(tables)
