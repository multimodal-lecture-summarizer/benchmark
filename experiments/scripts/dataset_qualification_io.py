"""Small evidence writers for additive dataset qualification reviews."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments/outputs/dataset_qualification_261010'
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def write_json(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}

def write_csv(name, rows):
    path = OUT / name
    rows = list(rows)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'rows': len(rows)}

def receipt(dataset, counts, artifacts, **details):
    value = {'dataset': dataset, 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
             'counts': counts, 'artifacts': artifacts, 'model_inference_run': False,
             'unseen_reference_claim': False, **details}
    write_json(dataset + '-qualification-receipt.json', value)
    return value
