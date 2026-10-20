"""Write the scorer-only Colab notebook from an already hashed private bundle."""
import hashlib
import json
from pathlib import Path

from experiments.scripts.tib_scorer_colab_bundle import LOCAL, REGISTRY, ROOT, file_hash
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL


def create_notebook():
    receipt = json.loads((REGISTRY / "scorer_ready_receipt.json").read_text(encoding="utf-8"))
    bootstrap_policy = {"amendment_id": "tib-scorer-bootstrap-261020-v2",
                        "setup_cell_sha256": hashlib.sha256(SETUP_CELL.encode("utf-8")).hexdigest(),
                        "scorer_bundle_sha256": receipt["archive_sha256"],
                        "scorer_metrics_and_requirements_changed": False}
    cells = []
    def markdown(text):
        cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})
    def code(text):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": text.splitlines(keepends=True)})
    markdown("""# TIB P4 — formal-runtime scorer on Colab T4 (notebook v2)
Choose **Runtime → Change runtime type → T4 GPU**, then run cells in order.
Upload the matching ZIP. This notebook scores **21 stored development summaries / 3 sources**;
it never loads generation models or runs selection/test. Reference B and warning outputs remain included.

Status remains **HOLD** until actual fixtures, native/long-input probes, all21 scoring and checkpoint checks pass here.
PASS is scoped scorer readiness on these development inputs, not pilot40, model quality/admission or budget approval.
Sources/references and attribution are private research material: keep the bundle/evidence in private Drive.
Do not publish ZIP or source/reference text. Pinned weights download from official Hugging Face.
""")
    code(f'''from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, time, zipfile
from google.colab import drive, files
SESSION_STARTED = time.monotonic()
SESSION_LIMIT_SECONDS = 11.5 * 3600
EXPECTED_ZIP_SHA256 = {receipt['archive_sha256']!r}
EXPECTED_MANIFEST_SHA256 = {receipt['manifest_sha256']!r}
WORK = Path('/content/TIB_SCORER_261020_V1')
WORK.mkdir(exist_ok=True)
drive.mount('/content/drive')
STORE = Path('/content/drive/MyDrive/TIB_P4_SCORER_261020_V1')
STORE.mkdir(parents=True, exist_ok=True)
OUTPUT = STORE / 'scorer-evidence'
OUTPUT.mkdir(exist_ok=True)
BOOTSTRAP_POLICY = {bootstrap_policy!r}
(OUTPUT/'bootstrap_policy.json').write_text(json.dumps(BOOTSTRAP_POLICY,indent=2))
def bootstrap_hold(reason):
    payload = {{'status':'HOLD', 'scorer_ready':False, 'T4_verified':False,
               'actual_colab_execution':True, 'reason':str(reason),
               'generation_executed':False, 'selection_start_authorized':False}}
    history=OUTPUT/'bootstrap-history'
    history.mkdir(exist_ok=True)
    (history/('hold-'+str(time.time_ns())+'.json')).write_text(json.dumps(payload, indent=2))
    (OUTPUT/'bootstrap_hold.json').write_text(json.dumps(payload, indent=2))
    (OUTPUT/'scorer_ready_receipt.json').write_text(json.dumps(payload, indent=2))
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as h:
        for part in iter(lambda:h.read(4*1024*1024), b''):
            digest.update(part)
    return digest.hexdigest()
print('Private checkpoint/evidence folder:', STORE)
bootstrap_hold('New notebook session; actual scorer receipt not produced yet')
''')
    markdown("""## 1. Upload and verify the supplied ZIP
The notebook verifies both outer ZIP and every packaged file before installing or executing it.
The package contains no selection/test records and no generation adapters.
""")
    code('''uploaded = files.upload()
matches = [Path(name) for name in uploaded if name.endswith('.zip')]
assert len(matches)==1, 'Upload exactly the supplied scorer ZIP.'
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
assert set(names)==set(manifest['files'])|{'package_manifest.json'}
for relative, expected in manifest['files'].items():
    assert sha(BUNDLE/relative)==expected, relative
print('Verified files:', len(manifest['files']), '| Stored summaries: 21 | Sources: 3')
''')
    markdown("""## 2. Install the pinned runtime into a separate Python environment
Torch CUDA130 and NumPy differ from the existing CPU receipt; this versioned amendment changes the runtime only.
Exact scorer/support pins are supplied. The runner records all installed transitive versions and binds them to checkpoints.
Downloading/replacing CUDA wheels can take time if the Colab base image differs; the notebook does not relax pins.
Bootstrap v2 bypasses ensurepip with --without-pip and uses base pip --python to install into the target venv.
Existing partial venvs are repaired without deletion. All bootstrap stderr is retained in exported logs.
""")
    code(SETUP_CELL)
    markdown("""## 3. Download and validate the two pinned scorer models
Only BERTScore XLM-R layer17 and the sentence-similarity model are acquired.
If the cell was interrupted, rerun: complete manifests are verified; partial files are preserved for diagnosis.
""")
    code('''ASSETS = WORK/'scorer-assets'
asset_code = """
from pathlib import Path
from experiments.scripts.tib_benchmark_scorer_assets import acquire
from experiments.scripts.tib_benchmark_scorer import validate_assets
from experiments.scripts.rq2_tib_benchmark_metrics import BERT_MODEL,BERT_REVISION,SBERT_MODEL,SBERT_REVISION
root=Path(__import__('sys').argv[1])
if not all((root/k/'asset_manifest.json').exists() for k in ('bert','sentence')):
    # acquire never replaces an existing complete manifest; mixed completion needs explicit review.
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
    markdown("""## 4. Run actual scorer fixtures and scorer-only E2E
Fresh scoring is the default. Set `RESUME=True` only to reuse matching scorer checkpoints from an earlier attempt.
Reuse cost is separate from original scoring cost; hash/runtime mismatch becomes HOLD.
This tests scorer checkpoint persistence/readback. It does not certify generation checkpoint recovery or cross-session survival.
""")
    code('''RESUME = False
remaining_hours = min(11.5,(SESSION_LIMIT_SECONDS-(time.monotonic()-SESSION_STARTED))/3600)
command=[str(PYTHON),'-m','experiments.scripts.tib_scorer_colab_runner',
         '--bundle',str(BUNDLE),'--output',str(OUTPUT),'--assets',str(ASSETS),
         '--wall-hours',str(remaining_hours)]
if RESUME:
    command.append('--resume')
launch_ns=time.time_ns()
bootstrap_hold('Scorer subprocess started; awaiting current actual receipt')
exit_code=execute(command,'scorer-'+str(launch_ns)+'.log')
if exit_code not in (0,2):
    bootstrap_hold('Scorer subprocess failed before a complete receipt; inspect logs')
receipt_path=OUTPUT/'scorer_ready_receipt.json'
if receipt_path.exists() and exit_code in (0,2):
    current=json.loads(receipt_path.read_text())
    if int(current.get('run_id',0)) >= launch_ns:
        print(json.dumps(current,indent=2))
    else:
        bootstrap_hold('Receipt does not belong to this execution; prior PASS cannot certify it')
        print((OUTPUT/'bootstrap_hold.json').read_text())
else:
    bootstrap_hold('No actual scorer-ready receipt produced')
print('Do not infer PASS from install/download completion or local tests.')
''')
    markdown("""## 5. Download evidence ZIP (also run after a HOLD)
Includes inputs/provenance, pinned code and manifests, actual receipts, per-output metrics/cost, logs and scorer checkpoints.
Weights/venv are omitted. Send this private ZIP back for audit. No generation/selection/final execution follows automatically.
""")
    code('''from datetime import datetime, timezone
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export=STORE/('tib-scorer-evidence-'+stamp+'.zip')
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
        cell["id"] = f"scorer-v2-{index:02d}"
    notebook = {"nbformat": 4, "nbformat_minor": 5,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                             "accelerator": "GPU", "colab": {"name": "tib-p4-scorer-colab-t4-261020-v2.ipynb"}}, "cells": cells}
    path = ROOT / "experiments/notebooks/tib-p4-scorer-colab-t4-261020-v2.ipynb"
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"notebook": str(path), "sha256": file_hash(path), "execution_count": 0}


if __name__ == "__main__":
    print(json.dumps(create_notebook(), indent=2))
