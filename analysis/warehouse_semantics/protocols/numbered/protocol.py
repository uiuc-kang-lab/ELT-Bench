"""Offline, task-scoped semantic evidence contracts. Standard library only."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

ANALYSIS_MODE = 'warehouse_specific_semantics'
WAREHOUSES = {'snowflake', 'databricks', 'redshift'}
CATEGORIES = {'numeric_identifier', 'null_ordering', 'integer_avg', 'division_precision', 'time_units', 'trailing_spaces'}
METADATA_KEYS = {'task_id', 'agent', 'snapshot_id', 'warehouses', 'target_id'}
HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def content_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def atomic_json(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + p.name, dir=p.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
        os.replace(name, p)
    finally:
        if os.path.exists(name): os.unlink(name)


def redact(text):
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]', text, flags=re.S)
    text = re.sub(r'\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b', '[REDACTED_KEY]', text)
    text = re.sub(r'(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]{8,}', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s/@]+(@)', r'\1[REDACTED]\2', text)
    names = r'(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret[_-]?access[_-]?key)'
    text = re.sub(r'(?i)([\"\']?\b' + names + r'\b[\"\']?\s*[:=]\s*)(?:\"[^\"\n]*\"|\'[^\'\n]*\'|[^\s,;}\n)]+)', r'\1[REDACTED]', text)
    return text


def target_id_for(metadata):
    base = {k: metadata[k] for k in sorted(METADATA_KEYS - {'target_id'})}
    digest = content_sha256(json.dumps(base, sort_keys=True, separators=(',', ':')))[:12]
    task = re.sub('[^A-Za-z0-9_.-]', '_', metadata['task_id'])[:100]
    return task + '__' + digest


def validate_payload(p):
    require(p.get('schema_version') == 1 and p.get('analysis_mode') == ANALYSIS_MODE, 'Wrong payload protocol')
    m = p['metadata']
    require(set(m) == METADATA_KEYS, 'Wrong metadata fields')
    require(all(isinstance(m[k], str) and m[k] for k in METADATA_KEYS - {'warehouses'}), 'Empty identity')
    require(isinstance(m['warehouses'], list) and len(set(m['warehouses'])) == len(m['warehouses']) and bool(m['warehouses']) and set(m['warehouses']) <= WAREHOUSES, 'Invalid warehouses')
    require(m['target_id'] == target_id_for(m), 'Non-deterministic task identity')
    require(isinstance(p.get('limitations'), list), 'Missing input limitations')
    ids = set()
    for a in p['artifacts']:
        require(re.fullmatch(r'[A-Za-z0-9_.-]+', a['artifact_id']) is not None, 'Invalid artifact identity')
        require(a['artifact_id'] not in ids, 'Duplicate artifact'); ids.add(a['artifact_id'])
        require(isinstance(a['content'], str), 'Artifact content not text')
        require(a['sha256'] == content_sha256(a['content']), 'Artifact hash mismatch')
        require(a['line_count'] == len(a['content'].splitlines()), 'Artifact line count mismatch')
        require(re.fullmatch(r'[0-9a-f]{64}', a['source_sha256']) is not None, 'Invalid original hash')
        require(isinstance(a['complete'], bool), 'Missing excerpt completeness')
        require(a['warehouse'] in m['warehouses'] or a['warehouse'] is None, 'Artifact outside task warehouses')
    models = set()
    for model in p['models']:
        key = (model['warehouse'], model['model_id'])
        require(key[0] in m['warehouses'] and key not in models, 'Duplicate/out-of-scope model'); models.add(key)
        require(model['sql_artifact_id'] is None or model['sql_artifact_id'] in ids, 'Missing model SQL artifact')
        if model['sql_artifact_id'] is not None:
            a = next(a for a in p['artifacts'] if a['artifact_id'] == model['sql_artifact_id'])
            require(a['warehouse'] == key[0] and a['model_id'] == key[1], 'SQL belongs to another model')
    require(bool(models), 'No evaluated models in task')
    return p


def load_manifest(path):
    path = Path(path).resolve(); m = json.loads(path.read_text())
    require(m.get('schema_version') == 1 and m.get('analysis_mode') == ANALYSIS_MODE, 'Wrong manifest protocol')
    ids = set()
    for item in m['targets']:
        require(item['target_id'] not in ids, 'Duplicate target'); ids.add(item['target_id'])
        p = Path(item['payload_path'])
        item['payload_path'] = str(p if p.is_absolute() else (path.parent / p).resolve())
    return m


def load_payload(item):
    require(sha256(item['payload_path']) == item['payload_sha256'], 'Payload changed since preparation')
    p = validate_payload(json.loads(Path(item['payload_path']).read_text()))
    require(p['metadata']['target_id'] == item['target_id'], 'Manifest/payload target mismatch')
    if 'task_id' in item: require(p['metadata']['task_id'] == item['task_id'], 'Manifest task mismatch')
    return p


def schema_check(value, schema, root=None, path='$'):
    root = root or schema
    if '$ref' in schema:
        s = root
        for k in schema['$ref'][2:].split('/'): s = s[k]
        schema_check(value, s, root, path); return
    if 'anyOf' in schema:
        for s in schema['anyOf']:
            try: schema_check(value, s, root, path); return
            except ValueError: pass
        raise ValueError(path + ': no valid schema alternative')
    if 'enum' in schema: require(value in schema['enum'], path + ': invalid enum')
    if 'const' in schema: require(value == schema['const'], path + ': invalid constant')
    checks = {'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),'boolean':isinstance(value,bool),'null':value is None,'integer':isinstance(value,int) and not isinstance(value,bool)}
    if 'type' in schema:
        kinds = schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        require(any(checks.get(k,False) for k in kinds), path + ': invalid type')
    if isinstance(value,dict):
        require(set(schema.get('required',[])) <= set(value), path + ': missing field')
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False: require(set(value)<=set(props), path+': unknown field')
        for k,v in value.items():
            if k in props:schema_check(v,props[k],root,path+'.'+k)
    if isinstance(value,list):
        require(len(value)>=schema.get('minItems',0),path+': empty list')
        if 'items' in schema:
            for i,v in enumerate(value):schema_check(v,schema['items'],root,path+f'[{i}]')
    if isinstance(value,str):require(len(value)>=schema.get('minLength',0),path+': empty string')
    if isinstance(value,int) and not isinstance(value,bool) and 'minimum' in schema:require(value>=schema['minimum'],path+': below minimum')


def validate_result(result, payload):
    schema_check(result,json.loads((HERE/'single_task.output_schema.json').read_text()))
    require(result['metadata']==payload['metadata'], 'Result identity changed')
    artifacts={a['artifact_id']:a for a in payload['artifacts']}
    models={(m['warehouse'],m['model_id']) for m in payload['models']}
    def evidence(ref, warehouse=None, sql=False):
        require(ref['artifact_id'] in artifacts,'Unknown evidence artifact')
        a=artifacts[ref['artifact_id']]; lo,hi=ref['line_start'],ref['line_end']
        require(1<=lo<=hi<=a['line_count'],'Evidence line range invalid')
        span='\n'.join(a['content'].splitlines()[lo-1:hi])
        require(ref['quote'].strip() and ref['quote'] in span,'Evidence quote absent from cited lines')
        if warehouse:require(a['warehouse'] in (None,warehouse),'Evidence warehouse mismatch')
        if sql:require(a['kind'] in {'final_sql','compiled_sql','upstream_sql','replay_sql'},'SQL citation is not SQL evidence')
        return a
    def verify_failure_replay(site):
        """Bind publication attribution to stored, whole-column evaluator facts.

        This verifies provenance and the recorded comparison, not whether an SQL
        edit isolates the claimed mechanism; that remains an analyst judgment.
        """
        replay=site['replay']
        require(replay['kind']=='analyst_replay','Publication failure attribution requires analyst replay evidence')
        require(replay['baseline_reproduced'] is True and replay['fixed_columns'] and replay['corrected_sql'] is not None and replay['result_evidence'],'Failure attribution requires reproduced baseline and whole-column repair evidence')
        corrected=replay['corrected_sql']['artifact_id']
        require(artifacts[corrected]['kind']=='replay_sql','Attributed correction must cite saved analyst replay SQL')
        facts=[]
        for ref in replay['result_evidence']:
            a=artifacts[ref['artifact_id']]
            if a['kind']!='replay_results':continue
            require((a['warehouse'],a['model_id'])==(site['warehouse'],site['model_id']),'Replay results belong to another model')
            try: data=json.loads(a['content'])
            except (ValueError,TypeError): raise ValueError('Replay results are not structured JSON')
            require(isinstance(data,dict) and (data.get('warehouse'),data.get('task'),data.get('model'))==(site['warehouse'],payload['metadata']['task_id'],site['model_id']),'Replay facts identity mismatch')
            sql_refs=data.get('sql_artifacts',{})
            baseline=artifacts.get(sql_refs.get('baseline')) if isinstance(sql_refs,dict) else None
            if not baseline or baseline['kind']!='replay_sql' or (baseline['warehouse'],baseline['model_id'])!=(site['warehouse'],site['model_id']):continue
            mutations=data.get('mutations',{})
            if not isinstance(mutations,dict):continue
            for name,mutation in mutations.items():
                if isinstance(mutation,dict) and mutation.get('saved_sql_artifact_id')==corrected and sql_refs.get(name)==corrected and corrected!=baseline['artifact_id']:
                    facts.append((data,mutation))
        require(bool(facts),'Failure attribution lacks structured results bound to the saved correction and baseline')
        def passed_score(score):
            return isinstance(score,dict) and score.get('status')=='ok' and isinstance(score.get('match'),bool) and not score.get('error') and not score.get('error_type')
        def columns(score,key):
            value=score.get(key,[])
            return {v.casefold() for v in value} if isinstance(value,list) and all(isinstance(v,str) for v in value) else set()
        supported=False
        for data,mutation in facts:
            reproduced=data.get('baseline_matches_actual',{}); before=data.get('baseline_score',{}); after=mutation.get('score',{})
            if not (passed_score(reproduced) and reproduced['match'] is True and passed_score(before) and before['match'] is False and passed_score(after)):continue
            if mutation.get('error') or mutation.get('error_type'):continue
            # A changed evaluator is not proof that the original column passed.
            if not before.get('rule') or before.get('rule')!=after.get('rule'):continue
            fixed=mutation.get('fixed_columns',[])
            if not isinstance(fixed,list) or not all(isinstance(v,str) for v in fixed):continue
            claimed=replay['fixed_columns']
            if not set(claimed)<=set(fixed):continue
            normalized={v.casefold() for v in claimed}
            originally_failed=columns(before,'unmatched')|columns(before,'missed')
            if not normalized<=originally_failed or not normalized<=columns(after,'matched'):continue
            if normalized & (columns(after,'unmatched')|columns(after,'missed')):continue
            if replay['model_pass_after'] is not None and replay['model_pass_after'] is not after['match']:continue
            supported=True
        require(supported,'Failure attribution contradicts baseline reproduction or whole-column repair facts')
    def verify_replay_evidence(owner):
        replay=owner['replay']
        if replay['corrected_sql'] is not None:
            correction=evidence(replay['corrected_sql'],owner['warehouse'],sql=True)
            require((correction['warehouse'],correction['model_id'])==(owner['warehouse'],owner['model_id']),'Replay SQL belongs to another model')
        for ref in replay['result_evidence']:
            replay_artifact=evidence(ref,owner['warehouse'])
            require(replay_artifact['model_id'] in (None,owner['model_id']),'Replay result belongs to another model')
        require(len(set(replay['fixed_columns']))==len(replay['fixed_columns']),'Duplicate fixed column')
    covered={(m['warehouse'],m['model_id']) for m in result['coverage']['reviewed_models']}
    require(covered<=models,'Coverage invents models')
    reviewed=result['coverage']['reviewed_artifact_ids']
    require(len(set(reviewed))==len(reviewed) and set(reviewed)<=set(artifacts),'Coverage invents/duplicates artifacts')
    if result['review_status']=='complete':
        require(covered==models and set(reviewed)==set(artifacts),'Complete review omits supplied models/artifacts')
    seen=set(); locations=set()
    for site in result['sites']:
        require(site['site_id'] not in seen,'Duplicate site_id');seen.add(site['site_id'])
        require((site['warehouse'],site['model_id']) in models,'Site outside task model inventory')
        a=evidence(site['sql_evidence'],site['warehouse'],sql=True)
        require(a['kind'] in {'final_sql','compiled_sql'},'Site must cite original evaluated final or compiled SQL')
        require((a['warehouse'],a['model_id'])==(site['warehouse'],site['model_id']),'Site SQL belongs to another model')
        require(site['expression'] in site['sql_evidence']['quote'],'Expression is not literal SQL in cited quote')
        # Citation ranges and compiled copies cannot create extra logical sites.
        # Independent equal leaves must include enough surrounding SQL context
        # in expression to identify their distinct original projection/key.
        key=(site['warehouse'],site['model_id'],site['category'],site['expression'].strip())
        require(key not in locations,'Duplicate logical position');locations.add(key)
        for ref in site['trigger_evidence']: evidence(ref,site['warehouse'])
        for ref in site['supporting_evidence']: evidence(ref)
        replay=site['replay']
        verify_replay_evidence(site)
        require(all((site['warehouse'],m) in models for m in site['affected_models']),'Invalid propagated model')
        if site['inclusion']=='counted':
            require(site['trigger_status'] in {'observed_actual','verified_counterfactual'} and site['trigger_evidence'],'Counted site lacks observed trigger')
            require(next(m for m in payload['models'] if (m['warehouse'],m['model_id'])==(site['warehouse'],site['model_id']))['actual_available'],'Counted site lacks evaluated output')
        if site['failure_attributed']:
            require(site['inclusion']=='counted','Failure attribution requires a counted source site')
            verify_failure_replay(site)
        if replay['kind']=='none':
            require(replay['corrected_sql'] is None and not replay['result_evidence'] and not replay['fixed_columns'] and replay['baseline_reproduced'] is None and replay['model_pass_after'] is None and replay['single_site'] is None,'No replay must not claim replay facts')
    source_sites={site['site_id']:site for site in result['sites']}
    propagated_targets=set()
    for failure in result['propagated_failures']:
        target=(failure['warehouse'],failure['model_id'])
        require(target in models,'Propagated failure outside task model inventory')
        require(next(m for m in payload['models'] if (m['warehouse'],m['model_id'])==target)['actual_available'],'Propagated failure lacks evaluated output')
        key=target+(failure['category'],)
        require(key not in propagated_targets,'Duplicate propagated failure target');propagated_targets.add(key)
        source_ids=failure['source_site_ids']
        require(bool(source_ids) and len(set(source_ids))==len(source_ids),'Missing or duplicate propagated source sites')
        for source_id in source_ids:
            require(source_id in source_sites,'Unknown propagated source site')
            source=source_sites[source_id]
            require(source['inclusion']=='counted','Propagated source site is not counted')
            require((source['warehouse'],source['category'])==(failure['warehouse'],failure['category']),'Propagated source warehouse/category mismatch')
        verify_replay_evidence(failure)
        verify_failure_replay(failure)
    for exclusion in result['exclusions']:
        require(exclusion['warehouse'] in payload['metadata']['warehouses'],'Exclusion outside selected warehouses')
        require(exclusion['model_id'] is None or (exclusion['warehouse'],exclusion['model_id']) in models,'Exclusion outside selected models')
        for ref in exclusion['evidence']:evidence(ref)
    return result
