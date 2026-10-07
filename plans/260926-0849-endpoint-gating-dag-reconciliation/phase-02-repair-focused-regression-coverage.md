---
phase: 2
title: "Repair Focused Regression Coverage"
status: completed
priority: P1
dependencies: [phase-01-enforce-fail-closed-endpoint-eligibility]
---

# Phase 2: Repair Focused Regression Coverage

## Overview

Turn the endpoint gate and D2 transcript guarantees into repeatable regression checks, and remove the current Windows SAPI empty-WAV failure mode from the ASR smoke fixture without weakening what the test proves.

## Requirements

- Functional: Verify the legitimate TED-LIUM Arrow transcript mapping and all runner selection boundaries.
- Non-functional: Environment failures must be reported/skipped explicitly; invalid media must not become a misleading product/test failure or a fake ASR success.

## Architecture

Focused tests cover `phase2_freeze_tedlium.py`, `stage_benchmark_helpers.py`, and the stage runners. The ASR fixture must validate file existence, nonzero size and WAV readability before attempting decode. It may use a supported speech synthesizer fallback or skip with a precise environment reason; a tone-only WAV cannot satisfy an ASR happy-path test.

## Related Code Files

- Modify: `tests/test_phase1_stage_smoke_runners.py`
- Read: `tests/test_phase2_tedlium_d2.py`, `tests/test_phase1_priority_runners.py`, endpoint/helper tests
- Modify only if regression found: `experiments/scripts/phase2_freeze_tedlium.py`, `experiments/scripts/stage_benchmark_helpers.py`

## Implementation Steps

1. Add regression assertions that all 20 frozen `reference_text` values exactly match selected Arrow rows after the documented ID normalization, and remain non-empty.
2. Test the endpoint-gating cases from Phase 1, including missing/corrupt receipt and cases where matrix parsing raises.
3. Update the speech fixture helper to detect zero-byte/truncated WAVs before `wave.open`; choose a real speech fallback available in the environment or skip the ASR-specific happy path with an explicit reason.
4. Keep tone fallback restricted to media-decoder plumbing tests; never treat it as spoken content or expected ASR output.
5. Run focused D2, endpoint, group 02/07 and executor tests; record exact command, exit code, pass/fail/skip counts.

## Success Criteria

- [x] TED-LIUM GT mapping regression proves exact equality for all frozen units.
- [x] Endpoint fail-open cases regress to blocked behavior before inference.
- [x] The Windows SAPI test no longer throws `EOFError` for an empty file; any skip is explicitly environmental and the actual ASR path still requires speech.
- [x] Focused test suite passes with all outcomes, including skips/failures, accurately reported.

## Risk Assessment

Changing fixtures to avoid a platform failure can accidentally turn an ASR test into a media-only check. Preserve separate assertions for valid spoken media and actual recognized text.
