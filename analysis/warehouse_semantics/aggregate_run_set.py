#!/usr/bin/env python3
"""Combine independently validated, nonoverlapping tasks from frozen run snapshots.

Each source's own aggregate.py checks its original request, code, payload, output,
CLI completion and attempt provenance. This tool never invokes a model or changes
source runs. Use a new/empty output directory for every report to avoid stale data.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from aggregate import comparison, resolve_case_listings, summarize, write_csv
from protocol import atomic_json, load_manifest, load_payload, require, sha256
from run import selected_items, task_id_for_item

HERE = Path(__file__).resolve().parent
SNAPSHOT_FILES = ('aggregate.py', 'run.py', 'protocol.py', 'prompt.txt',
                  'taxonomy.json', 'single_task.output_schema.json')
SEMANTIC_FILES = tuple(name for name in SNAPSHOT_FILES if name != 'run.py')
REPORT_FILES = ('summary.json', 'coverage.json', 'sites.json', 'propagated_failures.json',
                'case_listings.json', 'table.csv', 'model_table.csv')


def snapshot_hashes(snapshot):
    return {name: sha256(snapshot / name) for name in SNAPSHOT_FILES}


def source_candidates(run_dir, selected_ids):
    """Orphans count as candidates too, so their invalid provenance stays visible."""
    found = {p.stem for folder in ('accepted_results', 'accepted_provenance')
             for p in (run_dir / folder).glob('*.json')}
    return sorted(found & selected_ids), sorted(found - selected_ids)


def validate_source(run_dir, manifest_path, target_ids, report_dir):
    snapshot = run_dir / 'protocol_snapshot'
    info = dict(run_dir=str(run_dir), protocol_snapshot=str(snapshot),
                selected_target_ids=target_ids, validation_report_dir=str(report_dir))
    report_dir.mkdir(parents=True)
    try:
        before = snapshot_hashes(snapshot)
        if not target_ids:
            info.update(status='no_candidates', protocol_hashes=before)
            return info, None
        command = [sys.executable, '-B', str(snapshot / 'aggregate.py'),
                   '--manifest', str(manifest_path), '--run-dir', str(run_dir),
                   '--output-dir', str(report_dir), '--allow-partial',
                   '--prompt', str(snapshot / 'prompt.txt'),
                   '--taxonomy', str(snapshot / 'taxonomy.json'),
                   '--schema', str(snapshot / 'single_task.output_schema.json')]
        for target_id in target_ids:
            command.extend(['--target-id', target_id])
        completed = subprocess.run(command, cwd=snapshot, text=True, capture_output=True,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        (report_dir / 'stdout.txt').write_text(completed.stdout)
        (report_dir / 'stderr.txt').write_text(completed.stderr)
        info.update(command=command, returncode=completed.returncode, protocol_hashes=before)
        require(before == snapshot_hashes(snapshot), 'Source protocol snapshot changed during validation')
        require(completed.returncode in (0, 2), 'Source snapshot aggregation failed; see its stdout/stderr')
        summary = json.loads((report_dir / 'summary.json').read_text())
        coverage = summary['coverage']
        require(sorted(t['target_id'] for t in coverage['targets']) == target_ids,
                'Source verification did not cover exactly its selected target IDs')
        require(coverage['selected_tasks'] == len(target_ids), 'Source selection count mismatch')
        accepted = {t['target_id'] for t in coverage['targets'] if t['status'] == 'accepted'}
        provenance = summary['provenance']
        require(len(provenance) == len(accepted) and {p['target_id'] for p in provenance} == accepted,
                'Source accepted provenance does not match verified coverage')
        info.update(status='validated', coverage=coverage,
                    verification_files_sha256={name: sha256(report_dir / name) for name in REPORT_FILES})
        return info, summary
    except (ValueError, KeyError, OSError, TypeError) as exc:
        info.update(status='invalid', error=str(exc))
        return info, None


def aggregate_run_set(args):
    manifest_path = args.manifest.resolve()
    manifest_hash = sha256(manifest_path)
    items = selected_items(load_manifest(manifest_path), args.target_id, None, args.task)
    require(len({task_id_for_item(i) for i in items}) == len(items),
            'Select one target per task to avoid double counting warehouse subsets')
    run_dirs = [p.resolve() for p in args.run_dir]
    require(len(set(run_dirs)) == len(run_dirs), 'Duplicate source run directory')
    require(all(p.is_dir() for p in run_dirs), 'A source run directory does not exist')
    output_dir = args.output_dir.resolve()
    require(not output_dir.exists() or not any(output_dir.iterdir()),
            'Output directory must be new or empty; preserve prior reports separately')
    require(all(output_dir != p and p not in output_dir.parents for p in run_dirs),
            'Write the combined report outside source run directories')
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_ids = {item['target_id'] for item in items}
    sources, verified = [], {}
    for index, run_dir in enumerate(run_dirs, 1):
        candidates, unselected = source_candidates(run_dir, selected_ids)
        info, child = validate_source(run_dir, manifest_path, candidates,
                                      output_dir / 'source_validation' / f'{index:02d}')
        info.update(source_id=f'source_{index:02d}', unselected_target_ids=unselected)
        sources.append(info)
        if child is not None:
            verified[info['source_id']] = child
    # Transport/runner variants are permitted; classification and aggregation
    # semantics must match, including the local functions used for the final sum.
    active_sources = [s for s in sources if s['status'] == 'validated']
    compatible = True
    if active_sources:
        baseline = active_sources[0]['protocol_hashes']
        compatible = all(all(s['protocol_hashes'][n] == baseline[n] for n in SEMANTIC_FILES)
                         for s in active_sources)
        compatible = compatible and baseline['aggregate.py'] == sha256(HERE / 'aggregate.py')
    coverage, records, provenance, payloads = [], [], [], {}
    input_models, accepted_models = set(), set()
    for item in items:
        target_id = item['target_id']
        entry = dict(target_id=target_id, task_id=task_id_for_item(item))
        owners = [s for s in sources if target_id in s['selected_target_ids']]
        entry['source_ids'] = [s['source_id'] for s in owners]
        try:
            payload = load_payload(item)
            members = {(m['warehouse'], payload['metadata']['task_id'], m['model_id']) for m in payload['models']}
            input_models.update(members)
            if not owners:
                entry['status'] = 'missing'
            elif len(owners) > 1:
                entry.update(status='overlap', error='Target is present in multiple source runs; no result was selected')
            elif owners[0]['status'] != 'validated':
                entry.update(status='invalid', error=owners[0].get('error', 'Source snapshot validation failed'))
            elif not compatible:
                entry.update(status='invalid', error='Source snapshots have incompatible semantic protocols')
            else:
                source = owners[0]
                child = verified[source['source_id']]
                status = next(t for t in child['coverage']['targets'] if t['target_id'] == target_id)
                entry.update({k: v for k, v in status.items() if k not in {'target_id', 'task_id'}})
                if status['status'] == 'accepted':
                    verified_record = next(p for p in child['provenance'] if p['target_id'] == target_id)
                    result_path = Path(source['run_dir']) / 'accepted_results' / (target_id + '.json')
                    raw = result_path.read_bytes()
                    require(hashlib.sha256(raw).hexdigest() == verified_record['output_sha256'],
                            'Accepted result changed after snapshot verification')
                    result = json.loads(raw)
                    require(result['metadata'] == payload['metadata'], 'Verified result/payload identity mismatch')
                    require(verified_record['context']['payload_sha256'] == item['payload_sha256'],
                            'Verified input differs from selected manifest')
                    records.append(result)
                    accepted_models.update(members)
                    payloads[target_id] = payload
                    provenance.append(dict(verified_record, source_id=source['source_id'],
                                           source_run_dir=source['run_dir']))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            entry.update(status='invalid', error=str(exc))
        coverage.append(entry)
    require(sha256(manifest_path) == manifest_hash, 'Manifest changed during aggregation')
    complete = compatible and all(t['status'] == 'accepted' and t['review_status'] == 'complete' for t in coverage)
    coverage_report = dict(selected_tasks=len(items), accepted_tasks=len(records),
                           all_selected_complete=complete, targets=coverage)
    run_set = dict(schema_version=1, manifest_path=str(manifest_path), manifest_sha256=manifest_hash,
                   aggregator_sha256=sha256(Path(__file__)),
                   compatible_semantic_protocol=compatible, sources=sources)
    atomic_json(output_dir / 'coverage.json', coverage_report)
    atomic_json(output_dir / 'run_set.json', run_set)
    if not complete and not args.allow_partial:
        raise ValueError('Missing, invalid, overlapping, or incomplete analyses. See coverage.json and run_set.json; use --allow-partial for explicit partial counts.')
    rows, sites = summarize(records)
    summary = dict(schema_version=1, analysis_mode='independent_task_analysis',
                   aggregation_mode='verified_run_set', coverage=coverage_report, rows=rows,
                   provenance=provenance, run_set=run_set,
                   prepared_model_warehouse_count=len(input_models),
                   accepted_model_warehouse_count=len(accepted_models),
                   counting_notes=['Each result was verified using its own frozen protocol snapshot.',
                                   'Tasks are unique across sources; overlaps are excluded, never resolved implicitly.',
                                   'Missing or invalid tasks are not zero-site tasks.',
                                   'Model membership is unique (task_id, model_id) within a warehouse and category.',
                                   'A model can contain multiple handling classes; C/I/U need not sum to total.',
                                   'F requires attributed whole-column repair; verified propagation adds only downstream F models.'])
    if args.reference_dir:
        warehouse_sets = {tuple(r['metadata']['warehouses']) for r in records}
        require(len(warehouse_sets) <= 1, 'Reference comparison requires consistent selected warehouses')
        summary['reference_comparison'] = comparison(rows, args.reference_dir,
            {r['metadata']['task_id'] for r in records}, set(next(iter(warehouse_sets), ())))
        atomic_json(output_dir / 'comparison.json', summary['reference_comparison'])
    counted = [s for s in sites if s['inclusion'] == 'counted']
    summary.update(counted_site_count=len(counted),
                   distinct_selected_models=len({(s['warehouse'], s['task_id'], s['model_id']) for s in counted}),
                   distinct_selected_warehouse_tasks=len({(s['warehouse'], s['task_id']) for s in counted}),
                   distinct_selected_tasks=len({s['task_id'] for s in counted}))
    atomic_json(output_dir / 'summary.json', summary)
    atomic_json(output_dir / 'sites.json', sites)
    atomic_json(output_dir / 'propagated_failures.json', [dict(f, task_id=r['metadata']['task_id'], target_id=r['metadata']['target_id']) for r in records for f in r.get('propagated_failures', [])])
    atomic_json(output_dir / 'case_listings.json', resolve_case_listings(records, payloads))
    write_csv(output_dir / 'table.csv', rows)
    with (output_dir / 'model_table.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['category_id', 'warehouse', 'total_models', 'correct_models', 'insufficient_models', 'unhandled_models', 'failed_models'])
        for row in rows:
            writer.writerow([row['category_id'], row['warehouse']] + row['model_counts'] + [row['counts'][4]])
    print(json.dumps(dict(accepted_tasks=len(records), selected_tasks=len(items),
                         all_selected_complete=complete, counted_sites=len(counted),
                         output_dir=str(output_dir),
                         reference_counts_match=summary.get('reference_comparison', {}).get('all_counts_match'))))
    return 0 if complete else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, action='append', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--task', action='append', default=[])
    parser.add_argument('--target-id', action='append', default=[])
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--reference-dir', type=Path)
    return aggregate_run_set(parser.parse_args(argv))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps(dict(status='aggregation_error', error=str(exc))))
        raise SystemExit(1)
