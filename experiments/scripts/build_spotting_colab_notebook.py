"""Generate an unexecuted Colab T4 notebook bound to a self-contained source ZIP."""
from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path

from experiments.scripts.spotting_colab_bundle import DEFAULT, ROOT, build as build_bundle

NOTEBOOK = ROOT / "experiments/notebooks/iiit-cvid-spotting-colab-t4.ipynb"


def cell(kind, source):
    # Triple-quoted source starts on the opening line; align it with its body.
    source = textwrap.dedent("    " + source).strip() + "\n"
    result = dict(cell_type=kind, metadata={}, source=source.splitlines(True))
    if kind == "code":
        ast.parse(source)
        result.update(execution_count=None, outputs=[])
    return result


def build(bundle=None, destination=NOTEBOOK):
    bundle = bundle or build_bundle()
    cells = []
    def md(value): cells.append(cell("markdown", value))
    def code(value): cells.append(cell("code", value))
    md('''# CVID spotting — Colab T4, weights/config bound, resumable evidence

    **1.754 test frames / 40.063 released XML objects.** Five primary pipelines:
    EasyOCR, PaddleOCR v3/v4, Tesseract, docTR FAST/PARSeq, PP-OCRv6 medium.
    TESTR is conditional: installation, actual model loading and train-image polygon/text
    forward pass must succeed before any TESTR test inference. Failed eligibility is retained.

    This notebook is prepared, **not executed on Colab**. No T4/TESTR verification claim exists yet.
    Select Runtime → Change runtime type → T4 GPU. Tesseract runs on CPU.
    Model environments are isolated; original CPU results/checkpoints are never imported.
    Do not tune thresholds, retry failures with another config, or change grouping on test.
    Native grouping differs: results compare packaged systems, not causal architecture effects.

    Test was exposed in EDA; annotations are selective and not certified gold.
    Hmean measures released-label agreement, not exhaustive visible-text correctness.
    Use the same RUN_ID to resume an identical sealed run, a new ID for any change.
    Never run two notebooks against the same output directory.
    ''')
    code('''from pathlib import Path
    import sys, os, json, subprocess, hashlib, zipfile, shutil
    from google.colab import drive, files
    drive.mount('/content/drive')
    DRIVE_ROOT = Path('/content/drive/MyDrive/OCR')  # explicit persistent destination
    RUN_ID = 'cvid-spotting-t4-261015-v1'
    BUNDLE_ZIP = DRIVE_ROOT / 'iiit-cvid-spotting-colab-t4-inputs.zip'
    SOURCE_ZIP = None  # optional existing source ZIP path on Drive; otherwise pinned HF download
    WORK = Path('/content/cvid-spotting-t4')
    ROOT = WORK / 'runner'
    OUT = DRIVE_ROOT / RUN_ID
    # Keep exact wheels and package seals across Colab VM loss, outside evidence ZIP.
    os.environ['SPOTTING_CACHE_ROOT'] = str(DRIVE_ROOT / (RUN_ID + '-runtime-cache'))
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,uuid,memory.total,driver_version',
                          '--format=csv,noheader'], check=True, text=True, capture_output=True)
    print(gpu.stdout)
    if 'T4' not in gpu.stdout:
        raise RuntimeError('This profile requires a T4. Select T4 and restart; do not reuse another GPU profile.')
    ''')
    md('''## 1. Verify portable runner before executing its code
    Upload the matching ZIP to DRIVE_ROOT (or change BUNDLE_ZIP). No GitHub clone is needed.
    Its expected SHA is embedded below. Every member is checked before extraction.
    ''')
    code(f'''EXPECTED_BUNDLE_SHA256 = {bundle['sha256']!r}
    def file_sha(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                h.update(block)
        return h.hexdigest()
    if not BUNDLE_ZIP.is_file():
        raise FileNotFoundError(f'Place the matching portable bundle at {{BUNDLE_ZIP}}')
    if file_sha(BUNDLE_ZIP) != EXPECTED_BUNDLE_SHA256:
        raise ValueError('Bundle hash differs from this notebook. Use the matching notebook/ZIP pair.')
    from pathlib import PurePosixPath
    with zipfile.ZipFile(BUNDLE_ZIP) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        for name in names:
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or '\\\\' in name or ':' in name:
                raise ValueError('Unsafe ZIP member')
        manifest = json.loads(archive.read('bundle-manifest.json'))
        entries = manifest['files']
        if len(entries) != len({{e['path'] for e in entries}}) or set(names) != {{e['path'] for e in entries}} | {{'bundle-manifest.json'}}:
            raise ValueError('Bundle membership changed')
        for entry in entries:
            value = archive.read(entry['path'])
            if len(value) != entry['bytes'] or hashlib.sha256(value).hexdigest() != entry['sha256']:
                raise ValueError('Bundle file changed: ' + entry['path'])
        # Use a fresh source directory to avoid stale modules outside the manifest.
        if ROOT.exists():
            shutil.rmtree(ROOT)
        archive.extractall(ROOT)
    sys.path.insert(0, str(ROOT))
    print('Verified bundle files:', len(entries))
    ''')
    md('''## 2. Isolated orchestrator and pinned dataset acquisition
    The live Colab kernel's NumPy/Pandas stack is not replaced. A Python 3.11 orchestrator
    performs acquisition/scoring; every model gets its own environment. Installation errors
    block that environment and do not count as successful model verification.
    ''')
    code('''subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'uv==0.6.17'], check=True)
    UV = [sys.executable, '-m', 'uv']
    ORCHESTRATOR = WORK / 'orchestrator'
    if not (ORCHESTRATOR / 'bin/python').exists():
        subprocess.run(UV + ['venv', '--python', '3.11.11', '--seed', str(ORCHESTRATOR)], check=True)
    PYTHON = ORCHESTRATOR / 'bin/python'
    subprocess.run(UV + ['pip', 'install', '--python', str(PYTHON),
        'numpy==1.26.4', 'Pillow==11.1.0', 'shapely==2.0.7', 'pandas==2.2.3',
        'matplotlib==3.10.1', 'huggingface_hub==0.30.2', 'uv==0.6.17'], check=True)
    ARCHIVE = Path(SOURCE_ZIP) if SOURCE_ZIP else WORK / 'IIIT-CVid.zip'
    if not ARCHIVE.exists():
        download_script = """from huggingface_hub import hf_hub_download, list_repo_files
    import shutil, sys
    repo = 'staghado/IIIT-CVid'
    revision = '8159222f11460bff70bec7990ade19c468755fe4'
    choices = [p for p in list_repo_files(repo, repo_type='dataset', revision=revision) if p.endswith('.zip')]
    assert len(choices) == 1, choices
    cached = hf_hub_download(repo, choices[0], repo_type='dataset', revision=revision)
    shutil.copyfile(cached, sys.argv[1])
    """
        subprocess.run([str(PYTHON), '-c', download_script, str(ARCHIVE)], check=True)
    if file_sha(ARCHIVE) != 'b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489':
        raise ValueError('Source archive differs from frozen CVID release')
    BASE = [str(PYTHON), '-m', 'experiments.scripts.run_spotting_colab',
            '--bundle-root', str(ROOT), '--work-root', str(WORK), '--output-root', str(OUT),
            '--source-zip', str(ARCHIVE)]
    def cli(command, candidate=None, check=True):
        args = BASE + [command]
        if candidate:
            args += ['--candidate', candidate]
        return subprocess.run(args, cwd=ROOT, check=check)
    cli('prepare')
    ''')
    md('''## 3. Train-only runtime preflight and eligibility
    Preflight uses fixed train images, not test scores. It must load the exact weights and
    return genuine box + transcription predictions. TESTR remains excluded until this gate passes.
    Failed candidate receipts remain on Drive. Inspect status before running test inference.
    ''')
    code("""cli('preflight', check=False)
    cli('status')
    """)
    md('''## 4. Full frozen cohort with immutable per-frame checkpoints
    The runner admits only sealed candidates. Resume checks identities before reusing records.
    GPU execution is a new profile; no old CPU checkpoints are merged. Missing/failed frames
    retain their GT denominator. A Colab disconnect may require rerunning setup and this cell.
    A failed primary candidate blocks the complete five-pipeline comparison.
    ''')
    code("""cli('run')
    cli('status')
    """)
    md('''## 5. Scoring, sensitivity, visual evidence
    Primary: pooled end-to-end Hmean. Secondary: detection precision/recall/F1, coverage,
    failures, per-course breakdown and fixed sensitivity variants. Same predictions are reused
    for sensitivity; no test tuning. Seven course clusters limit generalization.
    TESTR inclusion requires its successful sealed preflight and full same-cohort predictions.
    ''')
    code("""cli('analyze')
    subprocess.run([str(PYTHON), '-m', 'pip', 'check'], check=True)
    subprocess.run([str(PYTHON), '-c',
        'from experiments.scripts.spotting_colab_notebook import render_figures; import sys; render_figures(sys.argv[1])',
        str(OUT)], cwd=ROOT, check=True)
    from experiments.scripts.spotting_colab_notebook import display_results
    display_results(OUT)
    """)
    md('''## 6. Export receipts, checkpoints and results
    This cell also works after interrupted inference: exported status remains partial.
    A ZIP export is not proof of completion; analysis-summary and seals determine that status.
    Save this notebook with outputs separately in Colab. The exported ZIP contains all runner outputs.
    ''')
    code("""from experiments.scripts.spotting_colab_notebook import export_evidence
    exported = export_evidence(OUT)
    print(json.dumps(exported, indent=2))
    files.download(exported['path'])
    """)
    notebook = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"name": destination.name},
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 5}
    for index, item in enumerate(cells):
        item["id"] = f"cvid-t4-{index:02d}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"notebook": str(destination), "code_cells": sum(c['cell_type']=='code' for c in cells),
            "executed": False, "bundle": bundle}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
