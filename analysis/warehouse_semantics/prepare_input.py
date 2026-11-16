#!/usr/bin/env python3
"""Prepare task-scoped, read-only evidence for warehouse semantic annotation.

No warehouse/model calls. Only factual artifacts are supplied: saved SQL, observed
schema/type feedback, task specifications, CSV samples and stored replay results.
Existing analyst site classifications and aggregate reports are never inputs.
"""
import argparse
import csv
from functools import lru_cache
import io
import json
import math
from pathlib import Path
import re
import sys

from protocol import (ANALYSIS_MODE, atomic_json, content_sha256, redact,
                      sha256, target_id_for, validate_payload)

HERE = Path(__file__).resolve().parent
DEFAULT_AUDIT = Path('/mydata/elt/ELT-Bench/evaluation/agent_results/_error_analysis/audit_xwh_silent_20261025')
DEFAULT_TRAJECTORIES = Path('/mydata/elt/campus_downloads/claude_opus47_sql_logs_revised_20261021')
DEFAULT_INPUTS = Path('/mydata/elt/ELT-Bench')
WAREHOUSES = {'sf': 'snowflake', 'db': 'databricks', 'rs': 'redshift'}
SHORT = {v: k for k, v in WAREHOUSES.items()}
INPUT_DIRS = {'snowflake': 'inputs', 'databricks': 'inputs_databricks', 'redshift': 'inputs_redshift'}
SCORE_FIELDS = {'status', 'match', 'matched', 'unmatched', 'missed', 'rule', 'error', 'error_type'}
PROBE_FIELDS = {'sql', 'columns', 'rows', 'results', 'error', 'error_type'}
TYPE_QUERY = re.compile(r'(?i)\b(?:describe|desc\s+table|typeof|pg_typeof|system\$typeof)\b|information_schema\.columns|\bdata_type\b|\bfull_data_type\b')
TYPE_OUTPUT = re.compile(r"(?i)(?:agate\.Row|\bcolumn_name\b|\bdata_type\b|\bfull_data_type\b|\bdecimal\(\d+,\d+\)|\bDecimal\('|\btype(?:of)?\s*[:=])")
FORBIDDEN_PROBE_NAME = re.compile(r'(?i)(?:sites|summary|report|review|classification|handling|attribution|complete_table|counts|manifest|scoring|inventory_check)')


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def json_safe(value):
    """Keep NaN/Inf distinct from SQL NULL when old JSON used nonstandard numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite_saved_value': str(value)}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


@lru_cache(maxsize=8192)
def file_hash(path):
    return sha256(Path(path))


def score_facts(value):
    return json_safe({k: v for k, v in value.items() if k in SCORE_FIELDS}) if isinstance(value, dict) else {}


def content_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(content_text(x.get('text', '')) for x in value if isinstance(x, dict) and x.get('type') == 'text')
    return ''


def warehouse_for(path, record=None):
    if isinstance(record, dict):
        w = record.get('warehouse')
        if w in WAREHOUSES:
            return WAREHOUSES[w]
        if w in SHORT:
            return w
    path = Path(path)
    # This cross-warehouse probe is stored under sf/, but its saved producer
    # explicitly uses connect('db'); the filesystem parent is not the backend.
    if path.name == 'peer_db_apple_probe.json' and path.parent.name == 'sf':
        producer = path.parent / 'peer_db_probe.py'
        if not producer.is_file() or "connect('db')" not in producer.read_text():
            raise ValueError('Cross-warehouse probe producer cannot be verified: ' + str(path))
        return 'databricks'
    for part in reversed(path.parts):
        if part in WAREHOUSES:
            return WAREHOUSES[part]
        match = re.match(r'^(sf|db|rs)(?:_|\.)', part)
        if match:
            return WAREHOUSES[match.group(1)]
    return None


def json_pointer_part(part):
    return str(part).replace('~', '~0').replace('/', '~1')


class EvidenceBuilder:
    def __init__(self, task, warehouses, args):
        self.task = task
        self.warehouses = warehouses
        self.args = args
        self.artifacts = []
        self.models = []
        self.omissions = []
        self.used = {}
        self.identity = {}
        self.limits = {
            'trajectory_type_schema': args.trace_evidence_characters,
            'task_specification': args.task_spec_characters,
            'stored_probe': args.probe_evidence_characters,
            'source_description': args.source_description_characters,
        }
        self.limitations = [
            'This is offline extraction of the revised_20261021 saved snapshot and existing analyst replay records; no SQL, warehouse query, or model inference was executed during preparation.',
            'Replay discovery is retrospective and selective. A discovered replay is not an independent reexecution or evidence of exhaustive challenge coverage; absence of replay is not proof of no challenge.',
            'Saved final SQL may postdate trajectory actions. Historical trajectory excerpts and later analyst replay evidence have separate artifact kinds.',
            'Evaluator match/unmatched/fixed_columns are stored comparison facts, not warehouse-specific causal labels. Model mismatch alone does not establish a warehouse semantic cause.',
            'No previous site classifications, handling labels, expected counts, or narrative audit reports are included. SQL intervention filenames identify stored files; they do not certify a diagnosis.',
            'CSV evidence contains deterministic first-row samples with full row counts, not complete output datasets unless explicitly marked complete. No missing sample establishes absence of a value.',
            'Trace extraction includes returned task-specification and schema/type feedback only, not a complete trajectory review. Private reasoning and agent narrative are not included.',
            'Current input-folder schema descriptions are supplemental source documentation and may differ from the historical snapshot. Historical task requirements are extracted from tool feedback in the selected trajectory.',
        ]

    def omit(self, reason, path, **details):
        self.omissions.append({'reason': reason, 'source_path': str(path), **details})

    def add(self, kind, warehouse, model, path, content, complete=True, selector='', budget=None):
        path = Path(path).resolve()
        if not path.is_file():
            self.omit('source_file_missing', path, kind=kind)
            return None
        clean = redact(content)
        # Bound entire evidence units, never cut an SQL expression or CSV cell.
        if budget:
            used = self.used.get(budget, 0)
            if used + len(clean) > self.limits[budget]:
                self.omit('declared_evidence_budget', path, kind=kind, selector=selector,
                          excluded_characters=len(clean), budget=budget,
                          limit_characters=self.limits[budget])
                return None
            self.used[budget] = used + len(clean)
        digest = content_sha256(clean)
        key = (kind, warehouse, model, str(path), selector, digest)
        if key in self.identity:
            return self.identity[key]
        aid = 'a_' + content_sha256(json.dumps(key, ensure_ascii=False))[:20]
        artifact = dict(artifact_id=aid, kind=kind, warehouse=warehouse, model_id=model,
                        content=clean, line_count=len(clean.splitlines()), source_path=str(path),
                        source_sha256=file_hash(str(path)), sha256=digest, complete=complete)
        self.artifacts.append(artifact)
        self.identity[key] = aid
        return aid

    def file(self, kind, warehouse, model, path, **kwargs):
        path = Path(path)
        if not path.is_file():
            self.omit('source_file_missing', path, kind=kind)
            return None
        return self.add(kind, warehouse, model, path, path.read_text(errors='replace'), **kwargs)

    def csv_sample(self, kind, warehouse, model, path):
        path = Path(path)
        if not path.is_file():
            self.omit('csv_missing', path, kind=kind)
            return None
        sample = sample_csv(str(path.resolve()), self.args.csv_sample_rows, self.args.csv_sample_characters)
        if sample['omitted_rows']:
            self.omit('deterministic_csv_sample', path, kind=kind,
                      total_rows=sample['row_count'], included_rows=len(sample['rows']),
                      omitted_rows=sample['omitted_rows'])
        return self.add(kind, warehouse, model, path, json_text(sample),
                        complete=sample['omitted_rows'] == 0, selector='first_rows')


@lru_cache(maxsize=4096)
def sample_csv(path, max_rows, max_chars):
    rows, row_count, used = [], 0, 0
    with Path(path).open(newline='', errors='replace') as handle:
        reader = csv.reader(handle)
        columns = next(reader, [])
        for row in reader:
            row_count += 1
            if row_count <= max_rows:
                size = len(json.dumps(row, ensure_ascii=False))
                if used + size <= max_chars:
                    rows.append(row)
                    used += size
    return {'sampling': 'first rows in stored file order; complete cells; no inferred types',
            'limits': {'max_rows': max_rows, 'max_sample_value_characters': max_chars},
            'columns': columns, 'rows': rows, 'row_count': row_count,
            'omitted_rows': row_count - len(rows), 'values_are_stored_csv_text': True}


def trajectory_path(row, warehouse, task, args):
    # Prefer the exact bundle associated with the source SQL inventory record.
    for value in row.get('source_sql', []):
        p = Path(value)
        for parent in p.parents:
            if parent.name == task and parent.parent.name == 'datasets':
                candidate = parent / 'claude' / 'result.json'
                if candidate.is_file():
                    return candidate
    return args.trajectory_root / warehouse / 'datasets' / task / 'claude' / 'result.json'


def extract_trajectory(builder, path, warehouse):
    if not path.is_file():
        builder.omit('trajectory_missing', path, warehouse=warehouse)
        return
    data = json.loads(path.read_text())
    trajectory = data.get('trajectory', [])
    calls = {}
    extracted_specs = 0
    for index, entry in enumerate(trajectory):
        if not isinstance(entry, dict) or not isinstance(entry.get('content'), list):
            continue
        for block_index, block in enumerate(entry['content']):
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use':
                calls[block.get('id')] = (index, block_index, block)
                continue
            if block.get('type') != 'tool_result' or block.get('tool_use_id') not in calls:
                continue
            call_index, call_block_index, call = calls[block['tool_use_id']]
            tool = call.get('name', '')
            args = call.get('input', {})
            command = str(args.get('command', ''))
            file_path = str(args.get('file_path', args.get('path', '')))
            text = content_text(block.get('content', ''))
            if not text.strip() or block.get('is_error'):
                continue
            pointer = f'/trajectory/{index}/content/{block_index}/content'
            header = ('Historical tool result excerpt. Source JSON pointer: ' + pointer + '\n'
                      + f'Paired action: /trajectory/{call_index}/content/{call_block_index}; tool={tool}\n')
            read_spec = tool.lower() in {'read', 'read_file'} and file_path.endswith('/data_model.yaml')
            cat_spec = ('bash' in tool.lower() and 'data_model.yaml' in command
                        and re.search(r'\b(?:cat|sed|head|tail)\b', command)
                        and not re.search(r'config\.yaml|credential|\.env|profiles\.yml', command, re.I))
            if (read_spec or cat_spec) and re.search(r'(?:^|\n)(?:\d+\s+)?models\s*:|\bdescription\s*:', text):
                if builder.add('task_specification', warehouse, None, path, header + text,
                               complete=False, selector=pointer, budget='task_specification'):
                    extracted_specs += 1
                continue
            # Keep returned native type descriptions and the executed query where
            # the recorded action explicitly describes types. Never include Write/Edit
            # bodies or assistant reasoning as if they were warehouse observations.
            if 'bash' in tool.lower() and (TYPE_QUERY.search(command) or TYPE_OUTPUT.search(text)):
                if not TYPE_OUTPUT.search(text) and not TYPE_QUERY.search(command):
                    continue
                query_header = ''
                if TYPE_QUERY.search(command) and not re.search(r'password|secret|credential|token|Authorization', command, re.I):
                    query_header = 'Recorded command (not executed by preparer):\n' + command + '\nReturned feedback:\n'
                builder.add('trajectory_type_schema', warehouse, None, path, header + query_header + text,
                            complete=False, selector=pointer, budget='trajectory_type_schema')
    if not extracted_specs:
        builder.omit('historical_task_specification_not_extracted', path, warehouse=warehouse)


def supplemental_descriptions(builder):
    for warehouse in builder.warehouses:
        folder = builder.args.inputs_root / INPUT_DIRS[warehouse] / builder.task / 'schemas'
        if not folder.is_dir():
            builder.omit('supplemental_schema_directory_missing', folder, warehouse=warehouse)
            continue
        for path in sorted(folder.glob('*.csv')):
            prefix = ('Supplemental current input-folder source description; not a historical native warehouse type observation.\n'
                      'Source schema file: ' + path.name + '\n')
            builder.add('source_description', warehouse, None, path, prefix + path.read_text(errors='replace'),
                        complete=True, budget='source_description')


def inventory_sql(builder, row):
    warehouse = WAREHOUSES[row['warehouse']]
    model = row['model']
    sql_ids = []
    for path in row.get('source_sql', []):
        aid = builder.file('final_sql', warehouse, model, path)
        if aid:
            sql_ids.append(aid)
    for path in row.get('compiled_sql', []):
        builder.file('compiled_sql', warehouse, model, path)
    actual = row.get('actual_csv')
    baseline = score_facts(row.get('score', {}))
    for key in ('actual_rows', 'gt_rows'):
        if key in row:
            baseline[key] = row[key]
    builder.models.append(dict(warehouse=warehouse, model_id=model,
                               sql_artifact_id=sql_ids[0] if sql_ids else None,
                               actual_available=bool(actual and Path(actual).is_file()), baseline_score=baseline))
    if actual:
        builder.csv_sample('evaluated_output_sample', warehouse, model, actual)
    if row.get('gt_csv'):
        builder.csv_sample('reference_output_sample', warehouse, model, row['gt_csv'])


def add_upstream_sql(builder, rows):
    evaluated = {(WAREHOUSES[r['warehouse']], Path(p).resolve())
                 for r in rows for p in r.get('source_sql', [])}
    # Resolve only literal dbt refs reachable from evaluated source SQL.
    for warehouse in builder.warehouses:
        model_files = {}
        todo = []
        for row in rows:
            if WAREHOUSES[row['warehouse']] != warehouse:
                continue
            for path_value in row.get('source_sql', []):
                path = Path(path_value)
                if not path.is_file():
                    continue
                todo.append(path)
                parent = next((x for x in path.parents if x.name == 'models'), None)
                if parent:
                    for q in sorted(parent.rglob('*.sql')):
                        model_files.setdefault(q.stem, q)
        visited = set()
        while todo:
            path = todo.pop()
            if path.resolve() in visited:
                continue
            visited.add(path.resolve())
            text = path.read_text(errors='replace')
            for ref in re.findall(r"\bref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
                dep = model_files.get(ref)
                if dep is None:
                    builder.omit('literal_ref_dependency_not_found', path, warehouse=warehouse, ref=ref)
                    continue
                if (warehouse, dep.resolve()) not in evaluated:
                    # Non-evaluated upstream SQL is task evidence, not a new output model.
                    builder.file('upstream_sql', warehouse, None, dep)
                todo.append(dep)


def replay_index(audit_root):
    found = {}
    for path in sorted(audit_root.rglob('results.json')):
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in ('warehouse', 'task', 'model')):
            continue
        warehouse = warehouse_for(path, data)
        if warehouse and path.parent.name == data['task'] + '__' + data['model']:
            found.setdefault((warehouse, data['task'], data['model']), []).append((path, data))
    # Some later interventions reference an existing baseline instead of writing
    # another task__model/results.json (e.g. donor_arithmetic_result.json).
    # Follow this explicit saved linkage; never infer identity from a filename.
    for path in sorted(audit_root.rglob('*result*.json')):
        if path.name == 'results.json':
            continue
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get('baseline_reference'), str) or not isinstance(data.get('mutation_sql'), str):
            continue
        baseline_path = Path(data['baseline_reference']).resolve()
        mutation_path = Path(data['mutation_sql']).resolve()
        if not baseline_path.is_relative_to(audit_root) or not mutation_path.is_relative_to(audit_root):
            raise ValueError('Standalone replay links outside audit root: ' + str(path))
        if not baseline_path.is_file():
            raise ValueError('Standalone replay baseline missing: ' + str(path))
        baseline = json.loads(baseline_path.read_text())
        if not all(isinstance(baseline.get(k), str) for k in ('warehouse', 'task', 'model')):
            raise ValueError('Standalone replay baseline has no explicit task identity: ' + str(path))
        identity = baseline['task'] + '__' + baseline['model']
        if baseline_path.parent.name != identity or mutation_path.parent != baseline_path.parent:
            raise ValueError('Standalone replay links do not share task/model directory: ' + str(path))
        warehouse = warehouse_for(baseline_path, baseline)
        if warehouse:
            normalized = dict(data, warehouse=baseline['warehouse'], task=baseline['task'], model=baseline['model'],
                              _replay_directory=str(mutation_path.parent))
            found.setdefault((warehouse, baseline['task'], baseline['model']), []).append((path, normalized))
    return found


def add_replays(builder, row, replays):
    warehouse = WAREHOUSES[row['warehouse']]
    model = row['model']
    for path, data in replays.get((warehouse, builder.task, model), []):
        folder = Path(data.get('_replay_directory', str(path.parent)))
        sql_refs = {}
        csv_refs = {}
        # Include exact baseline and mutation SQL only from this explicitly
        # identified task/model directory; do not import intervention scripts.
        for name in ['baseline'] + sorted(data.get('mutations', {})):
            sql = folder / (name + '.sql')
            if sql.is_file():
                sql_refs[name] = builder.file('replay_sql', warehouse, model, sql)
            else:
                builder.omit('recorded_replay_sql_missing', sql, warehouse=warehouse, model_id=model)
        for name in ['baseline'] + sorted(data.get('mutations', {})):
            csv = folder / (name + '.csv')
            if csv.is_file():
                csv_refs[name] = builder.csv_sample('replay_output_sample', warehouse, model, csv)
        facts = {'provenance': 'Previously stored analyst replay; not historical agent repair and not rerun by this preparer',
                 'warehouse': warehouse, 'task': builder.task, 'model': model,
                 'baseline_matches_actual': score_facts(data.get('baseline_matches_actual', {})),
                 'baseline_score': score_facts(data.get('baseline_score', {})),
                 'sql_artifacts': sql_refs, 'csv_sample_artifacts': csv_refs, 'mutations': {}}
        for name, result in sorted(data.get('mutations', {}).items()):
            if not isinstance(result, dict):
                continue
            record = {}
            if isinstance(result.get('score'), dict):
                record['score'] = score_facts(result['score'])
            for key in ('fixed_columns', 'newly_failed_columns', 'error', 'error_type'):
                if key in result:
                    record[key] = json_safe(result[key])
            record['saved_sql_artifact_id'] = sql_refs.get(name)
            record['saved_csv_sample_artifact_id'] = csv_refs.get(name)
            facts['mutations'][name] = record
        if isinstance(data.get('baseline_reference'), str):
            facts['baseline_reference_path'] = data['baseline_reference']
            facts['baseline_reference_sha256'] = file_hash(str(Path(data['baseline_reference']).resolve()))
        if isinstance(data.get('source_sha256'), str):
            facts['recorded_source_sql_sha256'] = data['source_sha256']
        builder.add('replay_results', warehouse, model, path, json_text(facts), complete=False,
                    selector='whitelisted_execution_and_column_comparison_fields')


def probe_index(audit_root, tasks, inventory=None):
    """Extract query/result units only; never send a whole multi-task probe file."""
    indexed = {}
    schemas = set(tasks)
    source_identities = {}
    for row in inventory or []:
        identity_key = (WAREHOUSES[row['warehouse']], row['task'], row['model'])
        for field in ('source_sql', 'compiled_sql'):
            for value in row.get(field, []):
                source_identities.setdefault(str(Path(value).resolve()), set()).add(identity_key)
    task_pattern = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(t) for t in sorted(tasks, key=len, reverse=True)) + r')\s*\.', re.I)

    def identity(node, inherited):
        # Some raw execution records put task identity in an `original` object
        # alongside prior interpretations. Read only these three identity
        # fields; never copy that object or its analysis into the input.
        context = dict(inherited)
        sources = [node]
        if isinstance(node.get('original'), dict):
            sources.insert(0, node['original'])
        for source in sources:
            warehouse = source.get('warehouse')
            if warehouse in WAREHOUSES:
                context['warehouse'] = WAREHOUSES[warehouse]
            elif warehouse in SHORT:
                context['warehouse'] = warehouse
            task = source.get('task') or source.get('task_id')
            if task in schemas:
                if task != context.get('task'):
                    context.pop('model', None)
                context['task'] = task
            model = source.get('model') or source.get('model_id')
            if isinstance(model, str):
                context['model'] = model
        # When a saved record links exact evaluated SQL files, these inventory
        # paths provide stronger identity than older analyst metadata.
        linked = set()
        for field in ('source_sql', 'compiled_sql'):
            values = node.get(field, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str):
                        linked.update(source_identities.get(str(Path(value).resolve()), set()))
        if len(linked) == 1:
            context['warehouse'], context['task'], context['model'] = next(iter(linked))
        elif len(linked) > 1:
            context['_identity_conflict'] = True
        return context

    def index_unit(node, pointer, path, context, result_pointer=None):
        warehouse = context.get('warehouse') or warehouse_for(path)
        if not warehouse or context.get('_identity_conflict'):
            return
        raw_sql = node['sql']
        mentioned = set(x.lower() for x in task_pattern.findall(raw_sql.replace('`', '').replace('"', '')))
        mentioned.update(x.lower() for x in re.findall(r"(?i)\btable_schema\s*=\s*'([^']+)'", raw_sql) if x.lower() in schemas)
        explicit = context.get('task')
        # Do not route a multi-task or conflicting query into one task using
        # an ancestor's label. Exact SQL task references must agree.
        if explicit and mentioned and mentioned != {explicit}:
            return
        if explicit:
            mentioned.add(explicit)
        row_key = next((k for k in ('rows', 'results') if isinstance(node.get(k), list)), None)
        scoped = {}
        if row_key and any(isinstance(r, dict) and any(k.lower() == 'table_schema' for k in r) for r in node[row_key]):
            for record in node[row_key]:
                if not isinstance(record, dict):
                    continue
                table_schema = next((v for k, v in record.items() if k.lower() == 'table_schema'), None)
                if table_schema in schemas:
                    scoped.setdefault(table_schema, []).append(record)
            for task, records in scoped.items():
                factual = {k: node[k] for k in ('sql', 'columns') if k in node}
                factual[row_key] = records
                factual['task_filter'] = 'Only rows whose table_schema equals ' + task + '; other tasks excluded'
                if result_pointer:
                    factual['result_source_json_pointer'] = result_pointer
                indexed.setdefault((warehouse, task), []).append((path, pointer, factual))
        elif len(mentioned) == 1:
            task = next(iter(mentioned))
            factual = {k: v for k, v in node.items() if k in PROBE_FIELDS}
            if result_pointer:
                factual['result_source_json_pointer'] = result_pointer
            if explicit == task and context.get('model'):
                factual['task_id'] = task
                factual['model_id'] = context['model']
            indexed.setdefault((warehouse, task), []).append((path, pointer, factual))

    def visit(node, pointer, path, inherited):
        if isinstance(node, list):
            for i, value in enumerate(node):
                visit(value, pointer + '/' + str(i), path, inherited)
            return
        if not isinstance(node, dict):
            return
        context = identity(node, inherited)
        if isinstance(node.get('sql'), str) and any(k in node for k in ('rows', 'results', 'error')):
            index_unit(node, pointer, path, context)
            return
        # A second saved execution format stores SQL and returned rows in
        # parallel dictionaries. Pair only equal keys with actual feedback;
        # never infer a result for an unexecuted or unmatched SQL entry.
        if isinstance(node.get('queries'), dict) and isinstance(node.get('results'), dict):
            for key, sql in node['queries'].items():
                if not isinstance(sql, str) or key not in node['results']:
                    continue
                query_pointer = pointer + '/queries/' + json_pointer_part(key)
                result_pointer = pointer + '/results/' + json_pointer_part(key)
                index_unit({'sql': sql, 'results': node['results'][key]},
                           query_pointer, path, context, result_pointer)
        for key, value in node.items():
            # Recurse only to locate raw sql+result units. Interpretation fields
            # never survive the explicit whitelist above.
            if isinstance(value, (dict, list)):
                if key != 'original':
                    visit(value, pointer + '/' + json_pointer_part(key), path, context)
    for path in sorted(audit_root.rglob('*.json')):
        raw_count_query_file = path.name in {'trigger_counts.json', 'asana_id_counts.json'}
        if path.name == 'results.json' or (FORBIDDEN_PROBE_NAME.search(path.name) and not raw_count_query_file):
            continue
        rel = str(path.relative_to(audit_root)).lower()
        explicit_raw_query_file = (path.name.endswith('_results.json')
                                   or path.name in {'phase2_live_check.json', 'phase2_movie_duration_branches.json'})
        if not explicit_raw_query_file and not any(word in rel for word in ('probe', 'describe', 'type_matrix', 'source_types', 'schema', 'trigger', 'id_counts')):
            continue
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        visit(data, '', path, {'warehouse': warehouse_for(path)})
    return indexed


def add_probes(builder, probes):
    evaluated_models = {(m['warehouse'], m['model_id']) for m in builder.models}
    for warehouse in builder.warehouses:
        for path, pointer, data in probes.get((warehouse, builder.task), []):
            facts = {'provenance': 'Stored analyst query feedback; not executed during preparation',
                     'source_json_pointer': pointer or '/', **json_safe(data)}
            if path.name == 'peer_db_apple_probe.json' and path.parent.name == 'sf':
                producer = path.parent / 'peer_db_probe.py'
                facts['warehouse_attribution'] = {'method': "Saved producer explicitly calls connect('db'); storage folder sf is not the backend",
                                                  'producer_path': str(producer), 'producer_sha256': file_hash(str(producer))}
            # Preserve deterministic samples and disclose sample count; retain
            # all type-schema rows when they fit the same declared budget.
            for key in ('rows', 'results'):
                if isinstance(facts.get(key), list):
                    n = len(facts[key])
                    limit = builder.args.probe_sample_rows
                    if 'task_filter' in facts:
                        limit = builder.args.schema_sample_rows
                    if n > limit:
                        facts[key] = facts[key][:limit]
                        facts[key + '_sampling'] = {'stored_rows': n, 'included_rows': limit,
                                                   'omitted_rows': n - limit, 'method': 'first rows in saved record order'}
                        builder.omit('stored_probe_row_sample', path, selector=pointer,
                                     stored_rows=n, included_rows=limit, omitted_rows=n - limit)
            model = facts.get('model_id')
            if (warehouse, model) not in evaluated_models:
                model = None
                facts.pop('model_id', None)
            builder.add('stored_query_feedback', warehouse, model, path, json_text(facts),
                        complete=False, selector=pointer, budget='stored_probe')



def add_evaluator_context(builder):
    path = builder.args.inputs_root / 'evaluation' / 'eva_stage2.py'
    if not path.is_file():
        builder.omit('local_typed_scorer_source_missing', path)
        return
    text = path.read_text()
    start = text.find('def _to_numeric_if_possible(')
    end = text.find('\n# --------------------------------------------------------------------------', text.find('def check_corretness(', start))
    if start < 0 or end < 0:
        builder.omit('local_typed_scorer_functions_not_located', path)
        return
    first_line = text[:start].count('\n') + 1
    excerpt = ('Local scorer implementation supplied as comparison context; not executed by this preparer. '
               'Stored replay scores are full-column results and cannot be recalculated from the CSV samples. '
               'This code snapshot is not proof of its historical identity at every earlier scoring run.\n'
               + f'Original source starting line: {first_line}\n' + text[start:end])
    builder.add('evaluator_contract', None, None, path, excerpt, complete=False, selector=f'line:{first_line}')


def prepare_task(task, rows, replays, probes, args):
    warehouses = [w for w in WAREHOUSES.values() if w in args.warehouses]
    builder = EvidenceBuilder(task, warehouses, args)
    rows = sorted((r for r in rows if r['task'] == task and WAREHOUSES[r['warehouse']] in warehouses),
                  key=lambda r: (warehouses.index(WAREHOUSES[r['warehouse']]), r['model']))
    if not rows:
        raise ValueError('No selected scoring inventory rows for ' + task)
    seen = set()
    for row in rows:
        key = (row['warehouse'], row['model'])
        if key in seen:
            raise ValueError('Duplicate task/warehouse/model scoring inventory entry: ' + str(key))
        seen.add(key)
        inventory_sql(builder, row)
    add_upstream_sql(builder, rows)
    add_evaluator_context(builder)
    for warehouse in warehouses:
        row = next((r for r in rows if WAREHOUSES[r['warehouse']] == warehouse), None)
        if row:
            extract_trajectory(builder, trajectory_path(row, warehouse, task, args), warehouse)
        else:
            builder.limitations.append('No evaluated model rows available for warehouse ' + warehouse)
    supplemental_descriptions(builder)
    add_probes(builder, probes)
    for row in rows:
        add_replays(builder, row, replays)
    metadata = dict(task_id=task, agent='Claude Opus 4.7', snapshot_id='revised_20261021', warehouses=warehouses)
    metadata['target_id'] = target_id_for(metadata)
    builder.limitations.append('Declared evidence limits: ' + json.dumps(builder.limits, sort_keys=True)
                              + f'; CSV first {args.csv_sample_rows} rows, at most {args.csv_sample_characters} value characters/file;'
                              + f' probe first {args.probe_sample_rows} rows or {args.schema_sample_rows} task-filtered schema rows.')
    # The complete omission inventory is also embedded, so workers can never
    # mistake a declared budget omission for an absent phenomenon.
    for omission in builder.omissions:
        builder.limitations.append('Evidence omission: ' + json.dumps(omission, ensure_ascii=False, sort_keys=True))
    payload = dict(schema_version=1, analysis_mode=ANALYSIS_MODE, metadata=metadata,
                   models=builder.models, artifacts=builder.artifacts, limitations=builder.limitations)
    validate_payload(payload)
    rendered = json_text(payload) + '\n'
    report = dict(task_id=task, target_id=metadata['target_id'], model_count=len(builder.models),
                  artifact_count=len(builder.artifacts), payload_characters=len(rendered),
                  evidence_limits=builder.limits, evidence_characters_used=builder.used,
                  omissions=builder.omissions, model_calls=0, warehouse_calls=0,
                  audit_root=str(args.audit_root.resolve()),
                  scoring_inventory_sha256=file_hash(str((args.audit_root / 'scoring_inventory.json').resolve())))
    if len(rendered) > args.max_payload_characters:
        report.update(status='failed_payload_budget', max_payload_characters=args.max_payload_characters)
        atomic_json(args.output_dir / 'preparation_reports' / (metadata['target_id'] + '.json'), report)
        raise ValueError(f'{task}: payload has {len(rendered)} characters, exceeding declared limit {args.max_payload_characters}; no payload written. Increase --max-payload-characters explicitly.')
    path = args.output_dir / 'inputs' / (metadata['target_id'] + '.json')
    if path.exists() and path.read_text() != rendered:
        raise ValueError('Refusing to overwrite a different prepared input: ' + str(path))
    atomic_json(path, payload)
    report['status'] = 'prepared'
    report['payload_sha256'] = sha256(path)
    atomic_json(args.output_dir / 'preparation_reports' / (metadata['target_id'] + '.json'), report)
    return dict(target_id=metadata['target_id'], task_id=task,
                payload_path=str(path.relative_to(args.output_dir)),
                payload_sha256=sha256(path), preparer_sha256=sha256(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-root', type=Path, default=DEFAULT_AUDIT)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--task', action='append', help='Repeat for multiple task IDs')
    selection.add_argument('--all', action='store_true', help='All task IDs in scoring_inventory.json')
    parser.add_argument('--warehouses', nargs='+', choices=list(WAREHOUSES.values()), default=list(WAREHOUSES.values()))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--trajectory-root', type=Path, default=DEFAULT_TRAJECTORIES)
    parser.add_argument('--inputs-root', type=Path, default=DEFAULT_INPUTS)
    parser.add_argument('--max-payload-characters', type=int, default=1048576)
    parser.add_argument('--trace-evidence-characters', type=int, default=100000)
    parser.add_argument('--task-spec-characters', type=int, default=150000)
    parser.add_argument('--probe-evidence-characters', type=int, default=100000)
    parser.add_argument('--source-description-characters', type=int, default=60000)
    parser.add_argument('--csv-sample-rows', type=int, default=5)
    parser.add_argument('--csv-sample-characters', type=int, default=12000)
    parser.add_argument('--probe-sample-rows', type=int, default=20)
    parser.add_argument('--schema-sample-rows', type=int, default=200)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, int) and not isinstance(value, bool) and value < 1:
            parser.error('--' + key.replace('_', '-') + ' must be positive')
    args.audit_root = args.audit_root.resolve()
    args.output_dir = args.output_dir.resolve()
    args.warehouses = [w for w in WAREHOUSES.values() if w in args.warehouses]
    inventory = json.loads((args.audit_root / 'scoring_inventory.json').read_text())
    if not isinstance(inventory, list):
        raise ValueError('scoring_inventory.json must contain a list')
    for row in inventory:
        if row.get('warehouse') not in WAREHOUSES or not all(isinstance(row.get(k), str) for k in ('task', 'model')):
            raise ValueError('Invalid scoring inventory identity')
    known_tasks = sorted({r['task'] for r in inventory})
    selected = known_tasks if args.all else sorted(set(args.task))
    if any(t not in known_tasks for t in selected):
        parser.error('Unknown task(s): ' + ', '.join(t for t in selected if t not in known_tasks))
    replays = replay_index(args.audit_root)
    probes = probe_index(args.audit_root, known_tasks, inventory)
    manifest_path = args.output_dir / 'manifest.json'
    manifest = dict(schema_version=1, analysis_mode=ANALYSIS_MODE, targets=[])
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if old.get('schema_version') != 1 or old.get('analysis_mode') != ANALYSIS_MODE:
            raise ValueError('Existing output manifest uses another protocol')
        manifest = old
    entries = {r['target_id']: r for r in manifest['targets']}
    failures = []
    for task in selected:
        try:
            item = prepare_task(task, inventory, replays, probes, args)
            if item['target_id'] in entries and entries[item['target_id']] != item:
                raise ValueError('Existing manifest entry differs; use a new output directory')
            entries[item['target_id']] = item
            manifest['targets'] = sorted(entries.values(), key=lambda r: (r['task_id'], r['target_id']))
            atomic_json(manifest_path, manifest)
            print(json.dumps({'task_id': task, 'status': 'prepared', 'target_id': item['target_id']}), flush=True)
        except Exception as exc:
            failure = {'task_id': task, 'status': 'failed', 'error': redact(str(exc))}
            failures.append(failure)
            print(json.dumps(failure), flush=True)
    summary = {'selected_tasks': len(selected), 'prepared_this_invocation': len(selected) - len(failures),
               'manifest_targets': len(entries), 'failures': failures, 'model_calls': 0, 'warehouse_calls': 0,
               'manifest_path': str(manifest_path)}
    atomic_json(args.output_dir / 'preparation_summary.json', summary)
    print(json.dumps(summary), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
