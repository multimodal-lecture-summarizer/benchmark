"""Append executed qualification evidence without rerunning historical EDA cells."""
import json
from pathlib import Path
import nbformat
import yaml
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
from traitlets.config import Config
from experiments.scripts.dataset_qualification_io import ROOT, OUT, sha

DATASETS = {
    'tedlium3':'tedlium3-full-corpus-asr',
    'iiit-cvid':'iiit-cvid-validation-ocr',
    'lvvo':'lvvo-four-class-detection',
    'mlpdataset':'mlpdataset-slide-transition',
    'accessmath':'accessmath-board-annotations',
    'lecturemath':'lecturemath-keyframe-annotations',
    'eduvidqa':'eduvidqa-official-annotations',
}
MARKER = 'qualification-followup-2026-10-10'


def section(dataset, snapshot, expected):
    # The embedded receipt is a portable saved snapshot, never a fresh media audit.
    return f'''from pathlib import Path
import json, hashlib
import pandas as pd
from IPython.display import display, Markdown, Image
saved = json.loads({json.dumps(snapshot, ensure_ascii=False)!r})
roots = [Path.cwd(), *Path.cwd().parents]
root = next((p for p in roots if (p / "experiments/notebooks/notebook_manifest.yaml").is_file()), None)
receipt_path = root / "experiments/outputs/dataset_qualification_261010/{dataset}-qualification-receipt.json" if root else None
if receipt_path is not None and receipt_path.is_file():
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == {expected!r}, "Receipt changed: review and regenerate this section."
    evidence = json.loads(receipt_path.read_text(encoding="utf-8"))
    display(Markdown("**Saved qualification receipt loaded and hash verified.** This cell does not decode media or run models."))
else:
    evidence = saved
    display(Markdown("**Embedded historical snapshot only:** local qualification files unavailable. This is not a new acquisition or audit."))
display(pd.DataFrame([evidence["counts"]]))
display(Markdown("**Status:** " + str(evidence.get("status", "HOLD; cohort not frozen"))))
details = {{k:v for k,v in evidence.items() if k not in {{"counts", "artifacts"}}}}
display(pd.DataFrame([{{"field":k, "value":json.dumps(v, ensure_ascii=False)}} for k,v in details.items()]))
for item in evidence.get("artifacts", []):
    relative = item["path"].replace("\\\\", "/")
    display(Markdown("Evidence: `" + relative + "` · SHA-256 `" + item["sha256"] + "`"))
    path = root / relative if root else None
    if path is None or not path.is_file():
        continue
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Evidence hash changed: " + relative
    if path.suffix == ".csv" and path.stat().st_size > 5:
        table = pd.read_csv(path)
        # Show decisions and coordinates; avoid exposing more answer/reference content.
        safe = [c for c in table.columns if c not in {{"reference_text", "question", "answer"}}]
        display(Markdown(str(len(table)) + " ledger rows; first 20 shown below. Full ledger remains linked above."))
        display(table[safe].head(20))
    elif path.name.endswith("geometry-contact-sheet.png"):
        display(Image(filename=str(path), width=1000))
display(Markdown("**No scientific cohort/protocol freeze. Native test references inspected in EDA cannot be described as unseen. Evaluated counts here refer to new model evaluations in this follow-up.**"))
'''


def main():
    register = {'review_date':'2026-10-10', 'cohort_frozen':False,
                'scientific_benchmark_cohorts':[], 'model_inference_run':False, 'datasets':[]}
    manifest_path = ROOT/'experiments/notebooks/notebook_manifest.yaml'
    manifest = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
    entries = []
    shell = InteractiveShell.instance(config=Config({'HistoryManager':{'hist_file':':memory:'}}))
    for dataset, stem in DATASETS.items():
        receipt_path = OUT/(dataset+'-qualification-receipt.json')
        snapshot = json.loads(receipt_path.read_text(encoding='utf-8'))
        expected = sha(receipt_path)
        path = ROOT/'experiments/notebooks/diagnostics'/(stem+'-eda.ipynb')
        notebook = nbformat.read(path, as_version=4)
        old_cells = [c for c in notebook.cells if MARKER not in c.metadata.get('tags', [])]
        markdown = nbformat.v4.new_markdown_cell(
            '## Qualification follow-up — 2026-10-10\n\n'
            'Earlier executed outputs are retained as historical evidence. This additive review supersedes '
            'their current availability/qualification statements where explicitly recorded in the receipt. '
            'KEEP and REPAIR are scoped record-quality decisions, not approval of a benchmark cohort.',
            metadata={'tags':[MARKER]})
        code = nbformat.v4.new_code_cell(section(dataset, snapshot, expected), metadata={'tags':[MARKER]})
        with capture_output() as captured:
            result = shell.run_cell(code.source, store_history=False)
        if not result.success:
            raise RuntimeError(f'Qualification cell failed for {dataset}: {result.error_in_exec or result.error_before_exec}')
        code.outputs = [nbformat.v4.new_output('display_data', data=item.data, metadata=item.metadata)
                        for item in captured.outputs]
        if captured.stdout:
            code.outputs.append(nbformat.v4.new_output('stream', name='stdout', text=captured.stdout))
        if captured.stderr:
            code.outputs.append(nbformat.v4.new_output('stream', name='stderr', text=captured.stderr))
        code.execution_count = max((c.get('execution_count') or 0 for c in old_cells), default=0)+1
        notebook.cells = old_cells+[markdown, code]
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
        entry = {'dataset':dataset, 'path':path.relative_to(ROOT).as_posix(),
                 'receipt':receipt_path.relative_to(ROOT).as_posix(), 'receipt_sha256':expected,
                 'executed_followup_cells':1, 'cohort_frozen':False, 'status':snapshot.get('status', 'HOLD')}
        entries.append(entry)
        register['datasets'].append({**entry, 'counts':snapshot['counts'], 'evidence':snapshot})
        print('Updated', dataset, flush=True)
    # EDA inventory is separate from the official benchmark execution DAG.
    manifest['dataset_eda_notebooks'] = entries
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding='utf-8')
    target = ROOT/'experiments/registry/datasets/qualification-261010.json'
    target.write_text(json.dumps(register, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
