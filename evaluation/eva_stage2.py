import snowflake.connector
import pandas as pd
import os
import numpy as np
import json
import argparse

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

file_path = '../setup/destination/snowflake_credential.json' 
SNOWFLAKE_CONFIG = read_json(file_path)

parser = argparse.ArgumentParser(description="agent")
parser.add_argument("--folder", type=str, required=True, help='Specify the folder name where you want to store the results.')
args = parser.parse_args()

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

    with open(f'./agent_results/{args.folder}/stage2.log', 'a') as f:
        f.write(f"Matched columns: {matched_cols}\n")
        f.write(f"Unmatched columns: {unmatched_cols}\n")
        f.write(f"Missed: {missed_cols}\n\n\n")

def evaluate_stage2(folder, snowflake_config):
    databases = []
    with open(f'./agent_results/{folder}/results.log', 'r') as f:
        for line in f:
            s = line.split(' ')
            if s[0] == 'Success:':
                databases.append(s[1])
                    
    for db in databases:
        tables = [f.name for f in os.scandir(f'./{db}') if f.is_file() and f.name.endswith('.sql')]
        with open(f'./agent_results/{folder}/stage2.log', 'a') as f:
            f.write(f'Database: {db}\n')
            
        for table in tables:
            table = table.split('.')[0]
            with open(f'./agent_results/{folder}/stage2.log', 'a') as f:
                f.write(f'Table: {table}\n')
            try:
                if not os.path.exists(f'./agent_results/{folder}/{db}/{table}.csv'):       
                    conn = snowflake.connector.connect(**snowflake_config)
                    with open(f'./{db}/{table}.sql', 'r') as f:
                        query = f.read()
                    df = pd.read_sql(query, conn)
                    os.makedirs(f'./agent_results/{folder}/{db}', exist_ok=True)
                    df.to_csv(f'./agent_results/{folder}/{db}/{table}.csv', index=False)
                    conn.close()
                df = pd.read_csv(f'./agent_results/{folder}/{db}/{table}.csv')
                df_gt = pd.read_csv(f'./gt/{db}/{table}.csv')
                check_corretness(df_gt, df)
            except Exception as e:
                with open(f'./agent_results/{folder}/stage2.log', 'a') as f:
                    f.write(f'Error: {e}\n\n\n')
