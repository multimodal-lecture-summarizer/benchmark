## 2026-10-10 — TIB technical pilot before evaluation freeze

User-approved scope: RQ2 creator-abstract agreement and same-record RQ4 costs; OCR follows. Do not reopen unrelated media HOLDs. Audit confirms S3 changes boundary-constrained chunking, using S1's shared flattened map/reduce. Equal allocated map/final output caps do not mean equal actual tokens. Prepare nine source-length-selected train records, retain all failures, counterbalance arm order, record dispatches/VRAM/tokens and all scorers on Colab. CPU preparation executed; GPU pilot and <=12h feasibility unverified. Evaluation IDs/protocol and grouped uncertainty remain pending. Full 8,769-pool execution instruction is superseded by pilot-first. Historical results remain historical.

# Decisions Log

## D-EDA-20261010 — Seven-dataset qualification follow-up

**Subsequent scope clarification:** [the claim matrix](../../../../plans/reports/research-scope-261010-1621-claim-qualification-report.md) and [machine-readable claim register](../../../experiments/registry/datasets/claim-qualification-261010.json) distinguish usable narrow comparisons from blocked broader claims. TIB text-only abstract agreement, OCR crop recognition and LVVO released-image detection have evidence available for scoped protocols. Missing original videos do not impose a universal veto. Previous HOLD decisions retain their original endpoint scope; no cohort is automatically frozen and no benchmark was started.

**Decision:** preserve all historical outputs and original labels; add hash-bound ID ledgers and executed qualification cells. The [current register](../../../experiments/registry/datasets/qualification-261010.json) and [report](../../../../plans/reports/dataset-qualification-261010-report.md) supersede older availability and eligibility claims.

- TED-LIUM: EXCLUDE eight source ignore-marker segments from scored ASR; retain 42 bounded diagnostic candidates. Original Arrow recovery and full intended-cohort media remain HOLD.
- IIIT-CVID: full 5,475-frame ZIP review completed; allow 120 derived dimension overrides only. Hold 22 boxes on 20 frames and the complete 469-pair source/content review queue. No clipping or text edits.
- LVVO: 39 public source-token matches are documented; 100 groups and underlying media/rights remain unresolved. Save group-split design only, with zero assigned roles.
- Remaining four sources: ledger structural findings separately from original-media and target-label qualification. Preserve uncertain timestamp interpretations and board/keyframe semantics; never manufacture GT.
- All seven native test references inspected in EDA are observed references. No unseen-final-test claim, no scientific cohort/protocol freeze and no new model benchmark follows from this review.

**Status:** bounded review executed; scientific endpoint gates remain HOLD. No large model evaluation was initiated by this review.

> **Historical decisions (2026-08/09), not the active execution protocol.** Several RQ1–RQ4, TIB cohort, human-scoring and VISTA-priority decisions below were superseded. Use [BENCHMARK.md](../../../docs/BENCHMARK.md), [DATASET_EDA.md](../../../docs/DATASET_EDA.md) and the current [RQ2 plan](../../../plans/261002-0946-rq2-controlled-summarization/plan.md) for current scope. This file remains because `docs/frozen_decisions.json` and model-code comments cite it.

All strategic and technical decisions that affect reproducibility, scope, or timeline are recorded here.
Answers to the four Pending Decisions (README) are added here as they are resolved.

---

## Technical decisions (frozen)

### D-T01 — E4 compact VLM baseline
**Decision:** `Qwen3-VL-4B-Instruct` FP16 is the primary E4/C7 row.  
**Rationale:** Fits T4 16 GB with headroom (~10 GB weights); no quantization confound; DocVQA 91.  
**Optional row:** `Qwen3-VL-8B-Instruct` AWQ only if 10-video VRAM pilot confirms <12 GB peak.  
**Action required:** Pin exact HF commit hash after Week-1 pilot. Record here.  
**HF commit hash:** _(fill after pilot)_  
**Source:** `reports/260830-1917-dataset-vlm-research.md` §6.

---

### D-T02 — C5 and C6 architecture
**Decision:**
- C5 (Full learned fusion) = 4-layer cross-attention transformer, 256-dim hidden, text/visual/OCR projected to shared 256-dim token space, 3 learned [CLS]-style boundary tokens, supervised with binary cross-entropy on boundary positions.
- C6 (Full late fusion) = same as C5 but with concatenation-only fusion, no cross-attention; directly ablates the fusion mechanism.  
**Rationale:** Frozen before M3 so ablation is interpretable. Any architecture change requires a new variant ID.  
**Status:** Frozen.

---

### D-T03 — C7 / E4 identity
**Decision:** C7 (RQ1 compact VLM baseline) and E4 (RQ4 efficiency row) are the same `Qwen3-VL-4B-Instruct` FP16 checkpoint. Feature caches are shared; no double-running.  
**Status:** Frozen.

---

### D-T04 — OCR and visual embedder
**Decision:**
- OCR = PaddleOCR v3 (`ch_PP-OCRv4`), confidence threshold 0.6.
- Visual embedding = DINOv2 ViT-S/14 (`dinov2_vits14`, 384-dim).
- Keyframe sampling = TransNetV2 scene-boundary detector; fallback 1 fps.  
**Action required:** Record model revision/tag and freeze before precompute step (Week 7).  
**Model revisions:** Visual: `torch.hub/facebookresearch/dinov2:dinov2_vits14`, OCR: `paddleocr:ch_PP-OCRv4`, ASR: `openai/whisper-small` (Schema frozen in `benchmarks/core/feature_store.py`).  
**Status:** Frozen & verified in Phase 2.

**RQ1 learned-feature implementation amendment (2026-09-30, before validation scoring):** The locked 20-unit cohort's learned path uses the official Facebook Hugging Face distribution `facebook/dinov2-small` at commit `ed25f3a31f01632728cabb09d1542f84ab7b0056`, taking its 384-dimensional CLS vector. This replaces the `torch.hub` loading route above; bitwise equivalence of the two packaging routes has not been established, so record the implementation difference. Text uses `sentence-transformers/all-MiniLM-L6-v2` commit `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. TransNetV2 is absent in the local environment, so the predeclared 1-fps fallback is applied to the same frames for DINOv2 and OCR. Audio uses 16 kHz mono, 32-band log-mel means on a two-second grid. This amendment changes no GT, cohort, split, boundary labels, or model-result-based sample decision. Full learned extraction and training have not run yet.

---

### D-T05 — VISTA has no transcript field
**Decision:** The manifest assumption "can use provided transcripts/video features if raw video access is limited" is **wrong and removed**. VISTA ships no ASR transcript. Text-only VISTA requires self-ASR on raw video (out of scope unless media is fully downloaded and ASR is budgeted).  
**Fallback:** If VISTA media unavailable after 2-week gate, TIB (`gigant/tib-bench`) becomes primary; abstractive claim narrows to scientific presentations.  
**Source:** `reports/260830-1917-dataset-vlm-research.md` §1.  
**Status:** Frozen.

---

### D-T06 — TIB evaluation target
**Decision:** RQ2 external validation uses `gigant/tib-bench` test subset (80 records, zero leakage confirmed by probe 2026-08-30). Multimodal evidence = `slides` column (PIL PNG 512×288). No video decoding needed for slide evidence.  
**Source:** `reports/260830-1917-tib-audio-visual-probe.md` §2–4.  
**Status:** Frozen.

---

### D-T07 — Multiple-comparison correction
**Decision:** Holm-Bonferroni within each RQ family at α = 0.05.  
Families: RQ1 ablations (4 deltas: C2−C1, C3−C1, C4−C1, C5−C6), RQ2 S-pairs (4: S1−S0, S3−S1, S4−S3, S2−S1 where applicable), RQ3 Q-pairs (3: Q1−Q0, Q2−Q0, Q3−Q2).  
Report both raw p-values and Holm-corrected p-values. Effect size = Cohen's d; Hedges' g correction when n < 20. Bootstrap 95% CI.  
**Status:** Frozen.

---

### D-T08 — Equal-token-budget enforcement
**Decision:** If S3/S4 cannot fit the same source/output token budget as S1, that run is classified as **failed**, not as a "separate scaling curve." The hierarchical method must be reduced (shorter chapter summaries, scene selection) until budget matches. Any reduction is reported as an ablation.  
**Status:** Frozen.

---

### D-T09 — HF model cache location
**Decision:** HF model weight cache is stored on Colab **local SSD** (`/root/.cache/huggingface`). Google Drive is used only for **finished feature stores** (precomputed embeddings, prediction caches), not model weights.  
**Rationale:** Drive sync can corrupt partial writes; re-downloading 10 GB on session start is cheaper than debugging a corrupted cache.  
**Status:** Frozen.

---

### D-T10 — Human eval power analysis
**Decision:** Before running the full 50-video human eval, run a 10-video pilot (Week 13) to estimate within-video variance. Back-solve required n for d = 0.3 and d = 0.5 at 80% power. If required n > 50, expand the eval set and reduce the custom evidence subset (scope-cut order updated in `05-6month-timeline.md`).  
**Pilot results:** _(fill after Week-13 pilot)_  
**Final n:** _(fill after pilot)_  
**Status:** Protocol frozen; n to be determined Week 13.

---

### D-T11 — S2 oracle diagnostic on TIB
**Decision:** Attempt to construct oracle chapter inputs on TIB using `keyframes.timestamp` boundaries. If ≥ 80% of test videos have ≥ 3 segments, run S2 there and report. If not feasible, move S2 to appendix and remove from primary TIB table.  
**Week-14 deliverable:** Confirm feasibility and record here.  
**Status:** Pending confirmation Week 14.

---

### D-T12 — Three-tier summarization fallback
**Decision:**
1. **VISTA primary + TIB external → NOMINAL PATH ACTIVE.** (VISTA access approved on 2026-08-31 on Hugging Face `dongqi-me/VISTA`).
2. TIB primary if VISTA media decode/processing fails.
3. If both fail: narrow to RQ1 (YTSeg) + RQ3 (EduVidQA + custom), submit as short paper; no abstractive summarization claim.  
**VISTA Approval Date:** 2026-08-31  
**Status:** Nominal Path 1 Active.

---

### D-T13 — API evaluation date pinning
**Decision:** API track evaluation is run on a single fixed date (record here). If the API model is updated between pilot and final run, re-run on the same frozen items and note the model version change. Do not report results from two different API snapshots as comparable.  
**API evaluation date:** _(fill at run time)_  
**API model snapshot/version:** _(fill at run time)_  
**Status:** Protocol frozen; values to be filled at run time.

---

### D-T14 — Reference quality audit rubric
**Decision:** Per-record audit schema: `id, source_support (0–2), coverage (0–2), style (summary-like / boilerplate / mixed), action (keep / flag / exclude)`. Calibration: both annotators audit the same 20-record set independently; resolve disagreements before proceeding to the full 100. Exclusion list frozen before any system output is generated.  
**Source:** `reports/260830-1917-dataset-vlm-research.md` §5.  
**Status:** Frozen.

---

### D-T15 — Real-data-only policy (no mock / no synthetic research data)
**Decision:** **Toàn bộ dữ liệu nghiên cứu phải là dữ liệu thật (100% real datasets). Cấm mọi hình thức mock/synthetic/phát sinh giả cho kết quả nghiên cứu.**  
**Scope:**
- **Cấm:** `torch.randn`/`np.random.randn`/`np.random.uniform` để tạo features, boundaries, transcripts, OCR, QA; template-fake OCR (`Slide Concept…`, `Key Slide…`); answer-leak (`...confirms: {ans_text}`); `cumsum` heuristic boundaries; synthetic/mocked benchmark items; placeholder stats.
- **Cho phép:** (a) `torch.randn` chỉ cho `nn.Parameter` init (ví dụ `chaptering.py:279 boundary_tokens *0.02`) và `statistics.py` bootstrap RNG `np.random.default_rng`; (b) tổng hợp thống kê `synthetic_*` trong `generate_large_testset.py` không phải research claim (phải ghi rõ `notes: synthetic …` và không vào bảng kết quả RQ); (c) `unittest.mock` chỉ trong `tests/`; (d) LLM fallback `DeterministicAbstractiveEngine` là **phương thức suy luận**, không phải dữ liệu giả.
- **Thực thi:** Mọi notebook/script trước full run phải qua `grep` sweep: `torch.randn` ngoài `chaptering.py`, `np.random.randn/uniform` trong `experiments/notebooks/`, `ans_text` trong evidence, `Slide Concept` template → phải =0. `P2` thay `02_phase2` mock embeddings/boundaries bằng real `cached_features/*.pt` + real `C1–C6` inference; `P6` verification gate fail nếu phát hiện mock trong research path. `pilot_qualification_runner.py` synthetic sanity vectors giữ lại chỉ để validate metric impl, không tính vào RQ tables.
- **Ngoại lệ duy nhất:** Nếu dữ liệu thật thiếu (ví dụ `probes/cache` mất), phải **fail-loud** + ghi `missing_data_report.md`, không tự sinh mock thay thế.  
**Source:** User request 2026-09-01 “toàn bộ phải là dữ liệu thật, không dùng mock nữa” + audit 2026-09-01 (`NOTEBOOKS_ASSESSMENT.md`).  
**Status:** Frozen 2026-09-01.  
**Decided by:** owner (user) + plan maintainer  
**Date decided:** 2026-09-01

---

## Strategic decisions (answered 2026-08-31)

### D-S01 — Primary output: thesis or paper?
**Question:** Is the primary deliverable a graduation thesis, a conference paper, or both?  
**Decision:** **Khóa luận tốt nghiệp kết hợp bài báo hội nghị (Thesis + Paper track).**  
**Impact & Workflow:** Bản thảo luận văn chi tiết được hoàn thiện đầy đủ trong các tuần 21–24; sau đó trích xuất và rút gọn thành định dạng bài báo hội nghị chuẩn (camera-ready template) trong tuần 25–26 để chuẩn bị nộp ấn phẩm.  
**Decided by:** Supervisor + owner  
**Date decided:** 2026-08-31  
**Status:** Decided.

---

### D-S02 — Vietnamese evaluation: mandatory or future work?
**Question:** Is Vietnamese-language evaluation mandatory for the project deliverable?  
**Decision:** **Tiếng Anh là ngôn ngữ nghiên cứu chính; tiếng Việt là Future Work / Scope-cut #1.**  
**Impact:** Toàn bộ benchmark chính và so sánh mô hình tập trung trên các bộ dữ liệu chuẩn tiếng Anh (YTSeg, VISTA, TIB, EduVidQA, VT-SSum). Tiếng Việt không làm thay đổi timeline 26 tuần mà được xem như hướng ứng dụng mở rộng.  
**Decided by:** Supervisor + owner  
**Date decided:** 2026-08-31  
**Status:** Decided.

---

### D-S03 — Second annotator: committed for 26 weeks?
**Question:** Is a second human annotator available and committed for the full project duration?  
**Decision:** **Không có người gắn nhãn thứ 2; chuyển sang giao thức Pre-labeled Ground Truth + Single Human Audit + LLM-as-a-Judge.**  
**Impact:** 
1. **Dữ liệu:** Tận dụng 100% các bộ dữ liệu đã có sẵn nhãn chuẩn (pre-labeled ground truth): YTSeg (creator chapters), TIB-bench (slides + transcript segments alignment), EduVidQA (5,252 QA pairs có timestamp). Không tự gán nhãn thủ công từ đầu.
2. **Đánh giá tóm tắt (RQ2):** Thay thế giao thức 2-rater Cohen's Kappa bằng quy trình thẩm định 1 người (Single-Author Quality Audit trên 20–50 video pilot) kết hợp bộ tiêu chí đánh giá tự động đa chiều LLM-as-a-Judge (G-Eval, AlignScore/Factuality, Salient QA F1, ROUGE-L, BERTScore).  
**Decided by:** Supervisor + owner  
**Date decided:** 2026-08-31  
**Status:** Decided.

---

### D-S04 — Data release: IDs/features only, or source media too?
**Question:** May the project release source media in addition to IDs and derived features?  
**Decision:** **Chỉ phát hành IDs, Manifests, Precomputed Features và Reproduction Scripts.**  
**Impact:** Không phân phối lại (redistribute) video thô để tránh xung đột bản quyền (YouTube/TIB/VISTA TOS). Người dùng muốn tái tạo sẽ chạy script tự động tải hoặc sử dụng feature embeddings đã đóng gói sẵn.  
**Decided by:** Supervisor + owner  
**Date decided:** 2026-08-31  
**Status:** Decided.
