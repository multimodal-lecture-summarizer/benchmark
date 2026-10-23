"""Build the two P4e notebooks and their code bundle (nothing is executed).

    python -m experiments.scripts.build_tib_p4e_notebooks
"""
from __future__ import annotations

import hashlib
import json
import textwrap
import zipfile
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = ROOT / "experiments/notebooks"
OUTPUT_DIR = ROOT / "experiments/outputs/tib-p4e-261022"
PROTOCOL = "experiments/registry/protocols/tib-reference-free-multilength-261022-v1"
BUNDLE_NAME = "tib-p4e-code-261022-v1.zip"
BUNDLE_FILES = [
    "experiments/scripts/tib_benchmark_output.py",
    "experiments/scripts/tib_budget_views.py",
    "experiments/scripts/tib_summary_constructors.py",
    "experiments/scripts/tib_faithfulness_cost.py",
    "experiments/scripts/tib_pilot_faithfulness.py",
    "tests/test_tib_faithfulness_cost.py",
    "tests/test_tib_pilot_faithfulness.py",
    "tests/test_tib_benchmark_output.py",
    f"{PROTOCOL}/crossfamily_criteria.json",
    f"{PROTOCOL}/pilot_faithfulness_protocol.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code(source: str):
    return nbformat.v4.new_code_cell(textwrap.dedent(source).strip("\n"))


def md(source: str):
    return nbformat.v4.new_markdown_cell(textwrap.dedent(source).strip("\n"))


def setup_cell(criteria_name: str, expected_sha: str):
    return code(f'''
        import hashlib, json, platform, subprocess, sys, time, zipfile
        from pathlib import Path

        IN_COLAB = "google.colab" in sys.modules
        if IN_COLAB:
            from google.colab import drive
            drive.mount("/content/drive")
            DRIVE_DIR = Path("/content/drive/MyDrive/TIB_P4E_261022")  # private folder with the two input files
            ROOT = Path("/content/p4e"); ROOT.mkdir(exist_ok=True)
            with zipfile.ZipFile(DRIVE_DIR / "{BUNDLE_NAME}") as bundle:
                bundle.extractall(ROOT)
            RECORDS_PATH = DRIVE_DIR / "canonical_records.jsonl.gz"
            OUT_DIR = DRIVE_DIR / "results"
        else:
            here = Path.cwd()
            ROOT = next(p for p in [here, *here.parents] if (p / "experiments/scripts/tib_faithfulness_cost.py").exists())
            RECORDS_PATH = ROOT / "research-data/tib-qualification-261019-1703/eda/canonical_records.jsonl.gz"
            OUT_DIR = ROOT / "experiments/outputs/tib-p4e-261022"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(ROOT))
        assert RECORDS_PATH.exists(), f"Missing input: {{RECORDS_PATH}}"

        CRITERIA = ROOT / "{PROTOCOL}/{criteria_name}"
        EXPECTED_CRITERIA_SHA256 = "{expected_sha}"
        actual = hashlib.sha256(CRITERIA.read_bytes()).hexdigest()
        assert actual == EXPECTED_CRITERIA_SHA256, (
            f"Criteria file hash {{actual}} differs from the notebook's {{EXPECTED_CRITERIA_SHA256}}. "
            "Usually the code zip in Drive is an older build: upload the latest {BUNDLE_NAME}, "
            "replace the old one, then Runtime > Restart session and run again. Do not edit the criteria file.")
        print("root:", ROOT)
        print("records:", RECORDS_PATH)
        print("criteria sha256 verified:", actual[:16], "...")
    ''')


def environment_cell():
    return code('''
        import importlib.metadata as md_
        def version(name):
            try:
                return md_.version(name)
            except md_.PackageNotFoundError:
                return None
        ENVIRONMENT = {
            "python": platform.python_version(), "platform": platform.platform(),
            "packages": {n: version(n) for n in ["nltk", "scikit-learn", "scipy", "numpy", "pandas", "torch", "transformers"]},
            "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((ROOT / "experiments/scripts").glob("tib_*.py"))},
        }
        print(json.dumps(ENVIRONMENT["packages"], indent=1))
    ''')


def faithfulness_notebook() -> nbformat.NotebookNode:
    expected = sha256(ROOT / PROTOCOL / "crossfamily_criteria.json")
    cells = [
        md('''
            # TIB P4e: faithfulness families and scoring cost on Colab T4

            Pre-registered checks (`crossfamily_criteria.json`): which entailment-based faithfulness families
            separate source-extract summaries from off-topic and corrupted ones, whether the families agree
            with each other, and what scoring costs on a T4. Uses 60 train sources x 5 mechanically built
            summaries (300 summaries). No reference text and no generation model. Only published packages
            are used; nothing here is a self-made metric.

            **Choose a T4 GPU runtime.** Inputs (private; TIB source use is local/private/noncommercial): `canonical_records.jsonl.gz` and the code bundle zip,
            in Drive `MyDrive/TIB_P4E_261022/` on Colab, or the repository paths when run locally. The third-party packages are installed
            from their public repositories at run time; the installed versions and checkpoint names are written
            to the receipt and become the pins. This notebook was written against the packages' documented APIs
            and has not been executed yet: a family that fails to load is reported, not replaced.
        '''),
        setup_cell("crossfamily_criteria.json", expected),
        environment_cell(),
        code('''
            import torch
            assert torch.cuda.is_available(), "Select a GPU runtime (T4)"
            GPU = torch.cuda.get_device_name(0)
            print(GPU, torch.__version__)
            ENVIRONMENT["gpu"] = GPU
        '''),
        md('''
            ## Install the families
            SummaC is skipped by default because it pins older libraries that can break the others; set
            `TRY_SUMMAC = True` and run in a fresh runtime to try it. If pip changes numpy or transformers,
            restart the runtime and run the notebook again from the top (the cells are repeatable).
        '''),
        code('''
            TRY_SUMMAC = False
            INSTALL_LOG = {}
            def pip(label, *args):
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", *args], capture_output=True, text=True)
                INSTALL_LOG[label] = {"returncode": result.returncode, "tail": (result.stderr or result.stdout)[-400:]}
                print(label, "ok" if result.returncode == 0 else "FAILED")
                if result.returncode:
                    print("   ", INSTALL_LOG[label]["tail"])
            pip("AlignScore", "git+https://github.com/yuh-zha/AlignScore.git")
            if INSTALL_LOG["AlignScore"]["returncode"]:
                # AlignScore pins torch<2, which Colab cannot satisfy; try the package without its pins.
                pip("AlignScore-no-deps", "--no-deps", "git+https://github.com/yuh-zha/AlignScore.git")
                pip("AlignScore-runtime-deps", "pytorch-lightning", "sentencepiece")
            pip("spacy-model", "spacy")
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], capture_output=True)
            pip("MiniCheck", "minicheck @ git+https://github.com/Liyan06/MiniCheck.git@main")
            import nltk  # recent NLTK needs punkt_tab, which MiniCheck does not download
            for resource in ("punkt", "punkt_tab"):
                nltk.download(resource, quiet=True)
            if TRY_SUMMAC:
                pip("SummaC", "summac")
            else:
                INSTALL_LOG["SummaC"] = {"skipped": True}
        '''),
        md("## Build the 300 summaries"),
        code('''
            import random, statistics
            from experiments.scripts import tib_summary_constructors as build
            from experiments.scripts import tib_faithfulness_cost as fc
            criteria = fc.load_criteria()
            records = build.load_train_sources(RECORDS_PATH)
            full_sample = build.draw_sample(records, 70)
            subset = fc.select_subset(full_sample, 20)
            ROWS = fc.build_rows(subset, full_sample, criteria["data"]["budget_view_words"], 20261022)
            print(len(records), "train sources,", len(subset), "records,", len(ROWS), "summaries")
        '''),
        md("## Score with each family\nThe first three summaries of each family are warm-up and excluded from the timing."),
        code('''
            families, load_errors = fc.load_families(["AlignScore", "MiniCheck"] + (["SummaC"] if TRY_SUMMAC else []))
            print("available:", list(families)); print("unavailable:", load_errors)
            import traceback
            SCORES, TIMING, FAMILY_INFO, ROW_ERRORS = {}, {}, {}, {}
            for name, (score_fn, info) in families.items():
                torch.cuda.reset_peak_memory_stats()
                scores, times, errors = [], [], 0
                for i, row in enumerate(ROWS):
                    if i == 5 and errors == 5:
                        print(name, "failed on the first 5 summaries; stopping this family. First error:")
                        print(ROW_ERRORS[name])
                        scores += [None] * (len(ROWS) - len(scores)); break
                    torch.cuda.synchronize(); t0 = time.perf_counter()
                    try:
                        value = score_fn(row["source"], row["summary"])
                    except Exception as exc:
                        value, errors = None, errors + 1
                        ROW_ERRORS.setdefault(name, traceback.format_exc()[-1500:])
                    torch.cuda.synchronize(); elapsed = time.perf_counter() - t0
                    scores.append(value)
                    if i >= 3 and value is not None:
                        times.append(elapsed)
                SCORES[name] = scores
                FAMILY_INFO[name] = info
                TIMING[name] = {"seconds_per_summary": statistics.median(times) if times else None,
                                "mean_seconds": statistics.fmean(times) if times else None,
                                "peak_vram_gib": torch.cuda.max_memory_allocated() / 2**30,
                                "row_errors": errors}
                print(name, TIMING[name])
        '''),
        md("## Analysis"),
        code('''
            timing_ok = {k: v for k, v in TIMING.items() if v["seconds_per_summary"]}
            analysis = fc.analyze(ROWS, SCORES, criteria, timing_ok)
            print(json.dumps(analysis, indent=1)[:5000])
        '''),
        code('''
            receipt = {
                "schema_version": 1, "criteria_id": criteria["criteria_id"],
                "criteria_sha256": EXPECTED_CRITERIA_SHA256, "records": len(subset), "summaries": len(ROWS),
                "reference_text_used": False, "model_outputs_used": False,
                "environment": ENVIRONMENT, "install_log": INSTALL_LOG,
                "families": FAMILY_INFO, "unavailable": load_errors, "row_errors": ROW_ERRORS,
                "timing": TIMING, "analysis": analysis,
                "scores": [{"record_id": r["record_id"], "group": r["group"],
                            **{n: SCORES[n][i] for n in SCORES}} for i, r in enumerate(ROWS)],
            }
            path = OUT_DIR / "faithfulness_crossfamily_receipt.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(path, hashlib.sha256(path.read_bytes()).hexdigest()[:16])
        '''),
        code('''
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, max(1, len(SCORES)), figsize=(5 * max(1, len(SCORES)), 4), squeeze=False)
            for ax, (name, scores) in zip(axes[0], SCORES.items()):
                data = [[s for r, s in zip(ROWS, scores) if r["group"] == g and s is not None] for g in fc.ALL_GROUPS]
                ax.boxplot(data); ax.set_xticklabels(fc.ALL_GROUPS, rotation=30); ax.set_title(name)
            fig.tight_layout(); fig.savefig(OUT_DIR / "faithfulness_by_group.png", dpi=130); plt.show()
        '''),
        md('''
            ## What to send back
            `faithfulness_crossfamily_receipt.json` (scores only, no source text). It contains the installed
            versions and checkpoints to pin, the per-family G1/G2 results, cross-family agreement (G3) and the
            projected GPU hours for 12,000 summaries. You set the scoring budget after reading the projection.
        '''),
    ]
    return notebook(cells)


def pilot_faithfulness_notebook() -> nbformat.NotebookNode:
    expected = sha256(ROOT / PROTOCOL / "pilot_faithfulness_protocol.json")
    cells = [
        md('''
            # TIB P4e: MiniCheck faithfulness of Pilot40 outputs (S/M/L views)

            Scores the Pilot40 outputs (40 records x 5 profiles) with MiniCheck, one sentence at a time against the
            source, and derives the faithfulness of the 60/120/240-word views from those sentence scores. Descriptive
            only: no ranking, no selection. Scope and metric are fixed in `pilot_faithfulness_protocol.json`
            (hash-checked first).

            **Choose a T4 GPU runtime.** Inputs (private; TIB source use is local/private/noncommercial), in Drive
            `MyDrive/TIB_P4E_261022/` on Colab: the code bundle zip and the Pilot40 evidence zip
            (`tib-pilot40-evidence-*.zip`, exported by the Pilot40 notebook). Every record is checkpointed to Drive, so
            a disconnected session can be resumed by running the notebook again. Failed or missing records are listed
            and never scored as zero. First run of this scope: 191 records in 34 minutes on a T4.

            **Rerun with sentence detail.** Metric, views and protocol are unchanged. This version also writes every
            summary sentence with its MiniCheck probability to `PRIVATE_pilot_sentence_scores.jsonl` so flagged
            sentences can be read against the source. That file holds text derived from the private sources: keep it
            in the private Drive folder and on the local machine, never in the receipt, the code zip or the repository.
            It uses new checkpoint, receipt and PNG names so the first run's files are not overwritten, and it
            compares the new view scores with the first run's receipt as a reproducibility check.
        '''),
        setup_cell("pilot_faithfulness_protocol.json", expected),
        environment_cell(),
        code('''
            import torch
            assert torch.cuda.is_available(), "Select a GPU runtime (T4)"
            ENVIRONMENT["gpu"] = torch.cuda.get_device_name(0)
            print(ENVIRONMENT["gpu"], torch.__version__)
        '''),
        md("## Install MiniCheck"),
        code('''
            INSTALL_LOG = {}
            def pip(label, *args):
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", *args], capture_output=True, text=True)
                INSTALL_LOG[label] = {"returncode": result.returncode, "tail": (result.stderr or result.stdout)[-400:]}
                print(label, "ok" if result.returncode == 0 else "FAILED")
                if result.returncode:
                    print("   ", INSTALL_LOG[label]["tail"])
            pip("MiniCheck", "minicheck @ git+https://github.com/Liyan06/MiniCheck.git@main")
            import nltk  # recent NLTK needs punkt_tab, which MiniCheck does not download
            for resource in ("punkt", "punkt_tab"):
                nltk.download(resource, quiet=True)
        '''),
        md("## Load the Pilot40 outputs"),
        code('''
            from experiments.scripts import tib_pilot_faithfulness as pf
            if IN_COLAB:
                candidates = sorted(DRIVE_DIR.glob("tib-pilot40-evidence-*.zip"))
            else:
                candidates = sorted((ROOT / "experiments/outputs").rglob("tib-pilot40-evidence-*.zip"))
            assert candidates, "Put the Pilot40 evidence zip (tib-pilot40-evidence-*.zip) in the input folder"
            EVIDENCE_ZIP = candidates[-1]
            print("evidence:", EVIDENCE_ZIP.name, hashlib.sha256(EVIDENCE_ZIP.read_bytes()).hexdigest()[:16])
            ROWS, SKIPPED = pf.collect_rows(EVIDENCE_ZIP)
            from collections import Counter
            print("to score:", dict(Counter(r["candidate"] for r in ROWS)))
            print("not scored:", dict(Counter((s["candidate"], s["status"]) for s in SKIPPED)))
            assert ROWS, "No usable outputs in the evidence zip"
        '''),
        md("## Score (checkpointed; run again to resume)"),
        code('''
            score_claims, MINICHECK_INFO = pf.load_minicheck_claims()
            # New names: the checkpoint of the first run holds no sentence detail, so it must not be resumed.
            CHECKPOINT = OUT_DIR / "pilot_faithfulness_scores_sentences.jsonl"
            DETAIL_PATH = OUT_DIR / "PRIVATE_pilot_sentence_scores.jsonl"  # sentence text: keep private
            started = time.monotonic()
            done = {"n": 0}
            def progress(scored):
                done["n"] += 1
                if done["n"] % 10 == 0:
                    print(done["n"], "new rows,", round((time.monotonic() - started) / 60, 1), "min")
            RESULTS = pf.score_rows(ROWS, score_claims, CHECKPOINT, on_row=progress, detail_path=DETAIL_PATH)
            SCORING_SECONDS = time.monotonic() - started
            print("rows:", len(RESULTS), "errors:", sum(1 for r in RESULTS if "views" not in r),
                  "new-scoring minutes this run:", round(SCORING_SECONDS / 60, 1))
            errors = [r for r in RESULTS if "views" not in r]
            if errors:
                print("first error:", errors[0].get("error"))
            # A record that was scored but crashed before its checkpoint line appears twice in the detail file; keep the last.
            detail_records = {}
            for line in DETAIL_PATH.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                detail_records[(item["candidate"], item["record_id"])] = item
            print("records with sentence detail:", len(detail_records), "of", sum(1 for r in RESULTS if "views" in r))
        '''),
        md("## Reproducibility against the first run"),
        code('''
            FIRST_RECEIPT = OUT_DIR / "pilot_faithfulness_receipt.json"
            if FIRST_RECEIPT.exists():
                DRIFT = pf.max_abs_view_diff(RESULTS, json.loads(FIRST_RECEIPT.read_text(encoding="utf-8"))["scores"])
                print(DRIFT)
            else:
                DRIFT = None
                print("first-run receipt not found; no comparison")
        '''),
        md("## Summary (descriptive, no ranking)"),
        code('''
            import pandas as pd
            TABLE = pf.summarize(RESULTS, SKIPPED)
            flat = [{"candidate": c, "scored": e["scored_records"], "errors": e["error_records"],
                     "not_scored": e["not_scored_records"],
                     **{f"{v}_prob": e["views"][v]["mean_prob"] for v in pf.VIEW_NAMES},
                     **{f"{v}_flagged": e["views"][v]["flagged_share"] for v in pf.VIEW_NAMES}}
                    for c, e in TABLE.items()]
            pd.set_option("display.width", 200)
            print(pd.DataFrame(flat).round(3).to_string(index=False))
            receipt = {
                "schema_version": 1, "protocol_id": "tib-pilot40-faithfulness-minicheck-v1",
                "protocol_sha256": EXPECTED_CRITERIA_SHA256,
                "evidence_zip": EVIDENCE_ZIP.name, "evidence_zip_sha256": hashlib.sha256(EVIDENCE_ZIP.read_bytes()).hexdigest(),
                "environment": ENVIRONMENT, "install_log": INSTALL_LOG, "minicheck": MINICHECK_INFO,
                "scoring_seconds_this_run": SCORING_SECONDS, "table": TABLE,
                "skipped": SKIPPED, "scores": RESULTS, "drift_against_first_run": DRIFT,
                "sentence_detail_file": DETAIL_PATH.name,
            }
            path = OUT_DIR / "pilot_faithfulness_receipt_sentences.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(path, hashlib.sha256(path.read_bytes()).hexdigest()[:16])
        '''),
        code('''
            import matplotlib.pyplot as plt
            names = [c for c, e in TABLE.items() if e["scored_records"]]
            fig, ax = plt.subplots(figsize=(7, 4))
            width = 0.25
            for j, view in enumerate(pf.VIEW_NAMES):
                ax.bar([i + (j - 1) * width for i in range(len(names))],
                       [TABLE[n]["views"][view]["mean_prob"] for n in names], width, label=view)
            ax.set_xticks(range(len(names))); ax.set_xticklabels(names)
            ax.set_ylabel("mean MiniCheck probability"); ax.set_ylim(0, 1); ax.legend(title="view")
            ax.set_title("Pilot40 faithfulness by profile and view (descriptive)")
            fig.tight_layout(); fig.savefig(OUT_DIR / "pilot_faithfulness_sentences.png", dpi=130); plt.show()
        '''),
        md('''
            ## What to keep
            `pilot_faithfulness_receipt_sentences.json` (view scores and the drift check; no sentence text) and the PNG
            may be shared. `PRIVATE_pilot_sentence_scores.jsonl` holds the sentences themselves: download it to the
            local machine only. The pilot is 40 records per profile and one realization: read the table as a
            description of this pipeline's outputs, not as a ranking of the profiles.
        '''),
    ]
    return notebook(cells)


def notebook(cells) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "colab": {"provenance": []},
    }
    nbformat.validate(nb)
    return nb


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
    targets = {
        "tib-p4e-faithfulness-cost-t4-261022-v1.ipynb": faithfulness_notebook(),
        "tib-p4e-pilot40-faithfulness-t4-261022-v1.ipynb": pilot_faithfulness_notebook(),
    }
    for name, nb in targets.items():
        nbformat.write(nb, NOTEBOOK_DIR / name)
        print("wrote", NOTEBOOK_DIR / name)
    bundle = build_bundle()
    print("wrote", bundle, sha256(bundle))


if __name__ == "__main__":
    main()
