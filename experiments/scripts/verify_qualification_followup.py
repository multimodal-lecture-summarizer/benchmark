"""Verify evidence integrity, notebook retention and endpoint accounting."""
import csv
import hashlib
import json
import nbformat
import yaml
from experiments.scripts.dataset_qualification_io import ROOT, OUT, sha, write_json
from experiments.scripts.integrate_qualification_notebooks import MARKER


def cell_hash(cell):
    return hashlib.sha256(json.dumps(cell, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    original = json.loads((OUT/'notebook-original-cell-hashes.json').read_text())
    manifest = yaml.safe_load((ROOT/'experiments/notebooks/notebook_manifest.yaml').read_text(encoding='utf-8'))
    register = json.loads((ROOT/'experiments/registry/datasets/qualification-261010.json').read_text(encoding='utf-8'))
    assert len(manifest['dataset_eda_notebooks']) == len(register['datasets']) == 7
    assert register['scientific_benchmark_cohorts'] == [] and not register['cohort_frozen']
    results, artifacts_checked = [], 0
    for entry in register['datasets']:
        notebook = nbformat.read(ROOT/entry['path'], as_version=4)
        nbformat.validate(notebook)
        retained = [c for c in notebook.cells if MARKER not in c.metadata.get('tags', [])]
        stem = (ROOT/entry['path']).stem.removesuffix('-eda')
        # nbformat normalizes multiline JSON lists to strings in memory; compare
        # serialized source cells against the original JSON representation instead.
        serialized = json.loads((ROOT/entry['path']).read_text(encoding='utf-8'))
        raw_retained = [c for c in serialized['cells'] if MARKER not in c.get('metadata', {}).get('tags', [])]
        assert [cell_hash(c) for c in raw_retained] == original[stem], 'Historical cells changed: '+stem
        added = [c for c in notebook.cells if MARKER in c.metadata.get('tags', []) and c.cell_type=='code']
        assert len(added)==1 and added[0].execution_count and added[0].outputs
        assert not any(o.output_type=='error' for o in added[0].outputs)
        compile(added[0].source, str(entry['path'])+':followup', 'exec')
        path = ROOT/entry['receipt']
        assert sha(path)==entry['receipt_sha256']
        receipt = json.loads(path.read_text(encoding='utf-8'))
        assert receipt == entry['evidence'], 'Register snapshot drift'
        assert not receipt['model_inference_run'] and not receipt['unseen_reference_claim']
        counts = receipt['counts']
        assert all(counts[k]>=0 for k in ['selected','observed','label_valid','media_valid','evaluated','failed'])
        assert counts['evaluated']==0 and counts['observed']<=counts['selected']
        assert counts['label_valid']<=counts['observed'] and counts['media_valid']<=counts['observed']
        for artifact in receipt['artifacts']:
            source = ROOT/artifact['path']
            assert source.is_file() and sha(source)==artifact['sha256'], str(source)
            if source.suffix=='.csv' and 'rows' in artifact:
                with source.open(encoding='utf-8', newline='') as stream:
                    rows = list(csv.DictReader(stream))
                assert len(rows)==artifact['rows']
                if source.name.endswith('-id-ledger.csv') or source.name=='iiit-cvid-frame-ledger.csv':
                    assert len(rows)==counts['observed']
                    id_column = 'image_id' if entry['dataset']=='lvvo' else 'id'
                    assert len({r[id_column] for r in rows})==len(rows)
                    assert all(r['decision'] in {'KEEP','REPAIR','EXCLUDE','HOLD'} for r in rows)
            artifacts_checked += 1
        results.append({'dataset':entry['dataset'], 'historical_cells_unchanged':len(retained),
                        'followup_executed':True, 'artifact_hashes_verified':len(receipt['artifacts']),
                        'counts':counts, 'status':'PASS'})
    result = {'status':'PASS', 'notebooks':results, 'artifacts_checked':artifacts_checked,
              'scientific_benchmark_cohorts':[], 'model_evaluations_this_followup':0,
              'verification_scope':'syntax, nbformat, original-cell retention, receipt/ledger hashes and counts; not media/GT qualification'}
    write_json('verification-receipt.json', result)
    print(json.dumps({'status':'PASS','notebooks':len(results),'historical_cells_preserved':sum(r['historical_cells_unchanged'] for r in results),
                      'artifacts_checked':artifacts_checked}))


if __name__ == '__main__':
    main()
