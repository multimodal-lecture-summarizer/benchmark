"""Write the Pilot40 scorer Colab notebook from the already hashed private bundle.

Cells follow the audited scorer notebook v2 (venv without pip, pinned assets, ZIP verification)
and swap in the Pilot40 runner, its 1.5 h session guard and its receipt name.
"""
import hashlib
import json

from experiments.scripts.tib_pilot40_scorer_bundle import AMENDMENT_ID, REGISTRY, ROOT
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL
from experiments.scripts.tib_scorer_colab_bundle import file_hash

SESSION_HOURS = 1.5
NOTEBOOK = "experiments/notebooks/tib-pilot40-scorer-colab-t4-261023-v1.ipynb"
RECEIPT = "scorer_pilot40_receipt.json"


def create_notebook():
    prep = json.loads((REGISTRY / "preparation_receipt.json").read_text(encoding="utf-8"))
    policy = {"amendment_id": "tib-scorer-bootstrap-261020-v2",
              "setup_cell_sha256": hashlib.sha256(SETUP_CELL.encode("utf-8")).hexdigest(),
              "scorer_bundle_sha256": prep["archive_sha256"],
              "scorer_metrics_and_requirements_changed": False}
    cells = []

    def markdown(text):
        cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})

    def code(text):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": text.splitlines(keepends=True)})

    markdown(f"""# TIB Pilot40 reference scoring on Colab T4 (v1)
Choose **Runtime → Change runtime type → T4 GPU**, then run cells in order. Upload the matching ZIP.

Scores **{prep['scoreable_rows']} Pilot40 outputs** of {prep['rows']} cells (Lead-3, LexRank, BART control, LED ngram3; **no Qwen3**)
with the frozen scorer v2, then the S/M/L views (ROUGE + BERTScore only). The {prep['failed_rows']} failed generation cells stay in
the denominator with NULL metrics. It never loads a generation model and starts no selection/test.

Purpose: measure scoring cost by profile × source-length stratum and component. Scores are development data: no ranking, no selection.
Session guard {SESSION_HOURS} h (the scoring reserve of the 20/10 Pilot40 allocation). Status stays **HOLD** until actual fixtures and all
scoreable outputs pass here. The bundle holds sources/references: keep Drive private and never publish the ZIP.
""")
    code(f'''from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, time, zipfile
from google.colab import drive, files
SESSION_STARTED = time.monotonic()
SESSION_LIMIT_SECONDS = {SESSION_HOURS} * 3600
EXPECTED_ZIP_SHA256 = {prep['archive_sha256']!r}
EXPECTED_MANIFEST_SHA256 = {prep['manifest_sha256']!r}
WORK = Path('/content/TIB_PILOT40_SCORING_261023_V1')
WORK.mkdir(exist_ok=True)
drive.mount('/content/drive')
STORE = Path('/content/drive/MyDrive/TIB_PILOT40_SCORING_261023_V1')
STORE.mkdir(parents=True, exist_ok=True)
OUTPUT = STORE / 'scorer-evidence'
OUTPUT.mkdir(exist_ok=True)
BOOTSTRAP_POLICY = {policy!r}
(OUTPUT/'bootstrap_policy.json').write_text(json.dumps(BOOTSTRAP_POLICY,indent=2))
def bootstrap_hold(reason):
    payload = {{'delivered_status':'HOLD', 'views_status':'NOT_STARTED', 'scorer_pilot40_ready':False,
               'T4_verified':False, 'actual_colab_execution':True, 'reason':str(reason),
               'generation_executed':False, 'selection_start_authorized':False}}
    history=OUTPUT/'bootstrap-history'
    history.mkdir(exist_ok=True)
    (history/('hold-'+str(time.time_ns())+'.json')).write_text(json.dumps(payload, indent=2))
    (OUTPUT/'bootstrap_hold.json').write_text(json.dumps(payload, indent=2))
    (OUTPUT/{RECEIPT!r}).write_text(json.dumps(payload, indent=2))
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as h:
        for part in iter(lambda:h.read(4*1024*1024), b''):
            digest.update(part)
    return digest.hexdigest()
print('Private checkpoint/evidence folder:', STORE)
bootstrap_hold('New notebook session; actual Pilot40 scorer receipt not produced yet')
''')
    markdown("""## 1. Upload and verify the supplied ZIP
Both the outer ZIP and every packaged file are verified before anything is installed or executed.
""")
    code(f'''uploaded = files.upload()
matches = [Path(name) for name in uploaded if name.endswith('.zip')]
assert len(matches)==1, 'Upload exactly the supplied Pilot40 scorer ZIP.'
archive = matches[0]
assert sha(archive)==EXPECTED_ZIP_SHA256, 'ZIP hash mismatch; do not proceed.'
BUNDLE = WORK/'bundle'
BUNDLE.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    assert len(names)==len(set(names)), 'Duplicate ZIP members'
    for item in z.infolist():
        target = (BUNDLE/item.filename).resolve()
        assert target.is_relative_to(BUNDLE.resolve()), 'Unsafe ZIP path'
        assert not ((item.external_attr >> 16) & 0o170000)==0o120000, 'Symlink ZIP member'
    z.extractall(BUNDLE)
assert sha(BUNDLE/'package_manifest.json')==EXPECTED_MANIFEST_SHA256
manifest = json.loads((BUNDLE/'package_manifest.json').read_text())
assert set(names)==set(manifest['files'])|{{'package_manifest.json'}}
for relative, expected in manifest['files'].items():
    assert sha(BUNDLE/relative)==expected, relative
print('Verified files:', len(manifest['files']), '| cells:', {prep['rows']}, '| scoreable:', {prep['scoreable_rows']})
''')
    markdown("""## 2. Install the pinned runtime into a separate Python environment
Same pins and bootstrap as the audited scorer notebook v2 (`venv --without-pip`, base `pip --python`). No pin is relaxed.
""")
    code(SETUP_CELL)
    markdown("""## 3. Download and validate the two pinned scorer models
Only BERTScore XLM-R layer 17 and the sentence-similarity model are acquired; complete manifests are verified on rerun.
""")
    code('''ASSETS = WORK/'scorer-assets'
asset_code = """
from pathlib import Path
from experiments.scripts.tib_benchmark_scorer_assets import acquire
from experiments.scripts.tib_benchmark_scorer import validate_assets
from experiments.scripts.rq2_tib_benchmark_metrics import BERT_MODEL,BERT_REVISION,SBERT_MODEL,SBERT_REVISION
root=Path(__import__('sys').argv[1])
if not all((root/k/'asset_manifest.json').exists() for k in ('bert','sentence')):
    acquire(root)
for k,m,r in [('bert',BERT_MODEL,BERT_REVISION),('sentence',SBERT_MODEL,SBERT_REVISION)]:
    validate_assets(root/k,model=m,revision=r)
print('Actual pinned scorer asset hashes verified')
"""
asset_exit=execute([str(PYTHON),'-c',asset_code,str(ASSETS)],'assets.log')
if asset_exit:
    bootstrap_hold('Scorer assets incomplete/invalid; see assets.log')
assert asset_exit==0, 'HOLD: assets. Export evidence using the last cell.'
''')
    markdown("""## 4. Run the Pilot40 scorer
Fresh scoring is the default. Set `RESUME=True` only to replay a **complete** matching cache from an earlier attempt; a missing or
mismatched cache is a HOLD (no hole filling, no automatic retry). The runner scores delivered summaries (long sources first), then views.
""")
    code(f'''RESUME = False
remaining_hours = (SESSION_LIMIT_SECONDS-(time.monotonic()-SESSION_STARTED))/3600
assert remaining_hours > 0.25, 'Too little session time left; do not start scoring.'
command=[str(PYTHON),'-m','experiments.scripts.tib_pilot40_scorer_runner',
         '--bundle',str(BUNDLE),'--output',str(OUTPUT),'--assets',str(ASSETS),
         '--wall-hours',str(remaining_hours-0.15)]  # runner stops before the notebook kills it
if RESUME:
    command.append('--resume')
launch_ns=time.time_ns()
bootstrap_hold('Scorer subprocess started; awaiting current actual receipt')
exit_code=execute(command,'scorer-'+str(launch_ns)+'.log')
if exit_code not in (0,2):
    bootstrap_hold('Scorer subprocess failed before a complete receipt; inspect logs')
receipt_path=OUTPUT/{RECEIPT!r}
if receipt_path.exists() and exit_code in (0,2):
    current=json.loads(receipt_path.read_text())
    if int(current.get('run_id',0)) >= launch_ns:
        print(json.dumps({{k: current.get(k) for k in ('delivered_status','views_status','reasons',
              'successful_metric_records','expected_scoreable')}}, indent=2))
    else:
        bootstrap_hold('Receipt does not belong to this execution; a prior PASS cannot certify it')
        print((OUTPUT/'bootstrap_hold.json').read_text())
else:
    bootstrap_hold('No actual scorer receipt produced')
print('Do not infer PASS from install/download completion or local tests.')
''')
    markdown("""## 5. Download the evidence ZIP (also run after a HOLD)
Contains inputs/provenance, pinned code and manifests, receipts, per-output metrics and timings, logs and checkpoints.
Weights and the venv are omitted. Keep it private and send it back for audit.
""")
    code('''from datetime import datetime, timezone
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export=STORE/('tib-pilot40-scoring-evidence-'+stamp+'.zip')
with zipfile.ZipFile(export,'w',zipfile.ZIP_DEFLATED) as z:
    for root,prefix in [(OUTPUT,'evidence'),(BUNDLE,'bundle')]:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path,prefix+'/'+path.relative_to(root).as_posix())
    if 'ASSETS' in globals():
        for key in ('bert','sentence'):
            manifest=ASSETS/key/'asset_manifest.json'
            if manifest.exists():
                z.write(manifest,'scorer-assets/'+key+'/asset_manifest.json')
print('ZIP:',export,'| bytes:',export.stat().st_size,'| SHA256:',sha(export))
files.download(str(export))
''')
    for index, cell in enumerate(cells):
        cell["id"] = f"pilot40-scoring-{index:02d}"
    notebook = {"nbformat": 4, "nbformat_minor": 5,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                             "accelerator": "GPU", "colab": {"name": NOTEBOOK.rsplit('/', 1)[1]}}, "cells": cells}
    path = ROOT / NOTEBOOK
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"notebook": str(path), "sha256": file_hash(path), "amendment_id": AMENDMENT_ID,
            "execution_count": 0}


if __name__ == "__main__":
    print(json.dumps(create_notebook(), indent=2))
