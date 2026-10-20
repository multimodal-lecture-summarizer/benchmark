"""Generate origin handoff and fresh recovery notebooks; never execute them locally."""
import json
from pathlib import Path

from experiments.scripts.tib_p4_recovery_bundle import ROOT, REGISTRY, sha
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL


def create():
    receipt = json.loads((REGISTRY / 'preparation_receipt.json').read_text())
    shared = f'''from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, time, zipfile
from google.colab import drive, files
SESSION_STARTED=time.monotonic()
SESSION_LIMIT_SECONDS=11.5*3600
EXPECTED_ZIP_SHA256={receipt['archive_sha256']!r}
EXPECTED_MANIFEST_SHA256={receipt['manifest_sha256']!r}
WORK=Path('/content/TIB_P4_RECOVERY_261020_V2')
PACKAGE=WORK/'package'
PACKAGE.mkdir(parents=True,exist_ok=True)
drive.mount('/content/drive')
DRIVE=Path('/content/drive/MyDrive')
STORE=DRIVE/'TIB_P4_RECOVERY_261020_V2'
STORE.mkdir(exist_ok=True)
WITNESS=STORE/'origin_witness.json'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()
uploaded=files.upload()
archives=[Path(name) for name in uploaded if name.endswith('.zip')]
assert len(archives)==1,'Upload exactly the supplied recovery ZIP'
archive=archives[0]
assert sha(archive)==EXPECTED_ZIP_SHA256,'Wrong recovery ZIP'
with zipfile.ZipFile(archive) as z:
    names=z.namelist()
    assert len(names)==len(set(names)),'Duplicate members'
    for item in z.infolist():
        assert (PACKAGE/item.filename).resolve().is_relative_to(PACKAGE.resolve()),'Unsafe path'
        assert (item.external_attr>>16)&0o170000 != 0o120000,'Symlink member'
    z.extractall(PACKAGE)
assert sha(PACKAGE/'recovery_manifest.json')==EXPECTED_MANIFEST_SHA256
manifest=json.loads((PACKAGE/'recovery_manifest.json').read_text())
assert set(names)==set(manifest['files'])|{{'recovery_manifest.json'}}
for name,expected in manifest['files'].items():
    assert sha(PACKAGE/name)==expected,name
sys.path.insert(0,str(PACKAGE/'tools'))
from tib_p4_session_recovery import seal_origin, verify_fresh
from tib_p4_recovery_context import create_run_context, finalize
print('Recovery package verified; original stores will be read-only.')
'''
    def markdown(text):
        return {'cell_type': 'markdown', 'metadata': {}, 'source': text.splitlines(keepends=True)}
    def code(text):
        return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [],
                'source': text.splitlines(keepends=True)}
    origin = [markdown('''# P4 recovery — A. Seal current session
Run this notebook in your **current Colab runtime before deleting it**, using the recovery ZIP.
It reads existing Drive checkpoint files, binds their hashes to this VM boot ID and writes one origin witness.
No dependency install, model load, generation, scoring or copying checkpoints into their stores.

After both cells succeed: **Runtime → Disconnect and delete runtime**. Open notebook B in a new T4 runtime.
A kernel restart on the same VM is insufficient. Do not rerun notebook A in the new VM.
'''), code(shared), code('''try:
    origin=seal_origin(PACKAGE,DRIVE,WITNESS)
    print(json.dumps({'state':origin['state'],'origin_session':origin['origin_session'],
                      'sealed_file_counts':{k:len(v['files']) for k,v in origin['stores'].items()},
                      'witness':str(WITNESS)},indent=2))
    print('STOP HERE. Disconnect and delete this runtime, then open notebook B with a NEW T4 runtime.')
except Exception as error:
    hold={'status':'HOLD','stage':'origin_seal','reason':str(error),'cross_session_recovery_verified':False}
    (STORE/('origin-hold-'+str(time.time_ns())+'.json')).write_text(json.dumps(hold,indent=2))
    raise
''')]
    fresh = [markdown('''# P4 recovery — B. Fresh Colab T4
Prerequisite: notebook A sealed checkpoints in the previous runtime, then that runtime was **deleted**.
Choose T4 GPU. Upload the same recovery ZIP. Same-VM checks HOLD before dependency/model loading.

P4 scorer-ready is already closed PASS. This notebook never runs new generation, metrics, fixtures, pilot40,
selection300 or test. It replays all123generation nodes/21outputs and21scorer checkpoints using original keys.
Generation model reload independently verifies original runtime identity; missing cache fails without fallback.
Scorer replay reads archived valid results only. Original cost and fresh load/restore overhead are separate.
'''), code(shared), code('''RECOVERY_PREFLIGHT_OK=False
proof=verify_fresh(PACKAGE,DRIVE,WITNESS)
OUTPUT=STORE/'runs'/('fresh-'+str(time.time_ns()))
context=create_run_context(PACKAGE,DRIVE,WITNESS,OUTPUT)
CONTEXT=OUTPUT/'session_context.json'
print(json.dumps(proof,indent=2))
print('New immutable evidence run:',OUTPUT)
RECOVERY_PREFLIGHT_OK=True
def bootstrap_hold(reason):
    hold={'status':'HOLD','reason':str(reason),'cross_session_recovery_verified':False}
    (OUTPUT/('bootstrap-hold-'+str(time.time_ns())+'.json')).write_text(json.dumps(hold,indent=2))
'''), markdown('''## Pinned runtime setup
Uses the tested pip-less venv bootstrap. Direct recovery requirements preserve both original runtime profiles;
the accelerator pin1.15.0 is the same observed generation/scorer version. Any full-runtime mismatch HOLDs.
Recovery needs working disk for the three original model snapshots;32GiB free is an operational guard,
not a full-study storage budget. All subprocesses share the notebook11.5h session deadline.
'''), code("assert RECOVERY_PREFLIGHT_OK\nassert shutil.disk_usage('/content').free >= 32*1024**3,'Need 32 GiB free working disk for recovery assets/setup'\nBUNDLE=PACKAGE/'scorer_bundle'\n" + SETUP_CELL.replace("str(BUNDLE/'requirements-colab-t4.txt')", "str(PACKAGE/'requirements-recovery.txt')") + "\nDEPENDENCIES_READY=True\n"),
        markdown('''## Generation checkpoint recovery
Loads each original generation model once, then recomputes native source windows and reads original nodes.
All7historical profiles are replayed for integrity only; this does not reopen config search.
No missing-node inference is allowed. New generation calls must stay0. Model reload/download can take time.
'''), code('''assert RECOVERY_PREFLIGHT_OK and DEPENDENCIES_READY
RUN_ENV['PYTHONPATH']=str(PACKAGE/'generation_bundle')
GEN_STORE=DRIVE/'TIB_P41_DEVELOPMENT_261019/checkpoints'
remaining=(SESSION_LIMIT_SECONDS-(time.monotonic()-SESSION_STARTED))/3600
gen_command=[str(PYTHON),str(PACKAGE/'tools/tib_p4_generation_recovery.py'),
    '--bundle',str(PACKAGE/'generation_bundle'),'--store',str(GEN_STORE),
    '--expected',str(PACKAGE/'expected_generation.json'),'--output',str(OUTPUT/'generation'),
    '--session-context',str(CONTEXT),'--wall-hours',str(min(11.5,remaining))]
generation_exit=execute(gen_command,'generation-subprocess.log')
print('Generation exit:',generation_exit,'(inspect receipt; do not retry by inference)')
'''), markdown('''## Scorer cache replay
Reads the original21Drive checkpoints with exact original runtime/input/key identity; no scorer model loads,
metric calls or fixture reruns. A changed full package inventory, Python/platform or thread configuration HOLDs.
Do not edit identities/checkpoint keys to make the current runtime match.
'''), code('''assert RECOVERY_PREFLIGHT_OK and DEPENDENCIES_READY
RUN_ENV['PYTHONPATH']=str(PACKAGE/'scorer_bundle')
score_command=[str(PYTHON),str(PACKAGE/'tools/tib_p4_scorer_replay.py'),
    '--bundle',str(PACKAGE/'scorer_bundle'),
    '--store',str(DRIVE/'TIB_P4_SCORER_261020_V1/scorer-evidence/checkpoints'),
    '--origin-ready',str(PACKAGE/'origin_scorer_ready.json'),
    '--asset-manifests',str(PACKAGE/'scorer_asset_manifests'),
    '--expected',str(PACKAGE/'expected_scorer.json'),'--output',str(OUTPUT/'scorer'),
    '--session-context',str(CONTEXT)]
scorer_exit=execute(score_command,'scorer-replay-subprocess.log')
print('Scorer replay exit:',scorer_exit)
'''), markdown('''## Combine and export evidence
Combined PASS requires both actual stage results, this VM/run/witness bindings,123/21generation reuse,
21×5finite cached scores, zero new calls and unchanged original stores. Same-session/local tests cannot certify it.
Keep the ZIP private. No model weight files or virtual environment are exported. Pilot40 remains a separate gate.
'''), code('''result=finalize(PACKAGE,DRIVE,WITNESS,OUTPUT)
print(json.dumps({'status':result['status'],'reasons':result['reasons'],
                  'cross_session_recovery_verified':result['cross_session_recovery_verified'],
                  'new_generation_calls':result['new_generation_calls'],
                  'new_metric_calls':result['new_metric_calls']},indent=2))
'''), code('''from datetime import datetime,timezone
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export=STORE/('tib-p4-recovery-evidence-'+stamp+'.zip')
with zipfile.ZipFile(export,'w',zipfile.ZIP_DEFLATED) as z:
    for root,prefix in [(OUTPUT,'recovery'),(PACKAGE,'package')]:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path,prefix+'/'+path.relative_to(root).as_posix())
    z.write(WITNESS,'origin_witness.json')
print(export,'bytes',export.stat().st_size,'SHA256',sha(export))
files.download(str(export))
''')]
    results = {}
    for kind, cells in [('handoff', origin), ('fresh-recovery', fresh)]:
        name = 'tib-p4-' + kind + '-colab-261020-v2.ipynb'
        for index, cell in enumerate(cells):
            cell['id'] = f'recovery-{kind}-{index}'
        notebook = {'nbformat': 4, 'nbformat_minor': 5, 'cells': cells,
                    'metadata': {'kernelspec': {'display_name': 'Python3', 'language': 'python', 'name': 'python3'},
                                 'colab': {'name': name}, 'accelerator': 'GPU'}}
        path = ROOT / 'experiments/notebooks' / name
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        results[kind] = {'path': str(path), 'sha256': sha(path), 'executed': False}
    return results


if __name__ == '__main__':
    print(json.dumps(create(), indent=2))
