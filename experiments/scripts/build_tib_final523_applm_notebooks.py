"""Build the final523 application-summarizer notebooks (generation, scoring) and their code bundle; nothing is executed.

    python -m experiments.scripts.build_tib_final523_applm_notebooks
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import nbformat

from experiments.scripts.build_tib_final523_faithfulness_notebook import MINICHECK_PIN
from experiments.scripts.build_tib_p4e_notebooks import ROOT, code, environment_cell, md, notebook, sha256

NOTEBOOK_DIR = ROOT / "experiments/notebooks"
GENERATION_NAME = "tib-final523-applm-generate-t4-261031-v1.ipynb"
SCORING_NAME = "tib-final523-applm-score-t4-261031-v1.ipynb"
OUTPUT_DIR = ROOT / "experiments/outputs/tib-final523-applm-261031"
PROTOCOL = "experiments/registry/protocols/tib-final523-applm-261031-v1/protocol.json"
BUNDLE_NAME = "tib-final523-applm-code-261031-v1.zip"
DRIVE_FOLDER = "TIB_FINAL523_APPLM_261031"
SCORING_BUNDLE = "tib-final523-scoring-261024-v1.zip"
DRYRUN_BUNDLE = "tib-selection300-scoring-261024-v1.zip"
VLLM_PIN = "vllm==0.11.0"
TRANSFORMERS_PIN = "transformers==4.57.1"  # vllm 0.11.0 leaves Colab's transformers 5.x, whose tokenizers it cannot load
MODEL_REPO = "Qwen/Qwen2.5-7B-Instruct-AWQ"
MODEL_REVISION = "b25037543e9394b818fdfca67ab2a00ecc7dd641"
PROTOCOL_CEILING_SECONDS = 8 * 3600  # frozen in protocol.json (budget.ceiling_gpu_hours)
# User-approved budget increase (2026-11-02), made after the 8 h stop at 400/523 rows; the protocol file is not edited.
CEILING_SECONDS = 11 * 3600
BUNDLE_FILES = [
    "experiments/scripts/tib_benchmark_output.py",
    "experiments/scripts/tib_budget_views.py",
    "experiments/scripts/tib_summary_constructors.py",
    "experiments/scripts/tib_benchmark_generation_telemetry.py",
    "experiments/scripts/tib_pilot_faithfulness.py",
    "experiments/scripts/tib_final523_faithfulness.py",
    "experiments/scripts/tib_final523_applm.py",
    "tests/test_tib_final523_faithfulness.py",
    "tests/test_tib_final523_applm.py",
    "experiments/registry/protocols/tib-final523-faithfulness-261031-v1/protocol.json",
    PROTOCOL,
]


def fill(source: str, **values) -> str:
    for key, value in values.items():
        source = source.replace(f"@@{key}@@", str(value))
    assert "@@" not in source, "unfilled placeholder"
    return source


def setup_cell(extra_inputs: str) -> object:
    return code(fill('''
        import hashlib, json, platform, subprocess, sys, time, zipfile
        from datetime import datetime, timezone
        from pathlib import Path

        IN_COLAB = "google.colab" in sys.modules
        if IN_COLAB:
            from google.colab import drive
            drive.mount("/content/drive")
            DRIVE_DIR = Path("/content/drive/MyDrive/@@FOLDER@@")
            ROOT = Path("/content/applm"); ROOT.mkdir(exist_ok=True)
            with zipfile.ZipFile(DRIVE_DIR / "@@BUNDLE@@") as bundle:
                bundle.extractall(ROOT)
            INPUT_DIR = DRIVE_DIR
            OUT_DIR = DRIVE_DIR / "results"
        else:
            here = Path.cwd()
            ROOT = next(p for p in [here, *here.parents] if (p / "experiments/scripts/tib_final523_applm.py").exists())
            INPUT_DIR = ROOT / "research-data/tib-final523-scoring-261024-v1"
            OUT_DIR = ROOT / "research-data/tib-final523-applm-261031-v1"  # private: holds source and summary text
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(ROOT))

        PROTOCOL_PATH = ROOT / "@@PROTOCOL@@"
        EXPECTED_PROTOCOL_SHA256 = "@@PROTOCOL_SHA@@"
        actual = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        assert actual == EXPECTED_PROTOCOL_SHA256, (
            f"Protocol hash {actual} differs from the notebook's {EXPECTED_PROTOCOL_SHA256}: the code zip in Drive is "
            "probably an older build. Upload the latest @@BUNDLE@@, restart the session and run again. Do not edit the protocol.")
        print("protocol sha256 verified:", actual[:16], "...")
        @@EXTRA@@
    ''', FOLDER=DRIVE_FOLDER, BUNDLE=BUNDLE_NAME, PROTOCOL=PROTOCOL, PROTOCOL_SHA=sha256(ROOT / PROTOCOL), EXTRA=extra_inputs))


GEN_INPUTS = '''SCORING_ZIP = INPUT_DIR / "@@SCORING@@"
        DRYRUN_ZIP = INPUT_DIR / "@@DRYRUN@@"
        MODE = "dry_run"  # "dry_run": 8 validation IDs, lengths only | "final": the 523 test IDs
        assert MODE in ("dry_run", "final")
        SOURCE_ZIP = DRYRUN_ZIP if MODE == "dry_run" else SCORING_ZIP
        assert SOURCE_ZIP.exists(), f"Missing input: {SOURCE_ZIP}"
        SOURCE_ZIP_SHA256 = hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
        OUTPUTS = OUT_DIR / ("PRIVATE_applm_dryrun.jsonl" if MODE == "dry_run" else "PRIVATE_applm_outputs.jsonl")
        print("mode:", MODE, "| source bundle:", SOURCE_ZIP.name, SOURCE_ZIP_SHA256[:16], "...")'''


def generation_notebook() -> nbformat.NotebookNode:
    cells = [
        md(fill('''
            # TIB final523: the application's summarizer family (Qwen2.5-7B-Instruct AWQ) on the 523 test IDs

            Exploratory, post-hoc, text stage only (`protocol.json`, hash-checked first). One frozen prompt, greedy decoding,
            no chunking, no fallback model, run **locally on this T4** (no API, no transcript leaves Colab). It cannot change
            the final523 confirmatory label or the LED choice.

            **Choose a T4 GPU runtime.** Inputs (private; TIB use is local/private/noncommercial), in Drive `MyDrive/@@FOLDER@@/`:
            the code bundle `@@BUNDLE@@`, the final523 scoring bundle `@@SCORING@@` and, for the dry run, the selection300
            scoring bundle `@@DRYRUN@@`.

            **Order.** (1) `MODE = "dry_run"` first: 8 validation IDs; it prints counts, lengths and finish reasons, never text.
            Only mechanical faults (template, token limits, stop tokens) may be fixed after it; the wording of the prompt may not.
            (2) Set `MODE = "final"` and run again from the top. Every batch is checkpointed to Drive, so a dropped session is
            resumed by running the notebook again. Budget ceiling 8 GPU hours (estimate 1.5-3).
        ''', FOLDER=DRIVE_FOLDER, BUNDLE=BUNDLE_NAME, SCORING=SCORING_BUNDLE, DRYRUN=DRYRUN_BUNDLE)),
        setup_cell(fill(GEN_INPUTS, SCORING=SCORING_BUNDLE, DRYRUN=DRYRUN_BUNDLE)),
        environment_cell(),
        code('''
            import subprocess
            probe = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
            print(probe.stdout.strip())
            assert "T4" in probe.stdout, "Select a T4 GPU runtime"
            ENVIRONMENT["gpu"] = probe.stdout.strip()
        '''),
        md(f"## Install vLLM (pinned)\nIf `{VLLM_PIN}` and `{TRANSFORMERS_PIN}` are not both installed, the cell installs them and stops: restart the runtime (Runtime > Restart session) and run again from the top."),
        code(fill('''
            import importlib.metadata as md_
            def installed(name):
                try:
                    return md_.version(name)
                except md_.PackageNotFoundError:
                    return None
            INSTALL_LOG = {}
            PINS = dict(spec.split("==") for spec in ("@@PIN@@", "@@TPIN@@"))
            if any(installed(name) != version for name, version in PINS.items()):
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "@@PIN@@", "@@TPIN@@"], capture_output=True, text=True)
                INSTALL_LOG["vllm"] = {"returncode": result.returncode, "tail": (result.stderr or result.stdout)[-600:]}
                assert result.returncode == 0, INSTALL_LOG["vllm"]["tail"]
                raise SystemExit("vLLM and transformers installed. Restart the runtime (Runtime > Restart session) and run again from the top.")
            ENVIRONMENT["packages"].update({n: installed(n) for n in ("vllm", "torch", "transformers")})
            print({n: ENVIRONMENT["packages"][n] for n in ("vllm", "torch", "transformers")})
        ''', PIN=VLLM_PIN, TPIN=TRANSFORMERS_PIN)),
        md("## Load the sources (hash-checked)"),
        code('''
            from experiments.scripts import tib_final523_applm as ap
            SOURCES = ap.collect_sources(SOURCE_ZIP, limit=8 if MODE == "dry_run" else None)
            # Fixed spread over strata and lengths, so the early time projection is not taken from the first sorted IDs.
            SOURCES = [SOURCES[i] for i in sorted(range(len(SOURCES)), key=lambda i: (i * 7919) % len(SOURCES))]
            print(len(SOURCES), "records; strata:", {s: sum(1 for x in SOURCES if x["stratum"] == s) for s in ap.STRATA})
            assert MODE == "dry_run" or len(SOURCES) == 523, "the final run needs all 523 test IDs"
        '''),
        md("## Load the model (pinned revision)"),
        code(fill('''
            import os
            # Run the engine in this process: a crash of the separate engine process is invisible in Colab output,
            # in-process it surfaces as an ordinary traceback. Same engine, same weights, same prompt.
            os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"
            from vllm import LLM, SamplingParams
            LOAD_STARTED = time.monotonic()
            llm = LLM(model="@@REPO@@", revision="@@REVISION@@", tokenizer_revision="@@REVISION@@", quantization="awq", dtype="float16",
                      max_model_len=ap.MAX_MODEL_LEN, gpu_memory_utilization=0.80, max_num_batched_tokens=2048, seed=ap.SEED, max_num_seqs=4)
            LOAD_SECONDS = time.monotonic() - LOAD_STARTED
            tokenizer = llm.get_tokenizer()
            SAMPLING = SamplingParams(temperature=0, top_p=1, max_tokens=ap.MAX_NEW_TOKENS, seed=ap.SEED)
            print("model loaded in", round(LOAD_SECONDS), "s")
        ''', REPO=MODEL_REPO, REVISION=MODEL_REVISION)),
        md('''
            ## Generate (checkpointed; run again to resume)
            A prompt that cannot fit is a final `prompt_too_long` row and is never truncated. After the first five batches
            (20 records) the cell projects the total time and stops if the projection exceeds the ceiling.
        '''),
        code(fill('''
            def generate_batch(batch_messages):
                ids = [list(tokenizer.apply_chat_template(m, add_generation_prompt=True, tokenize=True, return_dict=False))
                       for m in batch_messages]
                outcomes, runnable = [None] * len(ids), []
                for i, prompt in enumerate(ids):
                    if len(prompt) + ap.MAX_NEW_TOKENS > ap.MAX_MODEL_LEN:
                        outcomes[i] = {"error": "prompt_too_long", "prompt_tokens": len(prompt)}
                    else:
                        runnable.append(i)
                if runnable:
                    started = time.monotonic()
                    try:
                        results = llm.generate([{"prompt_token_ids": ids[i]} for i in runnable], SAMPLING, use_tqdm=False)
                        share = (time.monotonic() - started) / len(runnable)
                        for i, result in zip(runnable, results):
                            out = result.outputs[0]
                            outcomes[i] = {"text": out.text, "finish_reason": out.finish_reason, "prompt_tokens": len(ids[i]),
                                           "completion_tokens": len(out.token_ids), "seconds": share}
                    except Exception as exc:  # text-free reason; the batch is generated again on the next run
                        import traceback
                        # The dry run uses validation sources, so its traceback may be shown in full; the final run shows the type only.
                        print(traceback.format_exc()[-2500:] if MODE == "dry_run" else "generation failed: " + type(exc).__name__)
                        for i in runnable:
                            outcomes[i] = {"error": type(exc).__name__, "prompt_tokens": len(ids[i])}
                return outcomes

            CEILING = @@CEILING@@
            SPENT_PATH = OUT_DIR / "generation_seconds.json"
            state = json.loads(SPENT_PATH.read_text()) if SPENT_PATH.exists() else {"seconds": 0.0, "batches": 0,
                                                                                  "first_generate_utc": datetime.now(timezone.utc).isoformat()}
            if MODE == "dry_run":
                state = {"seconds": 0.0, "batches": 0, "first_generate_utc": datetime.now(timezone.utc).isoformat()}
            started, spent_before, batches_before = time.monotonic(), state["seconds"], state["batches"]

            class CeilingReached(Exception):
                pass

            def on_batch(rows, count=[0]):
                count[0] += 1
                state["seconds"] = spent_before + time.monotonic() - started
                state["batches"] = batches_before + count[0]
                if MODE == "final":
                    SPENT_PATH.write_text(json.dumps(state))
                per_batch = state["seconds"] / state["batches"]
                if state["batches"] % 10 == 0:
                    print(state["batches"], "batches,", round(state["seconds"] / 3600, 2), "GPU h")
                if state["batches"] == 5 and MODE == "final":
                    projection = per_batch * -(-len(SOURCES) // 4)
                    print("projected %.2f GPU h for all %d records" % (projection / 3600, len(SOURCES)))
                    if projection > CEILING:
                        raise CeilingReached(f"projected {projection / 3600:.2f} h exceeds the ceiling")
                if state["seconds"] + per_batch > CEILING:
                    raise CeilingReached(f"the next batch would pass the ceiling at {state['seconds'] / 3600:.2f} h")

            try:
                ROWS = ap.generate_rows(SOURCES, generate_batch, OUTPUTS, batch_size=4, on_batch=on_batch)
            except CeilingReached as stop:
                raise SystemExit(f"{stop}. Every finished batch is checkpointed. Ask for more budget, then run again.")
            ROWS = ap.latest_rows(OUTPUTS)  # a retried row appears twice in the file; the last line wins
            RECEIPT = ap.generation_receipt(ROWS)
            print(json.dumps(RECEIPT, indent=1))
        ''', CEILING=CEILING_SECONDS)),
        md("## Receipt (no text)"),
        code(fill('''
            receipt = {"schema_version": 1, "protocol_id": ap.PROTOCOL_ID, "protocol_sha256": EXPECTED_PROTOCOL_SHA256, "mode": MODE,
                       "source_bundle": SOURCE_ZIP.name, "source_bundle_sha256": SOURCE_ZIP_SHA256,
                       "model": {"repo": "@@REPO@@", "revision": "@@REVISION@@"}, "environment": ENVIRONMENT,
                       "model_load_seconds": LOAD_SECONDS, "generation_seconds_total": state["seconds"],
                       "first_generate_utc": state["first_generate_utc"], "receipt_written_utc": datetime.now(timezone.utc).isoformat(),
                       "summary": RECEIPT, "prompt_sha256": ap.PROMPT_SHA256, "decoding": ap.DECODING,
                       "budget": {"protocol_ceiling_gpu_hours": @@PROTOCOL_HOURS@@, "approved_ceiling_gpu_hours": CEILING / 3600,
                                  "note": "the run stopped at the protocol ceiling with 400 of 523 rows; the user approved a higher ceiling on 2026-11-02 to finish the remaining records with the same configuration"}}
            path = OUT_DIR / ("applm_dryrun_receipt.json" if MODE == "dry_run" else "applm_generation_receipt.json")
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(path, hashlib.sha256(path.read_bytes()).hexdigest())
            if MODE == "final":
                assert RECEIPT["rows"] == 523, "rows differ from the 523 test IDs"
        ''', REPO=MODEL_REPO, REVISION=MODEL_REVISION, PROTOCOL_HOURS=PROTOCOL_CEILING_SECONDS // 3600)),
        md('''
            ## What to send back
            `applm_generation_receipt.json` (counts, tokens, finish reasons, timing; no text) and the executed notebook.
            `PRIVATE_applm_outputs.jsonl` holds sources, references and summaries: keep it in the private Drive folder and on
            the local machine, never in the repository. The scoring notebook reads it from Drive.
        '''),
    ]
    return notebook(cells)


SCORE_INPUTS = '''OUTPUTS = OUT_DIR / "PRIVATE_applm_outputs.jsonl"
        assert OUTPUTS.exists(), "Run the generation notebook in final mode first"
        OUTPUTS_SHA256 = hashlib.sha256(OUTPUTS.read_bytes()).hexdigest()
        print("outputs:", OUTPUTS.name, OUTPUTS_SHA256[:16], "...")'''


def scoring_notebook() -> nbformat.NotebookNode:
    cells = [
        md(fill('''
            # TIB final523: scoring the application-summarizer outputs (ROUGE and MiniCheck)

            Scores `PRIVATE_applm_outputs.jsonl` from the generation notebook. ROUGE-1/2/L F1 uses scorer v2's exact
            configuration (rouge-score 0.1.2; it reproduced all 2,088 stored final523 ROUGE-L values with difference 0).
            MiniCheck is pinned and run exactly as in the LED/BART faithfulness protocol. BERTScore (scorer v2, xlm-roberta-large)
            needs the formal scorer venv and is a separate optional step. Failed generation rows stay NULL.

            **Choose a T4 GPU runtime.** Inputs in Drive `MyDrive/@@FOLDER@@/`: the code bundle `@@BUNDLE@@` (the same one as
            for generation) and `results/PRIVATE_applm_outputs.jsonl`. Every record is checkpointed; run again to resume.
        ''', FOLDER=DRIVE_FOLDER, BUNDLE=BUNDLE_NAME)),
        setup_cell(SCORE_INPUTS),
        environment_cell(),
        code('''
            import torch
            assert torch.cuda.is_available(), "Select a GPU runtime (T4)"
            ENVIRONMENT["gpu"] = torch.cuda.get_device_name(0)
            print(ENVIRONMENT["gpu"], torch.__version__)
        '''),
        md("## Install the scorers (pinned)"),
        code(fill('''
            INSTALL_LOG = {}
            for label, spec in (("rouge-score", "rouge-score==0.1.2"), ("MiniCheck", "@@MINICHECK@@")):
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", spec], capture_output=True, text=True)
                INSTALL_LOG[label] = {"returncode": result.returncode, "tail": (result.stderr or result.stdout)[-400:]}
                assert result.returncode == 0, INSTALL_LOG[label]["tail"]
            import nltk  # recent NLTK needs punkt_tab, which MiniCheck does not download
            for resource in ("punkt", "punkt_tab"):
                nltk.download(resource, quiet=True)
            print("installed")
        ''', MINICHECK=MINICHECK_PIN)),
        md("## Load the generated rows"),
        code('''
            from collections import Counter
            from experiments.scripts import tib_final523_applm as ap
            from experiments.scripts import tib_final523_faithfulness as ff
            GENERATED = ap.latest_rows(OUTPUTS)  # a retried row appears twice in the file; the last line wins
            assert len(GENERATED) == 523 and len({r["record_id"] for r in GENERATED}) == 523, "need one row per test ID"
            SCOREABLE = [r for r in GENERATED if r["scoreable"]]
            print("generated:", dict(Counter(r["generation_status"] for r in GENERATED)))
        '''),
        md("## ROUGE (CPU, exact scorer v2 configuration)"),
        code('''
            ROUGE = []
            for r in GENERATED:
                scores = ap.rouge_scores(r["delivered_summary"], r["reference"]) if r["scoreable"] else \\
                    {"rouge1_f1": None, "rouge2_f1": None, "rougeL_f1": None}
                ROUGE.append({"record_id": r["record_id"], "stratum": r["source_stratum"], **scores})
            print("rouge scored:", sum(1 for x in ROUGE if x["rougeL_f1"] is not None))
        '''),
        md('''
            ## MiniCheck (checkpointed; run again to resume)
            Sentence level against the whole source, contract and S/M/L views, as in the LED/BART protocol. No score is printed.
        '''),
        code(fill('''
            score_claims, MINICHECK_INFO = ff.load_minicheck_claims()
            MINICHECK_INFO["install"] = "@@MINICHECK@@"
            ROWS = [ap.to_faithfulness_row(r) for r in SCOREABLE]
            CHECKPOINT = OUT_DIR / "applm_faithfulness_scores.jsonl"
            DETAIL_PATH = OUT_DIR / "PRIVATE_applm_sentence_scores.jsonl"  # sentence text: keep private
            SPENT_PATH = OUT_DIR / "faithfulness_seconds.json"
            CEILING = @@CEILING@@
            state = json.loads(SPENT_PATH.read_text()) if SPENT_PATH.exists() else {"seconds": 0.0, "records": 0,
                                                                                  "first_score_utc": datetime.now(timezone.utc).isoformat()}
            started, spent_before, records_before = time.monotonic(), state["seconds"], state["records"]

            class CeilingReached(Exception):
                pass

            def progress(scored, count=[0]):
                count[0] += 1
                state["seconds"] = spent_before + time.monotonic() - started
                state["records"] = records_before + count[0]
                SPENT_PATH.write_text(json.dumps(state))
                per_record = state["seconds"] / state["records"]
                if count[0] % 25 == 0:
                    print(count[0], "new records,", round(state["seconds"] / 3600, 2), "GPU h")
                if state["seconds"] + per_record > CEILING:
                    raise CeilingReached(f"the next record would pass the ceiling at {state['seconds'] / 3600:.2f} h")

            try:
                SCORES = ff.score_rows(ROWS, score_claims, CHECKPOINT, DETAIL_PATH, on_row=progress)
            except CeilingReached as stop:
                raise SystemExit(f"{stop}. Every scored record is checkpointed. Ask for more budget, then run again.")
            errors = [r for r in SCORES if "views" not in r]
            assert not errors, f"{len(errors)} error rows ({errors[0]['error']}): restart the runtime and run again to retry them"
        ''', MINICHECK=MINICHECK_PIN, CEILING=3 * 3600)),
        md("## Receipt (no text)"),
        code('''
            receipt = {"schema_version": 1, "protocol_id": ap.PROTOCOL_ID, "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                       "outputs_file": OUTPUTS.name, "outputs_sha256": OUTPUTS_SHA256, "environment": ENVIRONMENT,
                       "install_log": INSTALL_LOG, "minicheck": MINICHECK_INFO, "first_score_utc": state["first_score_utc"],
                       "receipt_written_utc": datetime.now(timezone.utc).isoformat(), "faithfulness_seconds_total": state["seconds"],
                       "generation": ap.generation_receipt(GENERATED), "rouge": ROUGE,
                       "faithfulness_scores": sorted(SCORES, key=lambda r: r["record_id"]),
                       "sentence_detail_file": DETAIL_PATH.name}
            path = OUT_DIR / "applm_scores_receipt.json"
            path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(path, hashlib.sha256(path.read_bytes()).hexdigest())
        '''),
        md('''
            ## What to send back
            `applm_scores_receipt.json` (per-record ROUGE and MiniCheck scores; no text) and the executed notebook.
            `PRIVATE_applm_sentence_scores.jsonl` stays on the private Drive folder and the local machine.
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
    for name, nb in ((GENERATION_NAME, generation_notebook()), (SCORING_NAME, scoring_notebook())):
        nbformat.write(nb, NOTEBOOK_DIR / name)
        print("wrote", NOTEBOOK_DIR / name)
    bundle = build_bundle()
    print("wrote", bundle, sha256(bundle))


if __name__ == "__main__":
    main()
