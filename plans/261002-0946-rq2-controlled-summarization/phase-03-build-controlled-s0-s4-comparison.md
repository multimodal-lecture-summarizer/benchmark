---
phase: 3
title: "Build controlled S0 S4 comparison"
status: pending
priority: P1
dependencies: [2]
---

# Phase 3: Build controlled S0 S4 comparison

## Overview

Turn existing summarizer scaffolding into a paired text-only S1/S3 diagnostic first. Add S0/S4 only on records supporting their inputs; the formal automatic study uses the frozen fair comparison.

## Requirements

- S1 fixed-chunk map-reduce and S3 predicted temporal hierarchy are the core pair. S0 flat/truncated is a lower bound; S4 adds verified visual evidence only on its paired visual subset. Define S3+ev only as a named single-factor ablation if distinct from S4.
- Development diagnostic: same generator/model and a common source/output cap, with actual token use reported per arm. Formal study: give both arms the same source span and freeze a per-talk cumulative input-token budget and allowed imbalance tolerance before test. Measure actual tokenizer/provider tokens across every map/reduce call, output and retry; report arm differences and a sensitivity analysis where imbalance is material. Keep output cap, decoding settings and item IDs common. Exact equality is not required when structure changes prompt overhead.
- If an arm exceeds budget, classify failure and reduce its input by predeclared rules. No post-hoc scaling-curve reclassification.
- Never generate references from source text; never hard-code hallucination rates or substitute GT for predicted boundaries. Lexical source overlap is a descriptive proxy, not factuality; reference-based metrics become N/A without a provided target.

## Architecture

Declared input package → deterministic S1/S3 arm builder → token/latency ledger → generator → paired outputs and errors. Formal run enforces the frozen budget/tolerance and records measured imbalance. Keep the older `run_rq2_benchmark.py` output quarantined.

## Related Code Files

- Reuse/modify: `benchmarks/models/summarization.py`, `benchmarks/models/llm_engine.py`, `experiments/registry/candidates.yaml`, `experiments/notebooks/notebook_manifest.yaml`.
- Create or replace a clearly named official runner: `benchmarks/scripts/run_rq2_official_benchmark.py`; adapt `05a_summarization_benchmark.ipynb` only after clarifying its current extractive 5/10/20% purpose.
- Tests: `tests/test_summarization.py` plus focused provenance/budget/pairing tests.

## Implementation Steps

1. Reconcile registered candidate class names with real classes and declare exact arm definitions; preserve 05a extractive metrics as a distinct diagnostic if retained.
2. Make cumulative tokenizer-based usage and generation settings observable per call. Use a shared cap in diagnostics; freeze source span, per-talk budget and imbalance tolerance for the formal automatic study.
3. Implement paired generation with stable seed, retries/errors recorded, deterministic ordering and immutable outputs; fail on absent source-bound transcript or predicted input. Mark reference-dependent metrics N/A when no creator abstract is available, and retain its unverified provenance when present.
4. Test fabricated-input and GT-leakage rejection, source/arm pairing, multi-call token cap, missing visual evidence, deterministic resume and no fixed metric injection.
5. Run S1/S3 on the selected development cohort and report paired item-level outputs, token differences and errors as diagnostic evidence. Add S4 only when aligned visuals pass its separate gate.

## Success Criteria

- [ ] Diagnostic S1/S3 pairs share source IDs, model/config and cap; actual token differences are visible. Formal pairs meet frozen measured budget/tolerance and output caps.
- [ ] Registry, runner and notebook entry agree on arm names and artifact contracts.
- [ ] Tests reject synthetic reference, GT-as-prediction, placeholder visual and budget overrun.
- [ ] Development integration outputs contain provenance and no preset outcome figures.

## Risk Assessment

Multimodal payloads may exceed a common budget or backend may not expose exact usage. Keep S4 as a separate visual subset; use model/provider token accounting or report that its fairness could not be verified.
