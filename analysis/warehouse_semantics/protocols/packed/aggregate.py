#!/usr/bin/env python3
"""Aggregate validated, independently analyzed tasks; compare frozen references afterward."""
import argparse
import csv
import json
from pathlib import Path

from protocol import CATEGORIES, WAREHOUSES, atomic_json, load_manifest, load_payload, require, sha256
from run import (HERE, build_request, context_for, protocol_fingerprints, read_accepted,
                 selected_items, task_id_for_item)

CATEGORY_ORDER = ['numeric_identifier', 'null_ordering', 'integer_avg', 'division_precision', 'time_units', 'trailing_spaces']
WAREHOUSE_ORDER = ['snowflake', 'databricks', 'redshift']
HANDLINGS = ['correct', 'insufficient', 'unhandled']


def summarize(results):
    """Count sites; deduplicate model and task membership independently of sites."""
    rows, sites = [], []
    for category in CATEGORY_ORDER:
        for warehouse in WAREHOUSE_ORDER:
            selected = []
            for result in results:
                for site in result['sites']:
                    if site['category'] == category and site['warehouse'] == warehouse:
                        selected.append(dict(site, task_id=result['metadata']['task_id'], target_id=result['metadata']['target_id']))
            counted = [s for s in selected if s['inclusion'] == 'counted']
            models = {k: set() for k in ['total'] + HANDLINGS}
            tasks = {k: set() for k in ['total'] + HANDLINGS}
            failed = set()
            for site in counted:
                key = (site['task_id'], site['model_id'])
                models['total'].add(key); models[site['handling']].add(key)
                tasks['total'].add(site['task_id']); tasks[site['handling']].add(site['task_id'])
                if site['failure_attributed']: failed.add(key)
            for result in results:
                for failure in result.get('propagated_failures', []):
                    if failure['category'] == category and failure['warehouse'] == warehouse:
                        failed.add((result['metadata']['task_id'], failure['model_id']))
            def members(values):
                return [dict(task_id=t, model_id=m) for t, m in sorted(values)]
            rows.append(dict(category_id=category, warehouse=warehouse,
                counts=[len(counted)] + [sum(s['handling'] == h for s in counted) for h in HANDLINGS] + [len(failed)],
                model_counts=[len(models[k]) for k in ['total'] + HANDLINGS],
                task_counts=[len(tasks[k]) for k in ['total'] + HANDLINGS],
                model_sets={k: members(v) for k, v in models.items()},
                task_sets={k: sorted(v) for k, v in tasks.items()},
                failed_model_sets=members(failed),
                uncertain_sites=sum(s['inclusion'] == 'uncertain' for s in selected),
                excluded_sites=sum(s['inclusion'] == 'excluded' for s in selected)))
            sites.extend(selected)
    return rows, sites


def comparison(rows, reference_dir, tasks, warehouses):
    reference_dir = Path(reference_dir)
    summary = json.loads((reference_dir / 'reference_summary.json').read_text())
    require(summary.get('analysis_mode') == 'frozen_reference_reconstruction', 'Reference has wrong analysis mode')
    reference_tasks = []
    for task in sorted(tasks):
        path = reference_dir / 'reference_tasks' / (task + '.json')
        require(path.is_file(), 'Missing frozen reference for task ' + task)
        reference_tasks.append(json.loads(path.read_text()))
    # Reference records deliberately have a separate schema from model outputs.
    # Membership, not all-task table totals, determines the selected-task baseline.
    diffs = []
    for current in rows:
        category, warehouse = current['category_id'], current['warehouse']
        if warehouse not in warehouses: continue
        expected = next((r for r in summary['rows'] if r['category_id'] == category and r['warehouse'] == warehouse), None)
        refs = []
        failures = set()
        for task, record in zip(sorted(tasks), reference_tasks):
            for site in record['sites']:
                if site['category_id'] == category and site['warehouse'] == warehouse:
                    refs.append((task, site))
            for failure in record['failure_attributions']:
                if failure['category_id'] == category and failure['warehouse'] == warehouse:
                    failures.add((task, failure['model_id']))
        expected_counts = [len(refs)] + [sum(s['handling'] == h for _, s in refs) for h in HANDLINGS] + [len(failures)]
        expected_models = [len({(t, s['model_id']) for t,s in refs})] + [len({(t,s['model_id']) for t,s in refs if s['handling'] == h}) for h in HANDLINGS]
        changed = current['counts'] != expected_counts or current['model_counts'] != expected_models
        applicable = expected is not None
        diffs.append(dict(category_id=category, warehouse=warehouse,
                          canonical_row=applicable, status='compared' if applicable else 'outside_historical_scope', matches=(not changed) if applicable else None,
                          reference_counts=expected_counts if applicable else None, observed_counts=current['counts'],
                          delta=[a-b for a,b in zip(current['counts'], expected_counts)] if applicable else None,
                          reference_model_counts=expected_models if applicable else None, observed_model_counts=current['model_counts'],
                          model_delta=[a-b for a,b in zip(current['model_counts'], expected_models)] if applicable else None))
    return dict(reference_summary_sha256=sha256(reference_dir / 'reference_summary.json'),
                compared_task_ids=sorted(tasks), compared_warehouses=sorted(warehouses),
                outside_historical_scope_sites=sum(r['observed_counts'][0] for r in diffs if not r['canonical_row']),
                comparison_status='compared' if tasks and warehouses else 'not_compared',
                all_counts_match=all(r['matches'] for r in diffs if r['canonical_row']) if tasks and warehouses else None, rows=diffs,
                interpretation='Comparison is post-analysis only. Equal counts do not establish identical site memberships. Historical numeric-ID and NULL scopes were audited candidates, not a full syntactic census.')



def resolve_case_listings(results, payloads):
    """Resolve citations into reviewable SQL and recorded before/after snippets."""
    listings = []
    for result in results:
        metadata = result['metadata']
        artifacts = {a['artifact_id']: a for a in payloads[metadata['target_id']]['artifacts']}
        def resolve(ref):
            if ref is None: return None
            a = artifacts[ref['artifact_id']]
            item = dict(ref, kind=a['kind'], source_path=a['source_path'],
                        source_sha256=a['source_sha256'], artifact_sha256=a['sha256'])
            if a['kind'] in {'final_sql', 'compiled_sql', 'replay_sql'}:
                item['full_sql'] = a['content']
            if a['kind'] == 'replay_results':
                item['saved_comparison'] = json.loads(a['content'])
            return item
        for site in result['sites']:
            replay = site['replay']
            listings.append(dict(task_id=metadata['task_id'], target_id=metadata['target_id'],
                site_id=site['site_id'], warehouse=site['warehouse'], model_id=site['model_id'],
                category=site['category'], handling=site['handling'], inclusion=site['inclusion'],
                expression=site['expression'], original_sql=resolve(site['sql_evidence']),
                corrected_sql=resolve(replay['corrected_sql']),
                before_after_evidence=[resolve(ref) for ref in replay['result_evidence']],
                trigger_evidence=[resolve(ref) for ref in site['trigger_evidence']],
                supporting_evidence=[resolve(ref) for ref in site['supporting_evidence']],
                replay_kind=replay['kind'], failure_attributed=site['failure_attributed'], reason=site['reason']))
    return listings

def write_csv(path, rows):
    fields = ['category_id', 'warehouse', 'sites_total', 'sites_correct', 'sites_insufficient', 'sites_unhandled', 'failed_models',
              'models_total', 'models_correct', 'models_insufficient', 'models_unhandled',
              'tasks_total', 'tasks_correct', 'tasks_insufficient', 'tasks_unhandled', 'uncertain_sites', 'excluded_sites']
    with path.open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(fields)
        for row in rows:
            writer.writerow([row['category_id'], row['warehouse']] + row['counts'] + row['model_counts'] + row['task_counts'] + [row['uncertain_sites'], row['excluded_sites']])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--task', action='append', default=[])
    p.add_argument('--target-id', action='append', default=[])
    p.add_argument('--allow-partial', action='store_true', help='Report available records with explicit missing/incomplete coverage')
    p.add_argument('--reference-dir', type=Path)
    p.add_argument('--prompt', type=Path, default=HERE / 'prompt.txt')
    p.add_argument('--taxonomy', type=Path, default=HERE / 'taxonomy.json')
    p.add_argument('--schema', type=Path, default=HERE / 'single_task.output_schema.json')
    args = p.parse_args(argv)
    manifest = load_manifest(args.manifest)
    items = selected_items(manifest, args.target_id, None, args.task)
    require(len({task_id_for_item(i) for i in items}) == len(items), 'Select one target per task to avoid double counting warehouse subsets')
    fingerprints = protocol_fingerprints(args.prompt, args.taxonomy, args.schema)
    prompt = args.prompt.read_text(); taxonomy = json.loads(args.taxonomy.read_text())
    records, coverage, provenance = [], [], []
    input_models = set(); accepted_models = set(); accepted_payloads = {}
    for item in items:
        entry = dict(target_id=item['target_id'], task_id=task_id_for_item(item))
        try:
            payload = load_payload(item)
            model_members = {(m['warehouse'], payload['metadata']['task_id'], m['model_id']) for m in payload['models']}
            input_models.update(model_members)
            accepted = read_accepted(args.run_dir, item['target_id'], payload)
            if accepted is None:
                entry.update(status='missing'); coverage.append(entry); continue
            result, record = accepted
            request = build_request(prompt, taxonomy, payload)
            expected = context_for(item, payload, request, fingerprints, record['context']['model_settings'])
            require(record['context'] == expected, 'Result protocol or input changed; use the original code/config or rerun into a new directory')
            records.append(result)
            accepted_models.update(model_members)
            accepted_payloads[item['target_id']] = payload
            entry.update(status='accepted', review_status=result['review_status'], warehouses=payload['metadata']['warehouses'])
            provenance.append(dict(target_id=item['target_id'], output_sha256=record['output_sha256'], context=record['context']))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            entry.update(status='invalid', error=str(exc))
        coverage.append(entry)
    complete = all(r['status'] == 'accepted' and r['review_status'] == 'complete' for r in coverage)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    coverage_report = dict(selected_tasks=len(items), accepted_tasks=len(records), all_selected_complete=complete, targets=coverage)
    atomic_json(args.output_dir / 'coverage.json', coverage_report)
    if not complete and not args.allow_partial:
        raise ValueError('Missing, invalid, or incomplete analyses. See coverage.json; use --allow-partial to report explicitly partial counts.')
    rows, sites = summarize(records)
    summary = dict(schema_version=1, analysis_mode='independent_task_analysis',
                   coverage=coverage_report, rows=rows, provenance=provenance,
                   prepared_model_warehouse_count=len(input_models), accepted_model_warehouse_count=len(accepted_models),
                   counting_notes=['Model membership is unique (task_id, model_id) within a warehouse and category.',
                                   'A model can contain multiple handling classes; C/I/U model counts need not sum to total.',
                                   'Missing tasks are not zero-site tasks. Uncertain/excluded sites are reported separately.',
                                   'F requires attributed whole-column repair; baseline model failure alone is insufficient.',
                                   'Only verified propagated_failures add downstream F models; affected_models alone never does. Neither adds direct model/site counts.',
                                   'distinct_selected_models counts models with counted sites; accepted_model_warehouse_count is the accepted-analysis denominator.'])
    if args.reference_dir:
        task_ids = {r['metadata']['task_id'] for r in records}
        warehouse_sets = {tuple(r['metadata']['warehouses']) for r in records}
        require(len(warehouse_sets) <= 1, 'Reference comparison requires consistent selected warehouses')
        summary['reference_comparison'] = comparison(rows, args.reference_dir, task_ids, set(next(iter(warehouse_sets), ())))
        atomic_json(args.output_dir / 'comparison.json', summary['reference_comparison'])
    counted = [s for s in sites if s['inclusion'] == 'counted']
    summary['counted_site_count'] = len(counted)
    summary['distinct_selected_models'] = len({(s['warehouse'], s['task_id'], s['model_id']) for s in counted})
    summary['distinct_selected_warehouse_tasks'] = len({(s['warehouse'], s['task_id']) for s in counted})
    summary['distinct_selected_tasks'] = len({s['task_id'] for s in counted})
    atomic_json(args.output_dir / 'summary.json', summary)
    atomic_json(args.output_dir / 'sites.json', sites)
    atomic_json(args.output_dir / 'propagated_failures.json', [dict(failure, task_id=r['metadata']['task_id'], target_id=r['metadata']['target_id']) for r in records for failure in r.get('propagated_failures', [])])
    atomic_json(args.output_dir / 'case_listings.json', resolve_case_listings(records, accepted_payloads))
    write_csv(args.output_dir / 'table.csv', rows)
    with (args.output_dir / 'model_table.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['category_id', 'warehouse', 'total_models', 'correct_models', 'insufficient_models', 'unhandled_models', 'failed_models'])
        for row in rows:
            writer.writerow([row['category_id'], row['warehouse']] + row['model_counts'] + [row['counts'][4]])
    print(json.dumps(dict(accepted_tasks=len(records), selected_tasks=len(items), all_selected_complete=complete,
                         counted_sites=sum(r['counts'][0] for r in rows), output_dir=str(args.output_dir),
                         reference_counts_match=summary.get('reference_comparison', {}).get('all_counts_match'))))
    return 0 if complete else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps({'status': 'aggregation_error', 'error': str(exc)}))
        raise SystemExit(1)
