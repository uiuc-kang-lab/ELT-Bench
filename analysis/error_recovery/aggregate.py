#!/usr/bin/env python3
"""Validate and aggregate independent flat-seven trajectory annotations offline.

The default requires all 500 selected trajectories. --allow-partial explicitly
produces a provisional table using only complete, validated annotations.
Historical labels are read only by the optional final --compare operation.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import sys
from runtime_utils import load_manifest
from run import validate_result as validate_runner_result

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
    'opus_snowflake': 'Claude Agent (Opus 4.7), Snowflake',
    'opus_databricks': 'Claude Agent (Opus 4.7), Databricks',
    'opus_redshift': 'Claude Agent (Opus 4.7), Redshift',
    'kimi_snowflake': 'OpenHands Agent (Kimi K3), Snowflake',
    'glm_snowflake': 'OpenHands Agent (GLM-5.3), Snowflake',
}
IDENTITY_FIELDS = ('trajectory_id', 'task', 'agent', 'warehouse', 'run_id',
                   'source_path', 'source_sha256')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    def no_duplicates(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'Duplicate JSON object key: ' + key)
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=no_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ValueError('Non-finite JSON number: ' + value)))


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_schema(value, schema, root=None, path='$'):
    """Stdlib validator for every keyword used by the accompanying full schema."""
    root = schema if root is None else root
    if isinstance(schema, bool):
        require(schema, path + ': schema forbids value')
        return
    if '$ref' in schema:
        ref = schema['$ref']
        require(ref.startswith('#/'), 'Only local schema references are supported')
        target = root
        for key in ref[2:].split('/'):
            target = target[key.replace('~1', '/').replace('~0', '~')]
        validate_schema(value, target, root, path)
    for branch in schema.get('allOf', []):
        validate_schema(value, branch, root, path)
    for key in ('anyOf', 'oneOf'):
        if key in schema:
            matched = 0
            for branch in schema[key]:
                try:
                    validate_schema(value, branch, root, path)
                    matched += 1
                except ValueError:
                    pass
            require(matched > 0 and (key != 'oneOf' or matched == 1), path + ': ' + key + ' mismatch')
    if 'if' in schema:
        try:
            validate_schema(value, schema['if'], root, path)
            branch = 'then'
        except ValueError:
            branch = 'else'
        if branch in schema:
            validate_schema(value, schema[branch], root, path)
    if 'enum' in schema:
        require(any(type(value) is type(x) and value == x for x in schema['enum']), path + ': enum mismatch')
    if 'const' in schema:
        require(type(value) is type(schema['const']) and value == schema['const'], path + ': const mismatch')
    if 'type' in schema:
        types = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        matches = {'null': value is None, 'object': isinstance(value, dict),
                   'array': isinstance(value, list), 'string': isinstance(value, str),
                   'boolean': isinstance(value, bool), 'integer': is_integer(value),
                   'number': isinstance(value, (int, float)) and not isinstance(value, bool)}
        require(any(matches.get(t, False) for t in types), path + ': type mismatch')
    if isinstance(value, dict):
        require(set(schema.get('required', [])) <= set(value), path + ': required field missing')
        require(len(value) >= schema.get('minProperties', 0), path + ': too few properties')
        props = schema.get('properties', {})
        for key, child in value.items():
            if key in props:
                validate_schema(child, props[key], root, path + '.' + key)
            elif schema.get('additionalProperties') is False:
                raise ValueError(path + ': unexpected property ' + key)
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), path + ': too few items')
        if 'maxItems' in schema:
            require(len(value) <= schema['maxItems'], path + ': too many items')
        if schema.get('uniqueItems'):
            require(len({json.dumps(x, sort_keys=True) for x in value}) == len(value), path + ': duplicate items')
        if 'items' in schema:
            for i, child in enumerate(value):
                validate_schema(child, schema['items'], root, path + '[' + str(i) + ']')
        if 'contains' in schema:
            count = 0
            for child in value:
                try:
                    validate_schema(child, schema['contains'], root, path)
                    count += 1
                except ValueError:
                    pass
            require(count >= schema.get('minContains', 1), path + ': required evidence item missing')
    if isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), path + ': string too short')
        if 'pattern' in schema:
            require(re.search(schema['pattern'], value) is not None, path + ': pattern mismatch')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in schema:
            require(value >= schema['minimum'], path + ': below minimum')


def validate_annotation(result, item, payload, schema):
    validate_schema(result, schema)
    tid = item['trajectory_id']
    for key in IDENTITY_FIELDS:
        require(result['metadata'][key] == item[key], tid + ': metadata mismatch: ' + key)
        require(payload['metadata'][key] == item[key], tid + ': payload identity mismatch: ' + key)
    turns, tool_rows = {}, {}
    for tool in payload['turn_index']:
        seq, turn = tool['tool_seq'], tool['decision_turn']
        require(is_integer(seq) and seq >= 0 and seq not in turns, tid + ': invalid or duplicate input tool sequence')
        require(is_integer(turn) and turn >= 0, tid + ': invalid input decision turn')
        turns[seq], tool_rows[seq] = turn, tool
    require(len(turns) == item['tool_count'], tid + ': input tool count mismatch')
    require(len(payload['trajectory']) == item['trajectory_entries'], tid + ': trajectory entry count mismatch')
    entry_base = 1 if payload['metadata']['agent'].startswith('Claude') else 0
    ids = [e['episode_id'] for e in result['episodes']]
    require(len(set(ids)) == len(ids), tid + ': duplicate episode IDs')
    warnings = []

    def check_pointer(pointer, where):
        if pointer is None:
            return
        if isinstance(pointer, str):
            require(bool(pointer.strip()), where + ': empty source locator')
            return
        require(any(v is not None for v in pointer.values()), where + ': empty source pointer')
        seq = pointer.get('tool_seq')
        if seq is not None:
            require(seq in turns, where + ': pointer tool sequence not in mapping')
            if pointer.get('decision_turn') is not None:
                require(pointer['decision_turn'] == turns[seq], where + ': evidence decision-turn mismatch')
        for key in ('trajectory_entry', 'response_entry'):
            if pointer.get(key) is not None:
                require(entry_base <= pointer[key] < item['trajectory_entries'] + entry_base, where + ': evidence entry out of range')

    for ep in result['episodes']:
        label = tid + '/' + ep['episode_id']
        require(ep['category'] in CATEGORIES, label + ': unknown category')
        require(ep['feedback_recovery_eligible'] is True, label + ': ineligible included episode')
        refs = list(ep['related_episode_ids'])
        if ep['parent_episode_id'] is not None:
            refs.append(ep['parent_episode_id'])
        require(all(x in ids and x != ep['episode_id'] for x in refs), label + ': invalid episode relationship')
        for key in ('failure_calls', 'repair_calls', 'verification_calls'):
            for seq in ep[key]:
                require(is_integer(seq) and seq in turns, label + ': invalid ' + key + ' tool sequence')
        first, failure_turn = ep['first_failure_tool_seq'], ep['failure_decision_turn']
        if first is not None:
            require(first in turns, label + ': unmapped first failure tool')
            require(failure_turn == turns[first], label + ': failure decision-turn mismatch')
            require(ep['failure_calls'] and first == min(ep['failure_calls']), label + ': first failure call mismatch')
        else:
            require(failure_turn is None, label + ': failure turn without tool endpoint')
            require(not turns, label + ': missing endpoint despite available full turn map')
        recovery, recovery_turn = ep['recovery_tool_seq'], ep['recovery_decision_turn']
        if ep['outcome'] == 'recovered':
            if recovery is not None:
                require(recovery in turns, label + ': unmapped recovery tool')
                require(recovery_turn == turns[recovery], label + ': recovery decision-turn mismatch')
                require(recovery in ep['verification_calls'], label + ': recovery call not in verification list')
                require(first is None or recovery >= first, label + ': recovery precedes failure')
            else:
                require(recovery_turn is None, label + ': recovery turn without tool endpoint')
                require(not turns, label + ': missing recovery endpoint despite available map')
            if failure_turn is not None and recovery_turn is not None:
                delta = recovery_turn - failure_turn
                require(delta >= 0 and ep['repair_turns'] == delta, label + ': incorrect decision-turn delta')
                if delta == 0:
                    warnings.append({'episode_id': ep['episode_id'], 'reason': 'zero_turn_recovery_requires_semantic_review'})
            else:
                require(ep['repair_turns'] is None, label + ': unknown endpoint requires null span')
        else:
            require(all(ep[key] is None for key in ('recovery_tool_seq', 'recovery_decision_turn', 'repair_turns', 'recovery_method')),
                    label + ': non-recovered episode has recovery values')
        for evidence in ep['evidence']:
            check_pointer(evidence['pointer'], label)
            if evidence['role'] in {'failure', 'verification'}:
                require(evidence['pointer'] is not None, label + ': decisive evidence lacks locator')
    for observation in result['excluded_observations']:
        check_pointer(observation['pointer'], tid)
    inv_ids = set()
    for inv in result['dbt_usage']:
        require(inv['invocation_id'] not in inv_ids, tid + ': duplicate dbt invocation ID')
        inv_ids.add(inv['invocation_id'])
        if inv['tool_seq'] is not None:
            require(inv['tool_seq'] in turns, tid + ': dbt invocation tool not in mapping')
            require(inv['decision_turn'] in (None, turns[inv['tool_seq']]), tid + ': dbt invocation turn mismatch')
        for ev in inv['evidence']:
            check_pointer(ev['pointer'], tid)
    return warnings


def make_rows(accepted):
    buckets = defaultdict(list)
    tasks = defaultdict(set)
    for item, result, _provenance in accepted:
        for ep in result['episodes']:
            key = item['group'], ep['category']
            buckets[key].append(ep)
            tasks[key].add(item['task'])
    rows = []
    for group, display in GROUPS.items():
        for category, name in CATEGORIES.items():
            eps = buckets[group, category]
            outcomes = Counter(e['outcome'] for e in eps)
            recovered = [e for e in eps if e['outcome'] == 'recovered']
            spans = [e['repair_turns'] for e in recovered if e['repair_turns'] is not None]
            rows.append({
                'group': group, 'agent_warehouse': display, 'category': category,
                'failure_category': name, 'episodes': len(eps), 'tasks': len(tasks[group, category]),
                'recovered_episodes': len(recovered),
                'recovery_rate': 100.0 * len(recovered) / len(eps) if eps else None,
                'mean_repair_turns': statistics.mean(spans) if spans else None,
                'median_repair_turns': statistics.median(spans) if spans else None,
                'recovered_turn_sum': sum(spans), 'recovered_with_known_turns': len(spans),
                'recovered_with_missing_turns': len(recovered) - len(spans),
                'outcomes': dict(sorted(outcomes.items())),
            })
    return rows


def compare_rows(rows, old_table):
    require(isinstance(old_table, dict) and isinstance(old_table.get('rows'), list), 'Comparison requires a table object with rows')
    old = {}
    for row in old_table['rows']:
        key = row['group'], row['category']
        require(key not in old, 'Duplicate historical comparison cell')
        old[key] = row
    require(set(old) == {(r['group'], r['category']) for r in rows}, 'Historical comparison cell set mismatch')
    fields = ('episodes', 'recovered_episodes', 'recovery_rate', 'mean_repair_turns',
              'median_repair_turns', 'recovered_with_known_turns', 'recovered_with_missing_turns')
    output = []
    for row in rows:
        previous = old[row['group'], row['category']]
        changes = {}
        for key in fields:
            before, after = previous.get(key), row[key]
            changes[key] = {'previous': before, 'fresh': after,
                            'delta': after - before if before is not None and after is not None else None}
        output.append({'group': row['group'], 'category': row['category'],
                       'changed': any(x['previous'] != x['fresh'] for x in changes.values()), 'metrics': changes})
    return output


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def write_outputs(out, rows, accounting, validation, provenance, comparisons=None):
    out = Path(out)
    if (out / 'table.json').exists():
        existing = load_json(out / 'table.json')
        require(existing.get('execution_mode') == 'independent_fresh_annotation',
                'Refusing to overwrite a table that is not an independent fresh aggregation')
        require(not (existing.get('status') == 'complete' and accounting['provisional']),
                'Refusing to replace a complete fresh table with a provisional subset; choose another output directory')
    status = 'complete' if not accounting['provisional'] else 'PROVISIONAL'
    table = {'execution_mode': 'independent_fresh_annotation', 'protocol_version': 'elt-recovery-flat8-concise-v2',
             'status': status, 'validated_trajectories': accounting['accepted_trajectories'], 'rows': rows}
    csvbuf = io.StringIO()
    writer = csv.DictWriter(csvbuf, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v for k, v in row.items()})
    cells = {(r['group'], r['category']): r for r in rows}
    lines = [status + ': independent fresh trajectory annotations',
             'Validated trajectories: ' + str(accounting['accepted_trajectories']) + '/500.',
             'Each cell: episodes / verified recovery percentage / mean known recovered decision-turn span.',
             'Missing recovered spans are reported in table.json and table.csv.', '',
             '| Failure category | ' + ' | '.join(GROUPS.values()) + ' |',
             '| ' + ' | '.join(['---'] * 6) + ' |']
    for category, label in CATEGORIES.items():
        vals = []
        for group in GROUPS:
            row = cells[group, category]
            rate = '–' if row['recovery_rate'] is None else format(row['recovery_rate'], '.1f')
            mean = '–' if row['mean_repair_turns'] is None else format(row['mean_repair_turns'], '.2f')
            vals.append(str(row['episodes']) + ' / ' + rate + ' / ' + mean)
        lines.append('| ' + label + ' | ' + ' | '.join(vals) + ' |')
    atomic_text(out / 'table.json', json_text(table))
    atomic_text(out / 'table.csv', csvbuf.getvalue())
    atomic_text(out / 'table.txt', '\n'.join(lines) + '\n')
    atomic_text(out / 'cohort_accounting.json', json_text(accounting))
    atomic_text(out / 'validation.json', json_text(validation))
    atomic_text(out / 'provenance.json', json_text(provenance))
    if comparisons is not None:
        atomic_text(out / 'historical_cell_deltas.json', json_text(comparisons))
    elif (out / 'historical_cell_deltas.json').exists():
        (out / 'historical_cell_deltas.json').unlink()


def aggregate(args):
    manifest = load_manifest(args.manifest)
    require(manifest.get('analysis_mode') == 'fresh_annotation', 'Manifest must identify fresh_annotation')
    items = manifest.get('trajectories', [])
    require(isinstance(items, list) and items, 'Empty or invalid fresh manifest')
    require(manifest.get('prepared_trajectory_count') == len(items), 'Manifest prepared count mismatch')
    by_id, by_task, groups = {}, set(), Counter()
    for item in items:
        tid = item['trajectory_id']
        require(isinstance(tid, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', tid), 'Unsafe trajectory identifier')
        require(tid not in by_id, 'Duplicate manifest trajectory identity')
        require(item['group'] in GROUPS, 'Unknown manifest cohort group')
        pair = item['group'], item['task']
        require(pair not in by_task, 'Duplicate group/task in selected manifest')
        by_id[tid] = item
        by_task.add(pair)
        groups[item['group']] += 1
    full_manifest = len(items) == 500 and all(groups[g] == 100 for g in GROUPS)
    if full_manifest:
        task_sets = [{x['task'] for x in items if x['group'] == g} for g in GROUPS]
        require(all(s == task_sets[0] for s in task_sets), 'Selected task sets differ across five groups')
    require(full_manifest or args.allow_partial, 'Full aggregation requires the 500-trajectory manifest (100 in each group)')
    expected = {tid + '.json' for tid in by_id}
    extra = {p.name for p in args.results.glob('*.json')} - expected
    require(not extra, 'Unexpected JSON result files: ' + ', '.join(sorted(extra)))
    require(args.output_dir.resolve() not in {args.results.resolve(), args.provenance.resolve()}, 'Output directory must be separate from results/provenance inputs')
    schema = load_json(args.schema)
    hashes = {'prompt_sha256': sha256(args.prompt), 'schema_sha256': sha256(args.schema),
              'provider_schema_sha256': sha256(args.provider_schema)}
    accepted, missing, incomplete, warnings, result_locks = [], [], [], [], []
    for tid in sorted(by_id):
        item = by_id[tid]
        result_path, prov_path = args.results / (tid + '.json'), args.provenance / (tid + '.json')
        if not result_path.is_file():
            missing.append(tid)
            continue
        require(prov_path.is_file(), tid + ': result has no accepted provenance')
        prov, result = load_json(prov_path), load_json(result_path)
        require(prov.get('status') == 'accepted' and prov.get('analysis_mode') == 'fresh_annotation', tid + ': result is not an accepted fresh annotation')
        require(prov.get('trajectory_id') == tid, tid + ': provenance identity mismatch')
        required_hashes = {**hashes, 'source_sha256': item['source_sha256'],
                           'payload_sha256': item['payload_sha256'], 'output_sha256': sha256(result_path)}
        for key, digest in required_hashes.items():
            require(prov.get(key) == digest, tid + ': provenance/hash mismatch: ' + key)
        require(isinstance(prov.get('model_settings'), dict) and prov['model_settings'], tid + ': missing model provenance')
        require(isinstance(prov.get('request_sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', prov['request_sha256']), tid + ': missing request hash')
        payload_path = Path(item['payload_path'])
        require(sha256(payload_path) == item['payload_sha256'], tid + ': payload hash mismatch')
        payload = load_json(payload_path)
        if args.verify_raw_sources:
            require(sha256(item['source_path']) == item['source_sha256'], tid + ': raw source hash mismatch')
        validate_runner_result(result, item, payload, schema)
        for warning in validate_annotation(result, item, payload, schema):
            warnings.append({'trajectory_id': tid, **warning})
        coverage = result['coverage']
        fully_reviewed = (coverage['review_status'] == 'complete' and
                          all(coverage[key] in {'reviewed_complete', 'not_reached'}
                              for key in ('extraction_loading', 'transformation')))
        if not fully_reviewed:
            incomplete.append({'trajectory_id': tid, 'coverage': coverage})
            continue
        accepted.append((item, result, prov))
        result_locks.append({'trajectory_id': tid, 'result_sha256': sha256(result_path),
                             'provenance_sha256': sha256(prov_path), 'payload_sha256': item['payload_sha256'],
                             'request_sha256': prov['request_sha256'], 'attempt_id': prov.get('attempt_id')})
    provisional = not full_manifest or bool(missing) or bool(incomplete)
    require(not provisional or args.allow_partial,
            'Incomplete cohort: ' + str(len(missing)) + ' missing and ' + str(len(incomplete)) + ' incompletely reviewed results; use --allow-partial only for an explicit provisional table')
    rows = make_rows(accepted)
    accepted_by_group = Counter(x[0]['group'] for x in accepted)
    outcome_counts, dbt_status = Counter(), Counter()
    for _item, result, _prov in accepted:
        outcome_counts.update(e['outcome'] for e in result['episodes'])
        dbt_status[result['dbt_usage_inventory_status']] += 1
    accounting = {
        'analysis_mode': 'independent_fresh_annotation', 'provisional': provisional,
        'expected_trajectories': 500, 'manifest_trajectories': len(items),
        'accepted_trajectories': len(accepted), 'missing_result_ids': missing,
        'incomplete_results': incomplete,
        'groups': {g: {'manifest_trajectories': groups[g], 'accepted_trajectories': accepted_by_group[g]} for g in GROUPS},
        'episodes': sum(r['episodes'] for r in rows), 'outcomes': dict(sorted(outcome_counts.items())),
        'excluded_observations': sum(len(x[1]['excluded_observations']) for x in accepted),
        'dbt_usage_inventory_status': dict(sorted(dbt_status.items())),
        'dbt_invocations': sum(len(x[1]['dbt_usage']) for x in accepted),
        'recovered_with_known_turns': sum(r['recovered_with_known_turns'] for r in rows),
        'recovered_with_missing_turns': sum(r['recovered_with_missing_turns'] for r in rows),
    }
    settings = Counter(json.dumps(x[2]['model_settings'], sort_keys=True) for x in accepted)
    observed = Counter(model for x in accepted for model in set(x[2].get('observed_models', [])))
    provenance = {'manifest_path': str(args.manifest.resolve()), 'manifest_sha256': sha256(args.manifest),
                  'aggregator_sha256': sha256(__file__), **hashes,
                  'model_settings': [{'settings': json.loads(k), 'trajectories': n} for k, n in sorted(settings.items())],
                  'observed_models': dict(sorted(observed.items())), 'results': result_locks}
    validation = {'status': 'passed_provisional' if provisional else 'passed_complete',
                  'semantic_reannotation': 'Model-produced annotations; validation checks schema, identity, provenance and arithmetic, not semantic ground truth.',
                  'validated_trajectories': len(accepted), 'cells': len(rows), 'categories': len(CATEGORIES),
                  'source_identity_verified': True, 'payload_hashes_verified': True,
                  'raw_source_hashes_verified': args.verify_raw_sources,
                  'prompt_and_schema_hashes_verified': True, 'decision_turn_mapping_verified': True,
                  'warnings': warnings, 'historical_labels_used_for_annotation_or_aggregation': False}
    comparisons = None
    if args.compare:
        # Deliberately read historical values only after fresh aggregation is finished.
        comparisons = {'comparison_only': True, 'fresh_status': validation['status'],
                       'historical_path': str(args.compare.resolve()), 'historical_sha256': sha256(args.compare),
                       'cells': compare_rows(rows, load_json(args.compare))}
    write_outputs(args.output_dir, rows, accounting, validation, provenance, comparisons)
    return {'status': validation['status'], 'validated_trajectories': len(accepted),
            'episodes': accounting['episodes'], 'output_dir': str(args.output_dir.resolve())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=HERE / 'manifest.json')
    parser.add_argument('--results', type=Path, default=HERE / 'fresh_results')
    parser.add_argument('--provenance', type=Path, default=HERE / 'fresh_provenance')
    parser.add_argument('--prompt', type=Path, default=HERE / 'prompt.txt')
    parser.add_argument('--schema', type=Path, default=HERE / 'single_trajectory.schema.json')
    parser.add_argument('--provider-schema', type=Path, default=HERE / 'single_trajectory.output_schema.json')
    parser.add_argument('--output-dir', type=Path, default=HERE / 'fresh_aggregated')
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--verify-raw-sources', action='store_true')
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(aggregate(args), ensure_ascii=False))
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
