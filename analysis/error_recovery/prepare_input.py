#!/usr/bin/env python3
"""Convert one raw result.json to a sanitized input and a run.py manifest, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from input_sanitization import sanitize, scrub_encoded_authorization
from runtime_utils import HERE, atomic_json, sha256

GROUPS = {
    'opus_snowflake': ('Claude Opus 4.7', 'Snowflake', 'claude'),
    'opus_databricks': ('Claude Opus 4.7', 'Databricks', 'claude'),
    'opus_redshift': ('Claude Opus 4.7', 'Redshift', 'claude'),
    'kimi_snowflake': ('OpenHands Kimi K3', 'Snowflake', 'openhands'),
    'glm_snowflake': ('OpenHands GLM 5.3', 'Snowflake', 'openhands'),
}
CLAUDE_METHOD = ('Consecutive assistant fragments before next feedback grouped as one '
                 'decision turn; SDK num_turns crosschecked.')
OPENHANDS_METHOD = ('Distinct llm_response_id on agent ActionEvent/MessageEvent; parallel '
                    'tools share one decision turn. No retries unrecorded in trajectory inferred.')


def build_turn_index(raw, framework):
    """Rebuild source coordinates, call/result pairs, and observed response turns."""
    trajectory = raw['trajectory']
    if any(not isinstance(entry, dict) for entry in trajectory):
        raise ValueError('Every trajectory entry must be an object')
    entry_turn, tools, warnings = {}, [], []
    n = 0
    if framework == 'claude':
        was_assistant = False
        pending = {}
        for i, entry in enumerate(trajectory, 1):
            if entry.get('role') == 'assistant':
                if not was_assistant:
                    n += 1
                entry_turn[i] = n
                was_assistant = True
            else:
                was_assistant = False
            content = entry.get('content', [])
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get('type') == 'tool_use':
                    call_id = block.get('id')
                    if not call_id or call_id in pending or i not in entry_turn:
                        raise ValueError(f'Invalid or duplicate tool_use at source entry {i}')
                    row = dict(tool_seq=len(tools) + 1, trajectory_entry=i,
                               result_entry=None, decision_turn=entry_turn[i])
                    tools.append(row)
                    pending[call_id] = row
                elif block.get('type') == 'tool_result':
                    row = pending.get(block.get('tool_use_id'))
                    if row is None:
                        warnings.append(f'Unmatched tool_result at source entry {i}')
                    elif row['result_entry'] is not None:
                        raise ValueError(f'Multiple results for one tool call at source entry {i}')
                    else:
                        row['result_entry'] = i
        method, entry_base = CLAUDE_METHOD, 1
        if raw.get('num_turns') is not None and raw['num_turns'] != n:
            warnings.append('Claude native num_turns differs from observable decision turns')
    elif framework == 'openhands':
        seen, observations, errors, actions = {}, {}, {}, []
        for i, entry in enumerate(trajectory):
            kind = entry.get('type')
            if entry.get('source') == 'agent' and kind in ('ActionEvent', 'MessageEvent'):
                response_id = entry.get('llm_response_id')
                if not response_id:
                    raise ValueError(f'Missing llm_response_id at source entry {i}; cannot infer decision turns')
                if response_id not in seen:
                    n += 1
                    seen[response_id] = n
                entry_turn[i] = seen[response_id]
            if kind == 'ObservationEvent':
                action_id = entry.get('action_id')
                if not action_id or action_id in observations:
                    raise ValueError(f'Missing or duplicate observation action_id at source entry {i}')
                observations[action_id] = i
            elif kind == 'AgentErrorEvent':
                call_id = entry.get('tool_call_id')
                if call_id:
                    if call_id in errors:
                        raise ValueError(f'Duplicate AgentErrorEvent at source entry {i}')
                    errors[call_id] = i
            elif kind == 'ActionEvent':
                actions.append((i, entry))
        action_ids = set()
        for i, entry in actions:
            if entry.get('tool_name') in ('think', 'finish'):
                continue  # Kept in trajectory, but not counted as external tool calls.
            action_id = entry.get('id')
            if not action_id or action_id in action_ids or i not in entry_turn:
                raise ValueError(f'Invalid or duplicate ActionEvent at source entry {i}')
            action_ids.add(action_id)
            result_entry = observations.get(action_id)
            if result_entry is None:
                result_entry = errors.get(entry.get('tool_call_id'))
            if result_entry is not None and result_entry <= i:
                raise ValueError(f'Observation precedes action at source entry {i}')
            tools.append(dict(tool_seq=len(tools) + 1, trajectory_entry=i,
                              result_entry=result_entry, decision_turn=entry_turn[i]))
        method, entry_base = OPENHANDS_METHOD, 0
    else:
        raise ValueError('Unsupported trajectory framework')
    missing = [row['tool_seq'] for row in tools if row['result_entry'] is None]
    if missing:
        warnings.append('Some tool calls have no matching feedback; result_entry remains null')
    if not entry_turn:
        raise ValueError('No recognized agent decisions; check --group and source format')
    return tools, method, {
        'framework': framework, 'trajectory_entry_base': entry_base,
        'json_pointer_array_base': 0, 'tool_count': len(tools),
        'observable_decision_turns': n, 'recorded_native_num_turns': raw.get('num_turns'),
        'native_num_turns_equals_decision_turns': raw.get('num_turns') == n,
        'missing_feedback_tool_seqs': missing, 'warnings': warnings,
    }


def build_payload(source, group, task=None, expected_source_sha256=None):
    source = Path(source).resolve()
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if expected_source_sha256 is not None and source_hash != expected_source_sha256:
        raise ValueError('Raw source hash does not match --expected-source-sha256')
    raw = json.loads(source_bytes)
    if not isinstance(raw, dict) or not isinstance(raw.get('trajectory'), list):
        raise ValueError('Expected an object containing the raw trajectory array')
    task = task or raw.get('db')
    if not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', task):
        raise ValueError('Provide a valid --task, or a raw result.json with a valid db field')
    agent, warehouse, framework = GROUPS[group]
    tools, method, mapping_report = build_turn_index(raw, framework)
    counts = {key: 0 for key in ('redacted_strings', 'removed_reasoning_blocks',
              'removed_reasoning_fields', 'removed_posthoc_fields', 'redacted_secret_fields')}
    trajectory = sanitize(raw['trajectory'], counts)
    counts['encoded_authorization_scrubs'] = 0
    trajectory = scrub_encoded_authorization(trajectory, counts)
    trajectory_id = f'{group}__{task}__{source_hash[:12]}'
    metadata = dict(trajectory_id=trajectory_id, task=task, agent=agent, warehouse=warehouse,
                    source_path=str(source), source_sha256=source_hash, run_id=trajectory_id)
    payload = {
        'metadata': metadata,
        'input_contract': {
            'scope': 'Exactly one complete selected raw /trajectory array; original entry indices preserved.',
            'source_sha256_verification': ('matched_before_sanitization' if expected_source_sha256
                                           else 'computed_before_sanitization'),
            'raw_trajectory_entry_count': len(raw['trajectory']),
            'included_trajectory_entry_count': len(trajectory),
            'task_requirements': 'Read user/task instructions inside this trajectory. No other files are needed.',
            'omissions': 'Only private reasoning, explicit post-hoc annotation fields, and secrets are omitted/redacted. Top-level source fields outside /trajectory are not supplied.',
            'redaction_version': 'v3',
        },
        'turn_index_method': method, 'turn_index': tools, 'trajectory': trajectory,
    }
    report = {
        **mapping_report, 'source_sha256': source_hash,
        'expected_source_sha256': expected_source_sha256,
        'raw_trajectory_entry_count': len(raw['trajectory']),
        'included_trajectory_entry_count': len(trajectory), 'sanitization': counts,
        'source_top_level_fields_not_copied': sorted(set(raw) - {'trajectory'}),
        'metadata_note': 'Task defaults to raw db; --group explicitly selects agent and warehouse.',
        'prior_annotations_used': False, 'model_calls': 0,
    }
    return payload, report


def prepare(source, group, output_dir, task=None, expected_source_sha256=None, compact=False):
    output_dir = Path(output_dir).resolve()
    payload, report = build_payload(source, group, task, expected_source_sha256)
    metadata = payload['metadata']
    trajectory_id = metadata['trajectory_id']
    dumps_options = {'separators': (',', ':')} if compact else {'indent': 2}
    data = (json.dumps(payload, ensure_ascii=False, allow_nan=False, **dumps_options) + '\n').encode('utf-8')
    payload_path = output_dir / 'inputs' / (trajectory_id + '.json')
    dependencies = {name: sha256(HERE / name) for name in
                    ('prepare_input.py', 'input_sanitization.py', 'redaction.py', 'sanitize_text.py')}
    item = {
        **metadata, 'group': group, 'cohort_id': 'standalone-raw-input-v1',
        'payload_path': str(payload_path.relative_to(output_dir)),
        'payload_sha256': hashlib.sha256(data).hexdigest(), 'payload_bytes': len(data),
        'trajectory_entries': len(payload['trajectory']), 'tool_count': len(payload['turn_index']),
        'sanitization': report['sanitization'], 'preparer_sha256': dependencies['prepare_input.py'],
        'preprocessing_dependencies_sha256': dependencies,
    }
    manifest = {'manifest_version': 'elt-flat8-raw-input-v1', 'analysis_mode': 'fresh_annotation',
                'prepared_trajectory_count': 1, 'trajectories': [item]}
    report.update(trajectory_id=trajectory_id, payload_sha256=item['payload_sha256'],
                  compact=compact, preprocessing_dependencies_sha256=dependencies)
    report_path = output_dir / 'preparation_reports' / (trajectory_id + '.json')
    manifest_path = output_dir / 'manifest.json'
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if old.get('manifest_version') != manifest['manifest_version']:
            raise ValueError('Use a separate output directory; existing manifest has a different protocol')
        merged = {row['trajectory_id']: row for row in old['trajectories']}
        if trajectory_id in merged and merged[trajectory_id] != item:
            raise ValueError('Existing manifest entry differs; use a new output directory')
        merged[trajectory_id] = item
        manifest['trajectories'] = sorted(merged.values(), key=lambda row: row['trajectory_id'])
        manifest['prepared_trajectory_count'] = len(merged)
    if payload_path.exists() and payload_path.read_bytes() != data:
        raise ValueError('Refusing to overwrite a different prepared input')
    if report_path.exists() and json.loads(report_path.read_text()) != report:
        raise ValueError('Refusing to overwrite a different preparation report')
    if sha256(source) != metadata['source_sha256']:
        raise ValueError('Raw source changed during preparation')
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    if not payload_path.exists():
        if compact:
            # Exclusive creation prevents accidental overwrites of existing payloads.
            with payload_path.open('xb') as stream:
                stream.write(data)
        else:
            atomic_json(payload_path, payload)
    atomic_json(report_path, report)
    atomic_json(manifest_path, manifest)
    return {'manifest': str(manifest_path), 'input': str(payload_path),
            'report': str(report_path), 'trajectory_entries': len(payload['trajectory']),
            'tool_count': len(payload['turn_index']),
            'observable_decision_turns': report['observable_decision_turns'], 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Original result.json')
    parser.add_argument('--group', required=True, choices=GROUPS)
    parser.add_argument('--task', help='Defaults to the raw db field')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--expected-source-sha256', help='Optional frozen source hash to verify')
    parser.add_argument('--compact', action='store_true', help='Remove JSON indentation only; never truncate content')
    args = parser.parse_args()
    try:
        result = prepare(args.source, args.group, args.output_dir, args.task,
                         args.expected_source_sha256, args.compact)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Preparation failed: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
