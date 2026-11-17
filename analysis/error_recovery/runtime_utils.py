"""Local runtime helpers; no model requests or source-log preparation."""
import hashlib
import json
from pathlib import Path
import uuid
from redaction import redact
HERE = Path(__file__).resolve().parent

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)

def load_manifest(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text())
    for item in value['trajectories']:
        payload = Path(item['payload_path'])
        if not payload.is_absolute():
            item['payload_path'] = str((path.parent / payload).resolve())
    return value
