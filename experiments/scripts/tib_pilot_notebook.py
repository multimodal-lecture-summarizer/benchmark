"""Generate a user-run technical pilot notebook; no automatic Colab execution."""
import json

from .tib_pilot_bundle import ROOT, REGISTRY, sha, write
from .tib_scorer_colab_bootstrap import SETUP_CELL


def create():
    prepared = json.loads((REGISTRY / 'preparation_receipt.json').read_text())
    cells = []
    def markdown(source):
        cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': source.splitlines(keepends=True)})
    def code(source):
        cells.append({'cell_type': 'code', 'metadata': {}, 'execution_count': None,
                      'outputs': [], 'source': source.splitlines(keepends=True)})
    markdown('''# TIB P4d — Pilot40 on Colab T4
Run this private notebook with the supplied ZIP. Choose T4 GPU. Keep Drive files private.
The frozen40 sources and five profiles remain fixed: Lead-3/LexRank/BARTcontrol/LEDngram3/Qwen384.
Expected matrix200: nine historical neural imports,111 new neural outputs,80 new CPU controls.
This is a generation/resource pilot. No model-quality selection, metric recomputation or final test.

User ceilings: total11.5GPUh/23CPUh/11.5active-wallh across at most2 sessions;15% headroom.
Scoring1.5GPUh/3CPUh and recovery0.5wallh are reserved inside totals. Drive2GiB, localfree32GiB,
workingcap24GiB, transfer16GiB; no automatic retries. Default session grant5.75h preserves a second grant.
These are operating ceilings, not measured requirements. Runtime preflight may HOLD.

For session2: delete the old runtime, connect a new T4, set RESUME=True below and use the SAME ZIP/Drive folder.
Never delete/reset the ledger, edit profiles or shrink the cohort to bypass partial/HOLD.
''')
    code(f'''from pathlib import Path
import hashlib, json, os, resource, shutil, subprocess, sys, time, zipfile
import psutil
from google.colab import drive, files
SESSION_STARTED=time.monotonic()
SESSION_EPOCH_NS=time.time_ns()
SETUP_CPU_START=resource.getrusage(resource.RUSAGE_CHILDREN)
SETUP_NET_START=psutil.net_io_counters()
SETUP_WALL_START=SESSION_STARTED
SESSION_LIMIT_SECONDS=11.5*3600
RESUME=False
EXPECTED_ZIP_SHA256={prepared['archive_sha256']!r}
EXPECTED_MANIFEST_SHA256={prepared['manifest_sha256']!r}
WORK=Path('/content/TIB_PILOT40_261020_V1')
BUNDLE=WORK/'package'
BUNDLE.mkdir(parents=True,exist_ok=True)
drive.mount('/content/drive')
DRIVE=Path('/content/drive/MyDrive')
STORE=DRIVE/'TIB_PILOT40_261020_V1'
OUTPUT=STORE/'pilot'
OUTPUT.mkdir(parents=True,exist_ok=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
uploaded=files.upload()
archives=[Path(name) for name in uploaded if name.endswith('.zip')]
assert len(archives)==1,'Upload exactly the supplied pilot ZIP'
archive=archives[0]
assert sha(archive)==EXPECTED_ZIP_SHA256,'Pilot ZIP differs'
with zipfile.ZipFile(archive) as z:
    names=z.namelist()
    assert len(names)==len(set(names)) and z.testzip() is None,'Invalid ZIP'
    for item in z.infolist():
        assert (BUNDLE/item.filename).resolve().is_relative_to(BUNDLE.resolve()),'Unsafe path'
        assert (item.external_attr>>16)&0o170000 != 0o120000,'Symlink member'
    z.extractall(BUNDLE)
assert sha(BUNDLE/'pilot_manifest.json')==EXPECTED_MANIFEST_SHA256
manifest=json.loads((BUNDLE/'pilot_manifest.json').read_text())
assert set(names)==set(manifest['files'])|{{'pilot_manifest.json'}}
assert all(sha(BUNDLE/name)==value for name,value in manifest['files'].items())
sys.path.insert(0,str(BUNDLE))
from experiments.scripts.tib_pilot_session import begin_session, record_setup, finish_session
from experiments.scripts.tib_pilot_resources import allocated
allocation=json.loads((BUNDLE/'pilot_allocation.json').read_text())
allocated(allocation,11.5)
ALLOCATION=OUTPUT/'allocation.json'
if ALLOCATION.exists():
    assert json.loads(ALLOCATION.read_text())==allocation,'Existing allocation differs'
else:
    ALLOCATION.write_text(json.dumps(allocation,indent=2))
LEDGER=OUTPUT/'resource_ledger.json'
assert RESUME or not LEDGER.exists(),'Existing pilot ledger: use RESUME=True; never reset it'
ledger=begin_session(LEDGER,allocation,EXPECTED_MANIFEST_SHA256,local_working_root=WORK,
    observation={{'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'monotonic':SESSION_STARTED,'epoch_ns':SESSION_EPOCH_NS,
                  'logical_cpu_count':os.cpu_count()}})
SESSION_LIMIT_SECONDS=min(11.5*3600,ledger['session_limit_seconds'])
SESSION_STARTED=ledger['session_started_monotonic']
print('Package verified; allocation recorded. Runtime gates still apply before inference.')
def bootstrap_hold(reason):
    hold={{'status':'HOLD','reason':str(reason),'pilot_complete':False,'selection_start_authorized':False}}
    (OUTPUT/('bootstrap-hold-'+str(time.time_ns())+'.json')).write_text(json.dumps(hold,indent=2))
''')
    markdown('''## Runtime setup
Uses the proven pip-less venv bootstrap and pinned requirements. Setup/download time and CPU/transfer cost
count toward this pilot. Original checkpoint stores are read-only; new files go only to TIB_PILOT40_261020_V1.
If setup fails, inspect/export logs; installation completion alone is not a pilot PASS.
''')
    setup = SETUP_CELL.replace("str(BUNDLE/'requirements-colab-t4.txt')", "str(BUNDLE/'requirements-pilot.txt')")
    setup = setup.replace("HF_HUB_DISABLE_TELEMETRY='1')", "HF_HUB_DISABLE_TELEMETRY='1', HF_HOME=str(WORK/'hf-cache'), HF_HUB_CACHE=str(WORK/'hf-cache/hub'), XDG_CACHE_HOME=str(WORK/'cache'), PIP_CACHE_DIR=str(WORK/'pip-cache'))")
    code("assert shutil.disk_usage('/content').free>=allocation['minimum_local_free_bytes'],'Need32GiB free'\n" + setup + '''
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
net=psutil.net_io_counters()
setup_cpu=(usage.ru_utime+usage.ru_stime)-(SETUP_CPU_START.ru_utime+SETUP_CPU_START.ru_stime)
setup_transfer=(net.bytes_recv+net.bytes_sent)-(SETUP_NET_START.bytes_recv+SETUP_NET_START.bytes_sent)
record_setup(LEDGER,cpu_seconds=setup_cpu,transfer_bytes=max(0,setup_transfer),wall_seconds=time.monotonic()-SETUP_WALL_START)
DEPENDENCIES_READY=True
''')
    markdown('''## Run fixed pilot profiles
Sequential candidate subprocesses release GPU weights between models. Runtime checks exact T4/pins,
source/profile/acceptance/ledger identities, actual storage and node budget forecasts.
Stop at partial/HOLD; keep all40 IDs in each candidate denominator. Do not automatically retry failed or
interrupted attempts. A second session continues untouched compatible work within cumulative ceilings.
''')
    code('''assert DEPENDENCIES_READY
contract=json.loads((BUNDLE/'pilot_contract.json').read_text())
HISTORICAL=DRIVE/'TIB_P41_DEVELOPMENT_261019/checkpoints'
candidate_exits={}
for candidate in contract['candidate_order']:
    remaining=(SESSION_LIMIT_SECONDS-(time.monotonic()-SESSION_STARTED))/3600
    if remaining<=0:
        bootstrap_hold('Session guard reached before '+candidate)
        break
    command=[str(PYTHON),'-m','experiments.scripts.tib_pilot_runtime',
        '--bundle',str(BUNDLE),'--output',str(OUTPUT/candidate),
        '--historical-store',str(HISTORICAL),'--candidate',candidate,
        '--allocation',str(ALLOCATION),'--wall-hours',str(min(11.5,remaining))]
    if RESUME and (OUTPUT/candidate/'run_identity.json').exists(): command.append('--resume')
    exit_code=execute(command,candidate+'-'+str(time.time_ns())+'.log')
    candidate_exits[candidate]=exit_code
    receipt_path=OUTPUT/candidate/'candidate_receipt.json'
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {'status':'HOLD'}
    print(candidate,receipt.get('status'),receipt.get('summary'))
    if receipt.get('status') not in ('PASS','COMPLETED_WITH_FAILURES'):
        print('Stopping at partial/HOLD. Retain cohort40 and export evidence.')
        break
''')
    markdown('''## Summarize and export
Keep the ZIP private; source text, summaries and attribution are research artifacts.
No model weights, virtual environment or original historical stores are exported.
Complete execution is not a model winner or selection admission. Return ZIP and executed notebook for audit.
''')
    code('''from datetime import datetime,timezone
EXPORT_STARTED=time.monotonic()
EXPORT_CPU_STARTED=time.process_time()
EXPORT_NET_STARTED=psutil.net_io_counters()
contract=json.loads((BUNDLE/'pilot_contract.json').read_text())
summary={'scope':'technical_pilot40_only','expected_matrix_cells':200,'candidates':{},
         'actual_colab_evidence_requires_audit':True,'selection_start_authorized':False,'metrics_executed':False}
for candidate in contract['candidate_order']:
    path=OUTPUT/candidate/'candidate_receipt.json'
    summary['candidates'][candidate]=json.loads(path.read_text()) if path.exists() else {'status':'NOT_STARTED','selected_denominator':40}
(OUTPUT/'pilot_summary.json').write_text(json.dumps(summary,indent=2))
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export=STORE/('tib-pilot40-evidence-'+stamp+'.zip')
payload_bytes=sum(p.stat().st_size for root in (OUTPUT,BUNDLE) for p in root.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts)
stored_bytes=sum(p.stat().st_size for p in STORE.rglob('*') if p.is_file())
assert stored_bytes+payload_bytes+1024**2<=allocation['persistent_storage_bytes'],'Drive quota lacks export headroom'
ledger=json.loads(LEDGER.read_text())
assert ledger['transfer_bytes']+2*(payload_bytes+1024**2)<=allocation['transfer_bytes'],'Transfer quota lacks export headroom'
with zipfile.ZipFile(export,'w',zipfile.ZIP_DEFLATED) as z:
    for root,prefix in [(OUTPUT,'pilot'),(BUNDLE,'package')]:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path,prefix+'/'+path.relative_to(root).as_posix())
net=psutil.net_io_counters()
export_transfer=max(2*export.stat().st_size,
    (net.bytes_recv+net.bytes_sent)-(EXPORT_NET_STARTED.bytes_recv+EXPORT_NET_STARTED.bytes_sent))
record_setup(LEDGER,cpu_seconds=time.process_time()-EXPORT_CPU_STARTED,
             transfer_bytes=export_transfer,wall_seconds=time.monotonic()-EXPORT_STARTED)
closed=finish_session(LEDGER,status='evidence_exported')
# A unique closure snapshot follows the main payload. It binds post-compression
# accounting without rewriting the historical active-ledger snapshot in that payload.
with zipfile.ZipFile(export,'a',zipfile.ZIP_DEFLATED) as z:
    z.writestr('pilot/session_close_after_export.json',json.dumps(closed,indent=2))
print(json.dumps({k:{'status':v.get('status'),'summary':v.get('summary')} for k,v in summary['candidates'].items()},indent=2))
print(export,'bytes',export.stat().st_size,'SHA256',sha(export))
files.download(str(export))
''')
    name = 'tib-pilot40-colab-t4-261020-v1.ipynb'
    for index, cell in enumerate(cells):
        cell['id'] = 'pilot40-' + str(index)
    notebook = {'nbformat': 4, 'nbformat_minor': 5, 'cells': cells,
                'metadata': {'kernelspec': {'display_name': 'Python3', 'language': 'python', 'name': 'python3'},
                             'colab': {'name': name}, 'accelerator': 'GPU'}}
    path = ROOT / 'experiments/notebooks' / name
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    result = {'path': str(path), 'sha256': sha(path), 'executed': False}
    write(REGISTRY / 'notebook_preparation.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(create(), indent=2))
