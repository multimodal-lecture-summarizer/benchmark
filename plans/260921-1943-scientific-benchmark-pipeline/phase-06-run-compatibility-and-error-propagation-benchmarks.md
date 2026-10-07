---
phase: 6
title: "Run compatibility and error propagation benchmarks"
status: pending
priority: P1
dependencies: [5]
effort: "1-2 weeks compute and analysis"
---

# Phase 6: Run compatibility and error propagation benchmarks

## Overview

Kiểm tra giả thuyết quan trọng: thành phần tốt nhất riêng lẻ chưa chắc tạo pipeline tốt nhất. Chỉ ghép 2–3 Pareto candidates mỗi stage và dùng thiết kế screening có kiểm soát để tránh tích Descartes toàn bộ.

## Requirements

- Stage shortlist được freeze trước compatibility run.
- Oracle và predicted input dùng cùng downstream candidate để đo degradation.
- Error cascade phải perturb/rerun thật, không nội suy từ baseline.

## Architecture

`Stage Pareto shortlist -> constrained compatibility matrix -> oracle/predicted pairs -> controlled perturbations -> interaction analysis -> final pipeline shortlist`.

## Related Code Files

- Modify/create integration benchmark runner under `multimodal-lecture-summarizer/experiments/scripts/`
- Modify pipeline composition registry under `multimodal-lecture-summarizer/experiments/registry/`
- Reuse production modules under `multimodal-lecture-summarizer/ai_workers/` through adapters; do not fork hidden benchmark-only logic
- Modify notebook 06/07 generation and analysis

## Implementation Steps

1. Freeze 2–3 Pareto candidates/task; record why dominated candidates were dropped.
2. Define compatibility constraints: timestamps, label taxonomy, language, frame/token budget, context length, hardware and license.
3. Screening design: one-factor-at-a-time around a reference plus selected pairwise interactions; full factorial only khi số combo/budget cho phép.
4. Run oracle transcript vs predicted transcript for chaptering, summary và QA.
5. Run oracle scenes/chapters/evidence vs predicted equivalents; compute absolute and relative degradation.
6. Inject measured ASR substitutions/deletions, boundary shifts/misses, OCR corruption, detection misses và track switches at empirical severity; rerun downstream pipeline.
7. Test audio-only, visual-only, audio+visual và multimodal-with-evidence under equal budget.
8. Measure interaction effects and failure modes per video; inspect qualitative error cases using fixed sampling rule.
9. Select final 2–4 pipeline compositions for E2E, not a single winner prematurely.

## Success Criteria

- [ ] Compatibility matrix covers every selected component interface and rejects incompatible combos explicitly.
- [ ] Oracle-vs-predicted degradation is measured per video with CI.
- [ ] Error cascade uses real reruns and persists perturbed inputs/output artifacts.
- [ ] At least one cross-stage interaction is estimated where scientifically relevant.
- [ ] Final pipeline shortlist includes quality-first and deployable Pareto alternatives.
- [ ] If no composition dominates with adequate evidence, decision is `no_selection`/tie.

## Risk Assessment

- Combinatorial explosion: limit shortlist and pre-register screened interactions.
- Perturbation realism: derive severity/distribution from actual upstream errors, not arbitrary random noise.
