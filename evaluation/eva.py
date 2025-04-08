import json
import os
import argparse
from typing import Tuple
from evaluation.eva_stage1 import evaluate_stage1
from evaluation.eva_stage2 import evaluate_stage2
from inspect_ai.scorer import (
    Score,
    Scorer,
    accuracy,
    scorer,
    Target,
    Metric,
    metric,
    value_to_float,
    SampleScore,
    ValueToFloat
)

from pathlib import Path

from inspect_ai.solver import Generate, Solver, solver, TaskState

CURRENT_PATH = Path(__file__).parent

@metric
def elt_accurary(to_float: ValueToFloat = value_to_float()) -> Metric:
    def metric(scores: list[SampleScore]) -> dict:
        stage1_success = 0.0
        stage2_success = 0.0
        stage2_total = 0.0
        for item in scores:
            stage1_success += to_float(item.score.value[0])
            stage2_success += to_float(item.score.value[1])
            stage2_total += to_float(item.score.value[2])
        return {'stage1 accuracy': stage1_success / float(len(scores)), 'stage2 accuracy': stage2_success/stage2_total}

    return metric


def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

@scorer(metrics=[elt_accurary()])
def eva_elt(task_id):
    async def score(state: TaskState, target: Target) -> Tuple[Score, Score]:     
        db = state._sample_id
        folder = task_id

        file_path = f'{CURRENT_PATH.parent}/setup/destination/snowflake_credential.json' 
        SNOWFLAKE_CONFIG = read_json(file_path)

        os.makedirs(f'{CURRENT_PATH}/agent_results/{task_id}', exist_ok=True)

        stage1_result = evaluate_stage1(task_id, SNOWFLAKE_CONFIG, db)
        if stage1_result:
            stage1_score = 1
            stage2_score, stage2_total = evaluate_stage2(task_id, SNOWFLAKE_CONFIG, db)
        else:
            stage1_score = 0
            tables = [f.name for f in os.scandir(f'{CURRENT_PATH}/{db}') if f.is_file() and f.name.endswith('.sql')]
            stage2_score, stage2_total = 0, len(tables)
        return Score(value=[stage1_score, stage2_score, stage2_total])
    return score