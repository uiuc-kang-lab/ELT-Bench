#!/usr/bin/env python3
"""Format a complete 500-trajectory fresh table as wide CSV and LaTeX.

Reads only the selected aggregate table.json as data. It never computes rates
or means, reads annotations, invokes models, or changes aggregate artifacts.
Both output files must be new; existing exports are never overwritten.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
CATEGORIES = {
    'airbyte_config_deploy': 'Airbyte/Terraform configuration and deployment',
    'sync_control_execution': 'Synchronization control and execution',
    'dbt_setup_usage': 'dbt project configuration and command usage',
    'model_sql': 'Model-SQL compilation or execution failures',
    'data_correctness': 'Data correctness (observable in trajectories)',
    'delivery_contract': 'Output location and delivery requirements',
    'sql_exploration_validation': 'Data exploration and validation SQL',
}
GROUPS = {
    'opus_snowflake': ('Opus SF', 'Claude Agent (Opus 4.7), Snowflake'),
    'opus_databricks': ('Opus DB', 'Claude Agent (Opus 4.7), Databricks'),
    'opus_redshift': ('Opus RS', 'Claude Agent (Opus 4.7), Redshift'),
    'kimi_snowflake': ('Kimi SF', 'OpenHands Agent (Kimi K3), Snowflake'),
    'glm_snowflake': ('GLM SF', 'OpenHands Agent (GLM-5.3), Snowflake'),
}
DASH = '\u2013'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_table_bytes(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON object key: ' + key)
            result[key] = value
        return result
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_table(table):
    require(isinstance(table, dict), 'Expected an aggregate table object')
    require(table.get('execution_mode') == 'independent_fresh_annotation', 'Refusing a historical or non-fresh table')
    require(table.get('protocol_version') == 'elt-recovery-flat8-concise-v2', 'Unexpected annotation protocol version')
    require(table.get('status') == 'complete', 'Refusing a provisional or incomplete aggregate table')
    require(type(table.get('validated_trajectories')) is int and table['validated_trajectories'] == 500,
            'Export requires exactly 500 validated trajectories')
    rows = table.get('rows')
    require(isinstance(rows, list) and len(rows) == len(GROUPS) * len(CATEGORIES), f'Expected exactly {len(GROUPS) * len(CATEGORIES)} group/category cells')
    cells = {}
    for row in rows:
        require(isinstance(row, dict), 'Malformed aggregate cell')
        group, category = row.get('group'), row.get('category')
        require(group in GROUPS and category in CATEGORIES, 'Unexpected group or category')
        key = group, category
        require(key not in cells, 'Duplicate group/category cell')
        require(row.get('failure_category') == CATEGORIES[category], 'Category label differs from the aggregate format')
        require(row.get('agent_warehouse') == GROUPS[group][1], 'Agent/warehouse label differs from the aggregate format')
        episodes, rate, mean = row.get('episodes'), row.get('recovery_rate'), row.get('mean_repair_turns')
        require(type(episodes) is int and episodes >= 0, 'Episode count must be a nonnegative integer')
        require('recovery_rate' in row and 'mean_repair_turns' in row, 'Missing displayed aggregate metric')
        require(rate is None or (finite_nonnegative(rate) and rate <= 100), 'Invalid recovery percentage')
        require(mean is None or finite_nonnegative(mean), 'Invalid mean repair-turn span')
        require((episodes == 0 and rate is None and mean is None) or (episodes > 0 and rate is not None),
                'Empty/nonempty cell has inconsistent undefined display metrics')
        cells[key] = row
    require(set(cells) == {(group, category) for group in GROUPS for category in CATEGORIES}, 'Missing aggregate cell')
    return cells


def display_cell(row):
    # Exactly the display rules used in aggregate_fresh.write_outputs.
    rate = DASH if row['recovery_rate'] is None else format(row['recovery_rate'], '.1f')
    mean = DASH if row['mean_repair_turns'] is None else format(row['mean_repair_turns'], '.2f')
    return str(row['episodes']) + ' / ' + rate + ' / ' + mean


def latex_escape(text):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
                    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
                    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}', DASH: r'\textendash{}'}
    return ''.join(replacements.get(char, char) for char in text)


def render(table, source_sha256):
    cells = validate_table(table)
    wide = [['Failure category'] + [display for display, _full in GROUPS.values()]]
    for category, label in CATEGORIES.items():
        wide.append([label] + [display_cell(cells[group, category]) for group in GROUPS])
    csv_buffer = io.StringIO(newline='')
    csv.writer(csv_buffer, lineterminator='\n').writerows(wide)
    latex = [
        '% Generated solely from a complete independent fresh table.json with 500 validated trajectories.',
        '% Source table SHA-256: ' + source_sha256,
        '% Formatting only: stored episode counts, recovery percentages and mean spans are not recomputed.',
        '% Include this fragment in a LaTeX document with \\usepackage{graphicx}.',
        r'\begin{table*}[t]', r'\centering', r'\small',
        r'\caption{Observable ELT failure episodes and recovery in the 500 selected trajectories. '
        r'Each cell is episode count / verified recovery percentage / mean elapsed decision-turn span '
        r'among recovered episodes with known endpoints. Repair turns equal the recovery decision turn '
        r'minus the first-failure decision turn, without adding one; interleaved work is included. '
        r'All included non-recovered episodes remain in the percentage denominator. '
        r'\textendash{} denotes an undefined percentage or mean; recovered episodes with missing spans '
        r'are excluded from the mean and recorded in the source table. '
        r'SF = Snowflake, DB = Databricks, RS = Redshift; Opus = Claude Agent (Opus 4.7), '
        r'Kimi = OpenHands Agent (Kimi K3), GLM = OpenHands Agent (GLM-5.3).}',
        r'\label{tab:elt-failure-recovery}', r'\resizebox{\textwidth}{!}{%',
        r'\begin{tabular}{lccccc}', r'\hline',
        ' & '.join(latex_escape(x) for x in wide[0]) + r' \\', r'\hline',
    ]
    latex.extend(' & '.join(latex_escape(x) for x in row) + r' \\' for row in wide[1:])
    latex.extend([r'\hline', r'\end{tabular}%', '}', r'\end{table*}', ''])
    return {'table_wide.csv': csv_buffer.getvalue(), 'table.tex': '\n'.join(latex)}


def export(table_path, output_dir):
    table_path, output_dir = Path(table_path).resolve(), Path(output_dir).resolve()
    source_bytes = table_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    outputs = render(load_table_bytes(source_bytes), source_sha256)
    destinations = {name: output_dir / name for name in outputs}
    require(all(path != table_path and not path.exists() for path in destinations.values()),
            'Refusing to overwrite an existing source or export file; choose a new output directory')
    # Validate before creating anything. A concurrent aggregate replacement is
    # rejected rather than exporting data under the wrong source hash.
    require(table_path.read_bytes() == source_bytes, 'Source table changed during export preparation')
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary, published = [], []
    try:
        for name, text in outputs.items():
            target = destinations[name]
            tmp = output_dir / ('.' + name + '.' + uuid.uuid4().hex + '.tmp')
            temporary.append(tmp)
            tmp.write_text(text, encoding='utf-8')
            os.link(tmp, target)  # Exclusive publication; never overwrite a raced file.
            published.append(target)
        require(table_path.read_bytes() == source_bytes, 'Source table changed during export publication')
    except Exception:
        for path in published:
            path.unlink()
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return {'status': 'exported_complete_table', 'validated_trajectories': 500,
            'source_table': str(table_path), 'source_table_sha256': source_sha256,
            'outputs': {name: str(path) for name, path in destinations.items()},
            'metrics_recomputed': False, 'annotation_files_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, default=HERE / 'fresh_aggregated' / 'table.json')
    parser.add_argument('--output-dir', type=Path, help='Defaults to the input table directory; outputs must not already exist.')
    args = parser.parse_args()
    try:
        result = export(args.table, args.output_dir or args.table.resolve().parent)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
