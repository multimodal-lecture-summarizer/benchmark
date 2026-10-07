"""Build the reproducible local dataset-readiness notebook (not an inference run)."""
from pathlib import Path

import nbformat


def build() -> Path:
    root = Path(__file__).resolve().parents[2]
    md, code = nbformat.v4.new_markdown_cell, nbformat.v4.new_code_cell
    cells = [md("""# Local dataset readiness: real EDA and independent split preparation

No model inference or downloads. Protocol and selected IDs are saved before decoding/screening. All similarity decisions are conservative preparation evidence, not proof of semantic uniqueness or scientific benchmark completion. Failed attempts are retained separately.
"""), code('''from pathlib import Path
from datetime import datetime, timezone
import os, sys, json, subprocess
import pandas as pd
from IPython.display import display, Markdown, Image
ROOT = Path.cwd()
assert (ROOT / "experiments/scripts").is_dir()
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RUN = ROOT / "experiments/outputs/dataset_readiness_260926" / STAMP
RUN.mkdir(parents=True)
BUNDLE = RUN / "bundle"
os.environ.update(HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONIOENCODING="utf-8")
commands = []
def command(args, accepted=(0,)):
    try:
        result = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=1200)
    except subprocess.TimeoutExpired as error:
        def readable(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
        entry = dict(command=args, exit_code=None, accepted=False, timeout_seconds=1200,
                     stdout=readable(error.stdout), stderr=readable(error.stderr))
        commands.append(entry)
        (RUN / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        print("TIMEOUT", args, entry["stdout"], entry["stderr"])
        raise
    entry = dict(command=args, exit_code=result.returncode, accepted=result.returncode in accepted, stdout=result.stdout, stderr=result.stderr)
    commands.append(entry)
    (RUN / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
    print("COMMAND", args, "EXIT", result.returncode)
    print(result.stdout)
    if result.stderr: print(result.stderr)
    return result
print("Execution output:", RUN)
'''), md("## Regression checks\nFixtures validate protocol decisions and integrity failures. These test counts do not measure model quality."), code('''command([sys.executable, "-m", "compileall", "-q", "experiments/scripts/dataset_readiness_selection.py", "experiments/scripts/dataset_readiness_screening.py", "experiments/scripts/dataset_readiness_figures.py", "experiments/scripts/run_dataset_readiness.py"])
command([sys.executable, "-m", "pytest", "-q", "tests/test_dataset_readiness_selection.py", "tests/test_dataset_readiness_screening.py", "tests/test_dataset_readiness_figures.py"])
command(["git", "diff", "--check"])
assert all(c["accepted"] for c in commands), "Regression checks failed; see outputs"
'''), md("## Local selection, extraction, similarity screening and measured EDA\nExit 3 means preparation is blocked; preserve diagnostics without treating it as scientific success."), code('''command([sys.executable, "-m", "experiments.scripts.run_dataset_readiness", "--output", str(BUNDLE)], accepted=(0, 3))
assert commands[-1]["accepted"], "Readiness execution failed; see captured logs"
'''), md("## Receipt verification and tables\nAll referenced bytes are checked before displaying them."), code('''from experiments.scripts.benchmark_artifacts import sha256_file
receipt = json.loads((BUNDLE / "bundle-receipt.json").read_text(encoding="utf-8"))
for item in receipt["files"]:
    path = (BUNDLE / item["path"]).resolve()
    path.relative_to(BUNDLE.resolve())
    assert sha256_file(path) == item["sha256"], item["path"]
print("Verified bundle files:", len(receipt["files"]))
summary = json.loads((BUNDLE / "summary.json").read_text(encoding="utf-8"))
display(pd.DataFrame(summary).T)
selection = json.loads((BUNDLE / "selection.json").read_text(encoding="utf-8"))
display(Markdown("Protocol fixed before extraction:"))
display(pd.json_normalize(json.loads((BUNDLE / "protocol.json").read_text(encoding="utf-8"))))
for dataset in summary:
    rows = json.loads((BUNDLE / dataset / "units.json").read_text(encoding="utf-8"))
    audit = json.loads((BUNDLE / dataset / "screening.json").read_text(encoding="utf-8"))
    display(Markdown(f"### {dataset}: {audit['status']}"))
    display(pd.DataFrame(rows).groupby(["split", "decision"]).size().rename("units").reset_index())
    display(pd.DataFrame(rows).head(10))
    display(Markdown(f"Similarity hits: {len(audit['pairs'])}; showing first 20. Full pair decisions are saved in screening.json."))
    display(pd.DataFrame(audit["pairs"][:20]))
    print("Blockers:", audit["blockers"])
'''), md("## Actual universal plots\nEight per dataset. Still-image duration is explicitly not applicable; it is never represented as zero duration."), code('''figure_count = 0
for dataset in summary:
    manifest = json.loads((BUNDLE / dataset / "figure-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 8
    for figure in manifest:
        path = Path(figure["path"])
        if not path.is_absolute(): path = BUNDLE / path
        path.resolve().relative_to(BUNDLE.resolve())
        assert sha256_file(path) == figure["sha256"]
        display(Markdown(f"**{dataset} — {figure['figure_id']}**"))
        display(Image(filename=str(path)))
        figure_count += 1
assert figure_count == 16
'''), md("## Historical preservation and conclusion"), code('''baseline = json.loads((ROOT.parent / "plans/260926-1651-dataset-readiness/historical-before.json").read_text(encoding="utf-8-sig"))
changed = [r["path"] for r in baseline if sha256_file(Path(r["path"])).lower() != r["sha256"].lower()]
print("Historical files:", len(baseline), "changed:", changed)
assert not changed
assert all(c["accepted"] for c in commands)
display(pd.DataFrame([{k:c[k] for k in ("command", "exit_code", "accepted")} for c in commands]))
print("Prepared cohorts are screened under the saved protocol. No model inference, candidate ranking, official D2 promotion or full-DAG completion is claimed.")
print("Bundle:", BUNDLE)
''')]
    for index, cell in enumerate(cells):
        cell.id = f"dataset-readiness-{index:02d}"
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.kernelspec = {"name": "python3", "display_name": "Python 3", "language": "python"}
    destination = root / "experiments/notebooks/diagnostics/dataset_readiness.ipynb"
    existing = nbformat.read(destination, as_version=4) if destination.is_file() else None
    if existing is None or [(c.cell_type, c.id, c.source) for c in existing.cells] != [
        (c.cell_type, c.id, c.source) for c in notebook.cells
    ]:
        nbformat.write(notebook, destination)
    return destination


if __name__ == "__main__":
    print(build())
