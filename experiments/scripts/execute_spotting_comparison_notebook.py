"""Execute real full-test notebook in a fresh kernel; preserve interrupted evidence."""
import asyncio
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from experiments.scripts.build_spotting_comparison_notebook import PATH,build
from experiments.scripts.spotting_comparison_io_v2 import OUT,write_once
from experiments.scripts.spotting_candidate_contract import ROOT,sha


def main():
    if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    OUT.mkdir(parents=True,exist_ok=True)
    if PATH.exists():
        prior=nbformat.read(PATH,as_version=4)
        if any(c.get('execution_count') is not None for c in prior.cells if c.cell_type=='code'):
            history=OUT/'notebook-history';history.mkdir(exist_ok=True)
            shutil.copy2(PATH,history/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.ipynb'))
    source=build();notebook=nbformat.read(source,as_version=4)
    for key,folder in [('JUPYTER_RUNTIME_DIR','jupyter-runtime'),('IPYTHONDIR','ipython'),('MPLCONFIGDIR','mpl-config')]:
        directory=OUT/folder;directory.mkdir(exist_ok=True);os.environ[key]=str(directory)
    def start(cell,cell_index): print('Cell',cell_index,cell.cell_type,flush=True)
    def saved(**kwargs): nbformat.write(notebook,source)
    client=NotebookClient(notebook,timeout=None,startup_timeout=45,kernel_name='python3',
        resources={'metadata':{'path':str(ROOT)}},on_cell_start=start,on_cell_executed=saved)
    clock=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    print('Fresh kernel execution; inference cell timeout=None; driver',sys.executable,flush=True)
    try: client.execute()
    finally: nbformat.write(notebook,source)
    nbformat.validate(notebook)
    cells=[c for c in notebook.cells if c.cell_type=='code'];outputs=[o for c in cells for o in c.get('outputs',[])]
    require=all(c.execution_count is not None for c in cells) and not any(o.output_type=='error' for o in outputs)
    if not require: raise ValueError('incomplete/error notebook execution')
    body,_=HTMLExporter().from_notebook_node(notebook);html=OUT/'iiit-cvid-test-spotting-comparison.html';html.write_text(body,encoding='utf-8')
    def entry(path): return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size)
    receipt=dict(schema='iiit_cvid_full_test_spotting_notebook_execution_v1',started_at_utc=started,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-clock,
        fresh_kernel=True,code_cells=len(cells),executed_code_cells=len(cells),saved_errors=0,
        png_outputs=sum('image/png' in o.get('data',{}) for o in outputs),jpeg_outputs=sum('image/jpeg' in o.get('data',{}) for o in outputs),
        notebook=entry(source),html=entry(html),inference=entry(OUT/'inference-complete.json'),
        analysis=entry(OUT/'analysis-summary.json'),display=entry(OUT/'display-receipt.json'),
        frame_inference_executed=True,selected_frames=1754,selected_objects=40063,
        execution_implementation={n:sha(Path(__file__).with_name(n)) for n in ('execute_spotting_comparison_notebook.py','build_spotting_comparison_notebook.py')})
    write_once(OUT/'execution-receipt.json',receipt)
    target=ROOT/'experiments/registry/datasets/iiit-cvid-test-spotting-comparison-261014-v2.json'
    write_once(target,receipt)
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__': main()
