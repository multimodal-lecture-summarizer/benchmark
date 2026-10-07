# Brainstorm Report: Notebook Comparison Framework Redesign

**Date**: 2026-09-21
**Author**: Mavis (M3)
**Status**: Approved by user (4/4 design choices confirmed)
**Next**: Hand off to `/ck:plan`

---

## 1. Problem Statement

Project hiện tại có 7 notebook trong `experiments/notebooks/` (00-06) — mỗi cái đã so sánh nhiều candidates trong 1 task, nhưng có 6 vấn đề làm comparison **không công bằng**, dẫn đến khó chọn "optimal model" một cách khoa học:

| # | Vấn đề | Tác động |
|:-:|:-------|:---------|
| 1 | Hard-code candidates trong Step 1, không có registry | Khó thêm candidate mới, không có single source of truth |
| 2 | Sample size khác nhau (RQ0-V=1, RQ0-A=15, RQ1-3=20) | Không so sánh được chéo task |
| 3 | Không enforce compute budget per candidate | Có thể candidate "ăn gian" dùng nhiều FLOPs |
| 4 | Single composite score chưa chuẩn hóa (mỗi task metric riêng) | Không aggregate được across tasks |
| 5 | No ablation grid (chỉ so sánh end-to-end) | Không biết contribution từng thành phần |
| 6 | No inter-run reproducibility check | Không phát hiện non-determinism |

Đề cương (mục 2) yêu cầu đánh giá nhiều metrics: WER, Precision/Recall/mAP, ROUGE/BERTScore, processing time, success rate. Mỗi metric là 1 dimension, cần normalize + aggregate.

## 2. Approved Design Choices

| Decision | Choice | Lý do |
|:---------|:-------|:------|
| Scope | **Full redesign**: notebook mới + comparison dashboard | Cần unified framework |
| Sample policy | **Task-specific N** | Mỗi task có data constraints riêng |
| Scoring | **Multi-metric theo đề cương** (research thêm nếu thiếu) | Match đề cương yêu cầu |
| Ablation | **Có — với grid + cap 8 combinations/base** | Cân bằng compute vs coverage |
| Registry format | **YAML** | Human-readable, comment được |
| Dashboard | **Plotly.js (interactive)** | Drill-down UX |
| Old notebooks | **Archive + README redirect** | An toàn, có thể revert |
| Ablation strategy | **Cap 8 combinations/base** | Random sample nếu grid > 8 |

## 3. Target Architecture

```
experiments/
├── registry/
│   ├── candidates.yaml              # Centralized model registry
│   ├── ablation_specs.yaml          # 2^k grids per task
│   └── leaderboard_weights.yaml     # Multi-metric scoring per task
├── notebooks/                       # REFACTORED (9 notebooks)
│   ├── 00_dataset_eda_and_quality_audit.ipynb      # (giữ nguyên)
│   ├── 01_audio_asr_benchmark.ipynb                # Refactor
│   ├── 02_visual_scene_ocr_benchmark.ipynb         # Refactor: N video
│   ├── 02b_object_detection_benchmark.ipynb        # NEW (theo đề cương)
│   ├── 03_multimodal_chaptering_benchmark.ipynb    # Refactor: ablation
│   ├── 04_hierarchical_summarization_benchmark.ipynb # Refactor: multi-method
│   ├── 05_evidence_retrieval_qa_benchmark.ipynb    # Refactor
│   ├── 06_efficiency_pareto_error_cascading.ipynb  # Refactor
│   └── 07_cross_task_leaderboard.ipynb             # NEW: aggregate all tasks
├── dashboards/                      # AUTO-GENERATED HTML
│   ├── per_task_leaderboard.html    # Mỗi task 1 file
│   ├── cross_task_comparison.html   # Tất cả candidates × tất cả tasks
│   └── ablation_heatmap.html        # 2^k grid heatmap per task
├── scripts/
│   ├── registry_loader.py           # YAML → dataclass
│   ├── ablation_runner.py           # 2^k grid execution
│   ├── leaderboard_builder.py       # Multi-metric scoring
│   └── dashboard_renderer.py        # Plotly HTML generation
└── legacy_notebooks/                # ARCHIVED: 00-06 cũ
    ├── 00_dataset_eda_and_quality_audit.ipynb
    ├── 01_audio_asr_benchmark.ipynb
    ├── ... (7 files)
    └── README.md                    # Redirect + migration notes
```

## 4. Multi-metric Scoring

### 4.1 Per-task metric set (matching đề cương)

| Task | Metrics | Direction | Default Weight |
|:-----|:--------|:----------|:---------------|
| RQ0-A | WER, CER, RTF, success_rate | mixed | 0.4, 0.2, 0.2, 0.2 |
| RQ0-V | F1@2s, throughput, success_rate | mixed | 0.5, 0.3, 0.2 |
| RQ0-OD (new) | Precision, Recall, mAP@0.5 | higher | 0.3, 0.3, 0.4 |
| RQ1 | WindowDiff, F1@5s, success_rate | mixed | 0.5, 0.3, 0.2 |
| RQ2 | ROUGE-L, BERTScore, hallucination_rate, claim_density | mixed | 0.3, 0.2, 0.4, 0.1 |
| RQ3 | Recall@3, MRR, latency | mixed | 0.4, 0.4, 0.2 |
| RQ4 | Pareto(latency, VRAM, quality) | lower | Composite |

### 4.2 Normalized composite score

For each candidate c on task t:

```
score(c, t) = Σᵢ wᵢ × normalize(metricᵢ(c, t))
```

Where `normalize()`:
- For "higher better": `norm(m) = (m - min) / (max - min)` ∈ [0, 1]
- For "lower better": `norm(m) = (max - m) / (max - min)` ∈ [0, 1]
- For binary `success_rate`: 1.0 if m=1.0, else 0.0 (penalize hard)

### 4.3 Tie-breaking

1. Highest individual metric (theo weights)
2. Lowest std across seeds (stability)
3. Earliest registered timestamp (favor simpler model)

## 5. Ablation Grid Strategy

### 5.1 Per-task ablation toggles

| Task | Base candidates | Toggle variables | Combinations |
|:-----|:----------------|:-----------------|:-------------|
| RQ0-A | A0-A5 (6) | {denoise: on/off, vad: on/off} | 6 × 4 = 24, cap 8 → sample 8 |
| RQ0-V | V0-V3 (4) | {confidence_thresh: 0.2/0.4/0.6} | 4 × 3 = 12, cap 8 → sample 8 |
| RQ1 | C1-C6 (6) | {visual_snapping, dynamic_nms, pos_weight} | 6 × 8 = 48, cap 8 → sample 8 |
| RQ2 | S0-S4 (5) | {evidence_grounding: on/off} | 5 × 2 = 10, cap 8 → sample 8 |
| RQ3 | Q0-Q3 (4) | {rrf_k: 30/60/90} | 4 × 3 = 12, cap 8 → sample 8 |

### 5.2 Cap strategy

- Nếu total combinations > 8: random sample 8 với seed=42 (reproducible)
- Prefer sampling từ diverse regions (latin hypercube) thay vì pure random
- Log mọi sampled combination để audit

## 6. Candidates Registry Schema (YAML)

```yaml
# experiments/registry/candidates.yaml
version: "1.0.0"
last_updated: "2026-09-21"

candidates:
  - id: RQ0_A.A1_FasterWhisperSmall_GPU
    task: RQ0_A
    display_name: "Faster-Whisper Small (GPU)"
    model_class: faster_whisper.WhisperModel
    model_kwargs:
      model_size: small
      device: cuda
      compute_type: float16
    required_features: [audio.wav]
    compute_budget:
      max_vram_mb: 4096
      max_latency_ms: 5000
    family: transformer_asr
    reference_paper: "https://arxiv.org/abs/2309.09424"
    tags: [asr, gpu, baseline]

  - id: RQ1.C5_DecoupledCrossAttention
    task: RQ1
    display_name: "C5 — Decoupled Cross-Attention"
    model_class: benchmarks.models.chaptering.DecoupledCrossAttentionModel
    model_kwargs:
      d_ac: 32
      pos_weight: 4.0
      visual_snapping: true
    required_features: [text_features.pt, visual_features.pt, ocr_features.pt]
    compute_budget:
      max_vram_mb: 6144
      max_latency_ms: 30000
    family: cross_attention_transformer
    tags: [chaptering, multimodal, proposed]
```

```yaml
# experiments/registry/ablation_specs.yaml
RQ0_A:
  base_candidates: [RQ0_A.A0, RQ0_A.A1, RQ0_A.A2]
  toggles:
    denoise: [false, true]
    vad: [false, true]
  max_combinations_per_base: 8

RQ1:
  base_candidates: [RQ1.C1, RQ1.C2, RQ1.C3, RQ1.C4, RQ1.C5, RQ1.C6]
  toggles:
    visual_snapping: [true, false]
    dynamic_nms: [true, false]
    pos_weight: [true, false]
  max_combinations_per_base: 8
```

```yaml
# experiments/registry/leaderboard_weights.yaml
RQ0_A:
  wer: 0.4           # lower better
  cer: 0.2           # lower better
  rtf: 0.2           # lower better
  success_rate: 0.2  # binary
RQ1:
  window_diff: 0.5
  collar_f1_5s: 0.3
  success_rate: 0.2
RQ2:
  rouge_l: 0.3
  bertscore_f1: 0.2
  hallucination_rate: 0.4  # lower better
  claim_density: 0.1
RQ3:
  recall_at_3: 0.4
  mrr: 0.4
  latency_sec: 0.2  # lower better
RQ4:
  pareto_frontier: 1.0  # special: multi-dim Pareto
```

## 7. New Notebook Structure (uniform 7-step pattern)

Mỗi notebook 01-06 theo cấu trúc thống nhất:

```
[Cell 0] MD: Title + invariants
[Cell 1] PY: Step 0 — Imports + Load Registry + Seed
[Cell 2] PY: Step 1 — Run Ablation Grid (load candidates → execute)
[Cell 3] PY: Step 2 — Compute Per-task Metrics (multi-metric)
[Cell 4] PY: Step 3 — Statistical Comparison (Holm-Bonferroni với direction)
[Cell 5] PY: Step 4 — Per-task Leaderboard HTML (Plotly)
[Cell 6] PY: Step 5 — Aggregate to Cross-task Leaderboard (Notebook 07 input)
[Cell 7] PY: Step 6 — Export Results JSON (per-task leaderboard)
```

## 8. Implementation Phases (for /ck:plan)

### Phase 1: Registry + Loader (1 ngày)
- Tạo `experiments/registry/{candidates,ablation_specs,leaderboard_weights}.yaml`
- Tạo `experiments/scripts/registry_loader.py` (YAML → dataclass)
- Migration mapping từ existing candidates trong code → YAML

### Phase 2: Ablation Runner (2 ngày)
- `experiments/scripts/ablation_runner.py` — chạy 2^k grid với cap
- Random sampling reproducible (seed=42)
- Logging sampled combinations để audit

### Phase 3: Leaderboard Builder (2 ngày)
- `experiments/scripts/leaderboard_builder.py` — multi-metric scoring
- Normalize + composite + tie-breaking
- Export per-task JSON leaderboard

### Phase 4: Dashboard Renderer (1 ngày)
- `experiments/scripts/dashboard_renderer.py` — Plotly HTML generation
- 3 outputs: per-task, cross-task, ablation heatmap

### Phase 5: Refactor Notebooks (3 ngày)
- Update 6 notebooks 01-06 theo 7-step pattern
- Add Notebook 02b (Object Detection)
- Add Notebook 07 (Cross-task Leaderboard)

### Phase 6: Archive + Redirect (0.5 ngày)
- Move `experiments/notebooks/00-06` → `experiments/legacy_notebooks/`
- Create `README.md` ở `experiments/notebooks/` với redirect + migration notes

### Phase 7: Verification (1 ngày)
- Chạy thử 1 task end-to-end (vd RQ1)
- Verify dashboard render đúng
- Verify leaderboard pick winner đúng

**Total: ~10.5 ngày = ~2 tuần**

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|:-----|:-------|:-----------|
| Sample size too small cho statistical comparison | False winner | Cap N per task; document minimum N requirement |
| Ablation sampling bias | Miss optimal combo | Latin hypercube sampling + audit log |
| Dashboard chậm với Plotly trên browser | UX | Limit data size, lazy load per task |
| YAML drift (candidates.yaml lỗi thời) | Failed run | Add validation script check YAML ↔ code |
| Notebook 07 too large | Colab crash | Lazy load per task JSON |

## 10. Success Metrics

- [ ] `experiments/registry/candidates.yaml` chứa ≥30 candidates (RQ0-A:6, RQ0-V:4, OD:5, RQ1:6, RQ2:6, RQ3:4, RQ4:4 = 35)
- [ ] Mỗi notebook 01-06 chạy end-to-end trong <30 phút trên T4
- [ ] Dashboard HTML render được cho mỗi task
- [ ] Cross-task leaderboard pick 1 winner per task, với confidence interval
- [ ] Old notebooks accessible tại `legacy_notebooks/`
- [ ] Audit script check YAML ↔ code passes

## 11. Open Questions

1. **Cross-task composite**: Có cần 1 score tổng hợp across tasks không? (Vd: weighted average của mọi task scores) → Phase 2.
2. **User study**: Đề cương yêu cầu "đánh giá chất lượng bằng người dùng". Tích hợp vào leaderboard? → Phase 2.
3. **Live reload**: Có cần dashboard auto-update khi chạy xong 1 task không? → Nice-to-have.
4. **Federated across Colab sessions**: Mỗi session chạy 1 task riêng. Sync leaderboard ra sao? → Recommend GCS / S3 archive.

## 12. References

- **Đề cương** mục 2 (Lý thuyết) — metrics list
- **repro_manifest.json:D-T07** — Holm-Bonferroni standard
- **repro_manifest.json:D-T08** — Equal Budget Guardrails
- **benchmarks/metrics/statistics.py** — đã fix với `direction` parameter (turn này)
- **docs/ARCHITECTURE.md** — pipeline diagram

---

**Status**: ✅ Approved. Ready for `/ck:plan --tdd` hoặc `/ck:plan` default.
**Recommended**: `/ck:plan` default (greenfield new modules, không có existing test coverage trên registry/leaderboard).