"""Complete notebook displays and hash-bound visual evidence, separate from inference."""
import io
import json
import sys
from importlib.metadata import version
from pathlib import Path

from IPython.display import HTML, Image as NotebookImage, Markdown, display
import matplotlib.pyplot as plt
import matplotlib as mpl

from experiments.scripts.spotting_candidate_contract import ROOT, sha
from experiments.scripts.spotting_comparison_io_v2 import OUT, write_bytes_once, write_once
from experiments.scripts.spotting_runtime_binding import read_json, require


def table(frame, name):
    """Render every row and full string; HTML escapes all model/GT text."""
    content = frame.to_html(index=False, escape=True, max_rows=None, max_cols=None,
                            na_rep='', border=0)
    path = OUT/'tables'/(name+'.html')
    write_bytes_once(path, content.encode('utf-8'))
    display(HTML(content))


def figure(fig, name):
    folder = OUT/'figures'; folder.mkdir(parents=True, exist_ok=True)
    # Metadata avoids wall-clock timestamps in vector exports on replay.
    with mpl.rc_context({'svg.hashsalt':'cvid-test-spotting-261014-v2'}):
        for suffix in ('png', 'svg'):
            path = folder/(name+'.'+suffix)
            stream = io.BytesIO()
            fig.savefig(stream, format=suffix, dpi=150,
                        metadata={'Date': None} if suffix=='svg' else {}, bbox_inches='tight')
            write_bytes_once(path, stream.getvalue())
    display(NotebookImage(filename=str(folder/(name+'.png'))))
    plt.close(fig)


def galleries(data, output):
    from experiments.scripts.spotting_comparison_gallery import render_galleries
    return render_galleries(data, output)


def finish_display(output, analysis, gallery_receipt):
    output = Path(output)
    import pandas as pd
    macro=pd.read_csv(output/'macro-course-means.csv',keep_default_na=False)
    require(len(macro)==16 and macro.courses.eq(7).all(), 'incomplete course means')
    display(Markdown('**Unweighted course means (7 courses)** — chỉ số phụ; mỗi course có trọng số bằng nhau. Chỉ số chính ở trên pool toàn bộ TP/FP/FN.'))
    table(macro,'all-unweighted-course-means')
    for item in analysis['artifacts'].values():
        # Analysis exports use repository-relative paths.
        path = ROOT/item['path']
        require(sha(path)==item['sha256'], 'analysis export changed before display receipt')
    figures = sorted((output/'figures').glob('*'))
    tables = sorted((output/'tables').glob('*.html'))
    require(len([p for p in figures if p.suffix=='.png'])==8, 'eight scientific figures required')
    require(len(tables)>=7, 'incomplete full notebook tables')
    require(gallery_receipt['predeclared_frames']>=14, 'incomplete predeclared gallery')
    def entry(path):
        return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), bytes=path.stat().st_size)
    identity=read_json(output/'run-identity.json')
    attempts=[]
    candidate_rows=[]
    for candidate in identity['candidate_order']:
        folder=output/candidate/'attempts'
        files=sorted(p for p in folder.rglob('*') if p.is_file())
        require(any(p.name=='loaded-runtime.json' for p in files), 'missing actual loading evidence')
        require(any(p.name=='worker-complete.json' for p in files), 'missing worker completion evidence')
        loaded=read_json(next(p for p in files if p.name=='loaded-runtime.json'))
        native=loaded['identity']
        candidate_rows.append(dict(candidate_id=candidate,runtime_identity_sha256=loaded['runtime_identity_sha256'],
            configuration_sha256=native['configuration_sha256'],
            model_sha256=json.dumps(native['model_sha256'],ensure_ascii=False,sort_keys=True),
            basic_runtime=json.dumps(loaded['basic'],ensure_ascii=False,sort_keys=True),
            frozen_call_config=json.dumps(native['effective'].get('call_config',{}),ensure_ascii=False,sort_keys=True)))
        attempts.extend(entry(p) for p in files)
    display(Markdown('**Actual loaded candidate identities** — đối chiếu với runtime đã khóa; full settings và binary/source hashes được giữ trong loaded-runtime receipts.'))
    table(pd.DataFrame(candidate_rows),'actual-locked-candidate-identities')
    attempt_manifest=output/'attempt-evidence-manifest.json'
    write_once(attempt_manifest,dict(run_id=identity['run_id'],artifacts=attempts,
        description='All loading, launch, exit, stdout/stderr, timeout and worker completion files after full inference.'))
    tables=sorted((output/'tables').glob('*.html'))
    paths=figures+tables+[ROOT/item['path'] for item in gallery_receipt['artifacts']]
    result=dict(schema='iiit_cvid_spotting_full_display_v1', full_text_frames=1754,
        figure_count=8, table_count=len(tables), gallery_count=gallery_receipt['gallery_count'],
        analysis_summary=entry(output/'analysis-summary.json'),
        attempt_evidence=entry(attempt_manifest),
        gallery_decisions=entry(output/'gallery-receipt.json'), artifacts=[entry(p) for p in paths],
        display_runtime=dict(python=sys.version,packages={name:version(name) for name in
            ('matplotlib','numpy','pandas','Pillow','ipython','nbformat','nbclient','nbconvert')}),
        implementation={name:sha(Path(__file__).with_name(name)) for name in
            ('spotting_comparison_notebook.py','spotting_comparison_gallery.py','spotting_comparison_plots.py')})
    write_once(output/'display-receipt.json', result)
    return result
