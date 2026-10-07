# QA Test Report — ASR Full Corpus A0–A5

Date: 2026-10-03
Scope: focused ASR benchmark tests and notebook executor / phase-1 runner integration. No source files changed.

## Results

- `python -m pytest tests/test_asr_benchmark_runner.py tests/test_asr_candidate_adapters.py tests/test_asr_full_corpus.py tests/test_asr_selection_scoring.py tests/test_phase1_stage_smoke_runners.py -q` — **51 passed in 14.66s**.
- `python -m pytest tests/test_notebook_executor.py -q` — **27 passed in 27.43s**.
- `python -m pytest tests/test_phase1_priority_runners.py -q` — **17 passed, 1 failed in 17.85s**.
- Combined integration run `python -m pytest tests/test_notebook_executor.py tests/test_phase1_priority_runners.py -q` — **44 passed, 1 failed in 43.57s**.
- `python -m benchmarks.scripts.execute_all_notebooks --notebook 01a_asr_model_benchmark --profile full --run-namespace diagnostic --artifact-root experiments/outputs/asr_a0_a5_benchmark_261003_pinned --dry-plan` — succeeded; resolved 01a, runner path, required artifacts, and produced artifacts without executing inference.

## Failure

`tests/test_phase1_priority_runners.py::test_generator_entrypoints_match_repository_notebooks`

Both generator entrypoints (`python experiments/scripts/generate_refactored_notebook.py --check` and module invocation) exit 1 with `[WOULD CHANGE] .../experiments/notebooks/01a_asr_model_benchmark.ipynb`. The generated canonical 01a source differs from the checked-in working notebook. The notebook contains an `MLS_ASR_EVALUATION_MODE` argument path, captured runner output, and an artifact-rendering cell that the generator does not currently emit. This is **in scope / not unrelated**: generator and notebook source are out of sync. I did not modify either file.

## Coverage / limitations

No coverage report was requested or generated. These tests use offline mocks for model adapters; no A0–A5 model inference was run. Dry-plan validates executor wiring only, not successful execution.

## Unresolved questions

None for test execution. Generator/notebook parity needs a code-owner decision: update the generator to emit the intended 01a cells or regenerate 01a and preserve required behavior elsewhere.
