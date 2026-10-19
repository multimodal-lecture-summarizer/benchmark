"""Execute CVID EDA in a fresh kernel; export HTML and bind completion receipt."""
from datetime import datetime, timezone
import asyncio
import json
import os
from pathlib import Path
import platform
import sys
import time

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from experiments.scripts.build_cvid_all_split_eda import build
from experiments.scripts.cvid_eda_common import OUT, ROOT, sha


def main():
    if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    OUT.mkdir(parents=True,exist_ok=True)
    for key,folder in [('JUPYTER_RUNTIME_DIR','jupyter-runtime'),('IPYTHONDIR','ipython'),('MPLCONFIGDIR','mpl-config')]:
        directory = OUT/folder; directory.mkdir(exist_ok=True)
        os.environ[key] = str(directory)
    source = build()
    notebook = nbformat.read(source,as_version=4)
    started = time.perf_counter(); start_utc=datetime.now(timezone.utc).isoformat()
    print('Executing fresh kernel:',source,flush=True)
    client = NotebookClient(notebook,timeout=1800,startup_timeout=45,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}},
        on_cell_start=lambda cell,cell_index:print('Cell',cell_index,cell.cell_type,flush=True))
    print('Driver interpreter:',sys.executable,flush=True)
    client.execute()
    nbformat.validate(notebook)
    nbformat.write(notebook,source)
    body,_ = HTMLExporter().from_notebook_node(notebook)
    html = OUT/'iiit-cvid-all-splits-eda.html'; html.write_text(body,encoding='utf-8')
    cells = [c for c in notebook.cells if c.cell_type=='code']
    outputs = [o for c in cells for o in c.get('outputs',[])]
    errors = [o for o in outputs if o.output_type=='error']
    if errors or any(c.execution_count is None for c in cells): raise ValueError('incomplete notebook execution')
    summary = json.loads((OUT/'eda-summary.json').read_text(encoding='utf-8'))
    receipt = dict(schema='cvid_all_split_eda_execution_v1',started_at_utc=start_utc,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started,
        fresh_kernel=True,python=platform.python_version(),code_cells=len(cells),executed_code_cells=len(cells),saved_errors=0,
        png_outputs=sum('image/png' in o.get('data',{}) for o in outputs),
        jpeg_outputs=sum('image/jpeg' in o.get('data',{}) for o in outputs),
        notebook=dict(path=source.relative_to(ROOT).as_posix(),sha256=sha(source),bytes=source.stat().st_size),
        html=dict(path=html.relative_to(ROOT).as_posix(),sha256=sha(html),bytes=html.stat().st_size),
        eda_summary=dict(path=(OUT/'eda-summary.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'eda-summary.json')),
        coverage=summary['coverage'],visual_pair_review=summary['visual_pair_review'],semantic_review=summary['semantic_review'],
        readiness=summary['readiness'],unresolved=summary['unresolved'])
    path = ROOT/'experiments/registry/datasets/iiit-cvid-all-splits-eda-261014.json'
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'execution-receipt.json').write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
