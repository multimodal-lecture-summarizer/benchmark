# ASR architecture Colab: empty transcript and partial native test

Recorded 2026-10-05 (Asia/Bangkok). This is a diagnostic run record, not a confirmatory final-test result. The counts and unit ID below come from the Colab artifacts reported during the run; the implementation details were checked against the repository source.

Update on 2026-10-05: the corrected run `architecture_25ce9f1f300b` completed validation and native test. Its results are recorded in [the ASR architecture evaluation](asr-architecture-evaluation-2026-10-05.md). The obsolete input bundle `asr_architecture_colab_t4_inputs.zip` and its SHA sidecar were deleted after the corrected bundle and downloaded run archive were verified; the old partial run remains inside the downloaded archive as historical evidence.

## Observed result

Run root: `MyDrive/asr_architecture_colab_t4/runs/architecture_05740345a101` (bundle SHA-256 prefix `05740345a101`). Validation has a `complete` selection receipt for six candidates × 507 units. Native test has `parent_index.json` status `partial`: **6,929/6,930** candidate–unit pairs completed. Five candidates completed 1,155/1,155 units; `RQ0_ARCH.A1_Wav2Vec2CTC` completed 1,154/1,155.

The sole failure-ledger row is `final_test:MichaelSpecter-978.606-979.312-<o,f0,male>` for A1, with `RuntimeError: empty_transcript`. Its timestamp span is about 0.706 seconds. The bundled adapter rejected an empty worker response after stripping whitespace. The scorer in [`asr_selection_scoring.py`](../../experiments/evaluation/asr_selection_scoring.py) explicitly counts an empty hypothesis as deletions against a nonempty reference. Rejecting that hypothesis therefore prevented a defined scoring outcome. This row does not by itself show that the model or worker crashed.

The corrected [`asr_architecture_adapters.py`](../../experiments/evaluation/asr_architecture_adapters.py) accepts an empty string from a successful worker response and lets the existing scorer count its deletion errors. It still rejects a missing or non-string response, invalid audio input, and worker errors. A failed inference is not a completed checkpoint: [`run_asr_model_benchmark.py`](../../benchmarks/scripts/run_asr_model_benchmark.py) only reuses rows whose status is `completed`.

## Read-only check in Colab

Run this in a notebook cell after `RUN_ROOT` is set; it reads the saved artifacts and does not invoke inference or alter receipts:

```python
import json

root = RUN_ROOT / "native_test/diagnostic/full"
index = json.loads((root / "parent_index.json").read_text(encoding="utf-8"))
aggregate = json.loads((root / "payloads/asr.aggregate.json").read_text(encoding="utf-8"))
ledger = json.loads((root / "payloads/asr.failure_ledger.json").read_text(encoding="utf-8"))
print("parent status:", index["status"])
for row in aggregate["records"]:
    print(row["candidate"], row["completed_units"], row["failed_units"])
for row in ledger["records"]:
    if row.get("status") != "none":
        print(row["candidate"], row["unit_id"], row["status"], row.get("reason"))
```

Interpret `parent_index.json` status `complete` only after the runner writes it. The mere presence of 6,930 checkpoint files is not proof that all rows completed.

## Recovery after the source correction

The Colab orchestrator hashes the source and compares it with the probe, run configuration, validation selection receipt, and checkpoint identity. The native-test runner checks the receipt's `source_sha256`, `config_sha256`, and dependency identity against the current run. Consequently, a changed adapter **cannot resume under the old source identity** or use the old validation receipt as approval for native test.

1. Keep the old `architecture_05740345a101` run, its `partial` parent index, validation receipt, failure ledger, and checkpoints intact. Do not edit their status or copy them into a new root as if they belonged to the corrected source.
2. Use the rebuilt `experiments/outputs/asr_architecture_colab_t4_inputs_empty_transcript_261005_clean.zip` and its `.zip.sha256` sidecar. Its SHA-256 is `25ce9f1f300bd1944f081aac9c1543ee6fe3d2a027105c7f03f637505051027b`; the notebook derives the distinct run root `architecture_25ce9f1f300b`. The archive passed ZIP CRC verification and originally contained seven notebook cells with no execution outputs. In the Colab notebook's first cell, set `BUNDLE` to this new filename before running it; do not edit Python sources inside the extracted `REPO`. See [Benchmark: architecture Colab handoff](../BENCHMARK.md#022-architecture-diverse-asr-benchmark-preparation--2026-10-03) for the remaining setup.
3. In a T4 runtime, run preflight and all six real probes for the new source. Complete all six × 507 validation pairs and verify its new selection receipt says `complete`, with exactly one selected candidate, before opening native test.
4. Run the new native test under that root. Check all six × 1,155 rows, failure ledger, and `parent_index.json`. Report the result as **diagnostic** because this native-test cohort was previously exposed.

Two other observed interruptions have separate causes: a benchmark process blocked while reading a checkpoint JSON through the Drive mount, and a later preflight reported `cuda_unavailable` after a runtime restart. Neither explains the A1 `empty_transcript` failure. A Drive read stall requires checking the live process and mount; `cuda_unavailable` requires restoring the T4 runtime and passing preflight. Do not bypass either gate to force native-test completion.
