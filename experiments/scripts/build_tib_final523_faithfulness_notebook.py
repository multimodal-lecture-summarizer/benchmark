"""Build the final523 MiniCheck faithfulness notebook and its code bundle (nothing is executed).

    python -m experiments.scripts.build_tib_final523_faithfulness_notebook
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import nbformat

from experiments.scripts.build_tib_p4e_notebooks import ROOT, code, environment_cell, md, notebook, sha256

NOTEBOOK_DIR = ROOT / "experiments/notebooks"
NOTEBOOK_NAME = "tib-final523-faithfulness-t4-261031-v1.ipynb"
OUTPUT_DIR = ROOT / "experiments/outputs/tib-final523-faithfulness-261031"
PROTOCOL = "experiments/registry/protocols/tib-final523-faithfulness-261031-v1/protocol.json"
BUNDLE_NAME = "tib-final523-faithfulness-code-261031-v1.zip"
DRIVE_FOLDER = "TIB_FINAL523_FAITH_261031"
SCORING_BUNDLE = "tib-final523-scoring-261024-v1.zip"
MINICHECK_PIN = "minicheck @ git+https://github.com/Liyan06/MiniCheck.git@b58b9fa69acbd1015ec970fa65dd752413a053d2"
CEILING_SECONDS = 6 * 3600
BUNDLE_FILES = [
    "experiments/scripts/tib_benchmark_output.py",
    "experiments/scripts/tib_budget_views.py",
    "experiments/scripts/tib_summary_constructors.py",
    "experiments/scripts/tib_pilot_faithfulness.py",
    "experiments/scripts/tib_final523_faithfulness.py",
    "tests/test_tib_final523_faithfulness.py",
    PROTOCOL,
]


def faithfulness_notebook() -> nbformat.NotebookNode:
    expected = sha256(ROOT / PROTOCOL)
    cells = [
        md(f'''
            # TIB final523: MiniCheck faithfulness of LED and BART (post-hoc secondary)

            Scores the already generated final523 outputs of LED and BART (1,042 scoreable cells; the 4 failed LED cells
            stay NULL) one sentence at a time against the source. No output is generated again and no reference text is
            read. Scope, metric, analysis and interpretation rule are fixed in `protocol.json` (hash-checked first). The
            result cannot change the final523 confirmatory label.

            **Choose a T4 GPU runtime.** Inputs (private; TIB source use is local/private/noncommercial), in Drive
            `MyDrive/{DRIVE_FOLDER}/`: the code bundle `{BUNDLE_NAME}` and the scoring bundle `{SCORING_BUNDLE}`.
            Every record is checkpointed to Drive: if the session drops, run the notebook again from the top and it
            resumes. Budget ceiling 6 GPU hours (estimate 3-5): the scoring cell stops at the ceiling; ask for more
            budget, never drop records.
        '''),
        code(f'''
            import hashlib, json, platform, subprocess, sys, time, zipfile
            from pathlib import Path

            IN_COLAB = "google.colab" in sys.modules
            if IN_COLAB:
                from google.colab import drive
                drive.mount("/content/drive")
                DRIVE_DIR = Path("/content/drive/MyDrive/{DRIVE_FOLDER}")
                ROOT = Path("/content/final523_faith"); ROOT.mkdir(exist_ok=True)
                with zipfile.ZipFile(DRIVE_DIR / "{BUNDLE_NAME}") as bundle:
                    bundle.extractall(ROOT)
                SCORING_ZIP = DRIVE_DIR / "{SCORING_BUNDLE}"
                OUT_DIR = DRIVE_DIR / "results"
            else:
                here = Path.cwd()
                ROOT = next(p for p in [here, *here.parents] if (p / "experiments/scripts/tib_final523_faithfulness.py").exists())
                SCORING_ZIP = ROOT / "research-data/tib-final523-scoring-261024-v1/{SCORING_BUNDLE}"
                OUT_DIR = ROOT / "research-data/tib-final523-faithfulness-261031-v1"  # private, like the Pilot40 detail
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            sys.path.insert(0, str(ROOT))
            assert SCORING_ZIP.exists(), f"Missing input: {{SCORING_ZIP}}"

            PROTOCOL_PATH = ROOT / "{PROTOCOL}"
            EXPECTED_PROTOCOL_SHA256 = "{expected}"
            actual = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
            assert actual == EXPECTED_PROTOCOL_SHA256, (
                f"Protocol hash {{actual}} differs from the notebook's {{EXPECTED_PROTOCOL_SHA256}}: the code zip in Drive "
                "is probably an older build. Upload the latest {BUNDLE_NAME}, restart the session and run again. "
                "Do not edit the protocol.")
            SCORING_ZIP_SHA256 = hashlib.sha256(SCORING_ZIP.read_bytes()).hexdigest()
            print("protocol sha256 verified:", actual[:16], "... scoring bundle:", SCORING_ZIP_SHA256[:16], "...")
        '''),
        environment_cell(),
        code('''
            import torch
            assert torch.cuda.is_available(), "Select a GPU runtime (T4)"
            ENVIRONMENT["gpu"] = torch.cuda.get_device_name(0)
            print(ENVIRONMENT["gpu"], torch.__version__)
        '''),
        md("## Install MiniCheck (pinned commit)"),
        code(f'''
            INSTALL_LOG = {{}}
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "{MINICHECK_PIN}"],
                                    capture_output=True, text=True)
            INSTALL_LOG["MiniCheck"] = {{"returncode": result.returncode, "tail": (result.stderr or result.stdout)[-400:]}}
            assert result.returncode == 0, INSTALL_LOG["MiniCheck"]["tail"]
            import nltk  # recent NLTK needs punkt_tab, which MiniCheck does not download
            for resource in ("punkt", "punkt_tab"):
                nltk.download(resource, quiet=True)
            print("MiniCheck installed")
        '''),
        md("## Load the final523 outputs (hash-checked)"),
        code('''
            from collections import Counter
            from experiments.scripts import tib_final523_faithfulness as ff
            ROWS, SKIPPED = ff.collect_rows(SCORING_ZIP)
            print("to score:", dict(Counter(r["candidate"] for r in ROWS)))
            print("not scoreable (kept as NULL):", [(s["candidate"], s["record_id"]) for s in SKIPPED])
            assert len(ROWS) == 1042 and len(SKIPPED) == 4, "cell counts differ from the protocol"
        '''),
        md('''
            ## Score (checkpointed; run again to resume)
            Records are scored in a fixed spread order, so the first 10 cover both profiles and all source lengths. After
            them the cell projects the total time and stops if the projection exceeds the ceiling. Error rows are
            retried on the next run. No score is printed here: the contrast is computed locally after the hand-review
            sample is drawn.
        '''),
        code(f'''
            from datetime import datetime, timezone
            score_claims, MINICHECK_INFO = ff.load_minicheck_claims()
            MINICHECK_INFO["install"] = "{MINICHECK_PIN}"
            CHECKPOINT = OUT_DIR / "final523_faithfulness_scores.jsonl"
            DETAIL_PATH = OUT_DIR / "PRIVATE_final523_sentence_scores.jsonl"  # sentence text: keep private
            SPENT_PATH = OUT_DIR / "scoring_seconds.json"  # cumulative over sessions, for the budget ceiling
            CEILING = {CEILING_SECONDS}
            state = json.loads(SPENT_PATH.read_text()) if SPENT_PATH.exists() else {{
                "seconds": 0.0, "records": 0, "first_score_utc": datetime.now(timezone.utc).isoformat()}}
            started, spent_before, records_before = time.monotonic(), state["seconds"], state["records"]
            ORDER = sorted(range(len(ROWS)), key=lambda i: (i * 7919) % len(ROWS))  # deterministic spread
            ROWS_SPREAD = [ROWS[i] for i in ORDER]

            class CeilingReached(Exception):
                pass

            def progress(scored, count=[0]):
                count[0] += 1
                state["seconds"] = spent_before + time.monotonic() - started
                state["records"] = records_before + count[0]
                SPENT_PATH.write_text(json.dumps(state))
                per_record = state["seconds"] / state["records"]
                if count[0] % 25 == 0:
                    print(count[0], "new records,", round(state["seconds"] / 3600, 2), "GPU h in total")
                if state["records"] == 10:
                    projection = per_record * len(ROWS)
                    print("smoke: %.1f s per record, projected %.2f GPU h for all %d" % (per_record, projection / 3600, len(ROWS)))
                    if projection > CEILING:
                        raise CeilingReached(f"projected {{projection / 3600:.2f}} h exceeds the ceiling")
                if state["seconds"] + per_record > CEILING:
                    raise CeilingReached(f"the next record would pass the ceiling at {{state['seconds'] / 3600:.2f}} h")

            try:
                RESULTS = ff.score_rows(ROWS_SPREAD, score_claims, CHECKPOINT, DETAIL_PATH, on_row=progress)
            except CeilingReached as stop:
                raise SystemExit(f"{{stop}}. Every scored record is checkpointed. Ask for more budget, then run again.")
            errors = [r for r in RESULTS if "views" not in r]
            print("records:", len(RESULTS), "errors:", len(errors), "total GPU h:", round(state["seconds"] / 3600, 2))
            assert not errors, f"{{len(errors)}} error rows ({{errors[0]['error']}}): restart the runtime and run again to retry them"
        '''),
        md("## Receipt (no sentence text, no score table)"),
        code('''
            receipt = {
                "schema_version": 1, "protocol_id": ff.PROTOCOL_ID, "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                "scoring_bundle": SCORING_ZIP.name, "scoring_bundle_sha256": SCORING_ZIP_SHA256,
                "first_score_utc": state["first_score_utc"], "receipt_written_utc": datetime.now(timezone.utc).isoformat(),
                "environment": ENVIRONMENT, "install_log": INSTALL_LOG, "minicheck": MINICHECK_INFO,
                "scoring_seconds_total": state["seconds"], "skipped": SKIPPED,
                "scores": sorted(RESULTS, key=lambda r: (r["candidate"], r["record_id"])),
                "sentence_detail_file": DETAIL_PATH.name,
            }
            path = OUT_DIR / "final523_faithfulness_receipt.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(path, hashlib.sha256(path.read_bytes()).hexdigest())
            print("C_final:", len(ff.common_ids(RESULTS)), "expected", ff.EXPECTED_C_FINAL)
        '''),
        md('''
            ## What to send back
            `final523_faithfulness_receipt.json` (record scores, environment; no sentence text) and the executed notebook.
            `PRIVATE_final523_sentence_scores.jsonl` holds summary sentences derived from private sources: download it to
            the local machine only, never into the repository. The contrast, the hand review and the interpretation rule
            run locally from these two files (`tib_final523_faithfulness.analyze`).
        '''),
    ]
    return notebook(cells)


def build_bundle() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / BUNDLE_NAME
    manifest = {name: sha256(ROOT / name) for name in BUNDLE_FILES}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in BUNDLE_FILES:
            bundle.write(ROOT / name, name)
        bundle.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
    return path


def main() -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    nbformat.write(faithfulness_notebook(), NOTEBOOK_DIR / NOTEBOOK_NAME)
    print("wrote", NOTEBOOK_DIR / NOTEBOOK_NAME)
    bundle = build_bundle()
    print("wrote", bundle, sha256(bundle))


if __name__ == "__main__":
    main()
