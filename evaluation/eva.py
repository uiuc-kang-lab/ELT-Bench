import json
import os
import argparse
from eva_stage1 import evaluate_stage1
from eva_stage2 import evaluate_stage2

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

file_path = '../setup/destination/snowflake_credential.json'
SNOWFLAKE_CONFIG = read_json(file_path)
parser = argparse.ArgumentParser(description="agent")
parser.add_argument("--folder", type=str, required=True, help='Specify the folder name where you want to store the results.')
parser.add_argument("--example_index", type=str, required=False, default=None, help='Specify problem index range (e.g., 0-99, 0-4, 2,5,7)')
args = parser.parse_args()

# Use data/results instead of agent_results
results_dir = f'../data/results/{args.folder}'
os.makedirs(results_dir, exist_ok=True)

evaluate_stage1(args.folder, SNOWFLAKE_CONFIG, args.example_index)
evaluate_stage2(args.folder, SNOWFLAKE_CONFIG, args.example_index)
