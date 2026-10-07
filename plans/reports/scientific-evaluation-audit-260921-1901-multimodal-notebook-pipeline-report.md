---
type: researcher
date: 2026-09-21
scope: experiments/notebooks 00-07 and directly linked benchmark artifacts
evidence_status: current-worktree-read-only-audit
---

# Research Report: Audit tính khoa học của bộ notebook benchmark pipeline đa phương thức

## Tóm tắt

**Kết luận: chưa đạt mức đánh giá khoa học đủ để chọn “thành phần tốt nhất” ở từng tác vụ, và chưa đủ để kết luận pipeline ghép nối là tốt nhất.**

Bộ notebook có kiến trúc ý tưởng đúng hướng: tách ASR, scene/OCR, object detection, chaptering, summarization, retrieval/QA, efficiency và leaderboard. Tuy nhiên bằng chứng thực nghiệm hiện tại bị chặn bởi lỗi thực thi, dữ liệu giả/proxy, ground truth không độc lập, candidate không được chạy đúng, thống kê không hợp lệ và thiếu chuỗi provenance từ input đến raw prediction.

Trạng thái nên công bố hiện tại:

- `00_dataset_eda_and_quality_audit.ipynb`: **executed_descriptive_only / audit_claims_unverified**.
- `01`–`07`: **not_run / inert_notebook**.
- Các JSON ngày 2026-09-05: **legacy aggregate artifacts / provenance chưa đủ**, không phải output của notebook hiện tại.
- Chưa được phép ghi `best model`, `winner`, `SOTA`, `accepted hypothesis`, `scientifically validated`, hoặc `end-to-end benchmark passed`.

## Mục lục

1. Phạm vi và phương pháp
2. Phát hiện chặn toàn bộ
3. Đánh giá từng notebook
4. Đối chiếu với đề cương
5. Vì sao “best từng stage” chưa chắc tạo “best pipeline”
6. Protocol khoa học đề xuất
7. Thứ tự ưu tiên sửa
8. Tiêu chí hoàn thành
9. Nguồn tham khảo
10. Câu hỏi chưa giải quyết

## 1. Phạm vi và phương pháp

Audit đọc trực tiếp:

- 9 notebook hiện tại trong `multimodal-lecture-summarizer/experiments/notebooks/`.
- Notebook generator, registry, ablation runner, leaderboard builder.
- Benchmark runners RQ0-A/V/OD, RQ1–RQ4 và error cascading.
- Dataset/cache manifests, feature extractor, report JSON, reproducibility manifest.
- `tests/test_validation_gate.py` và chạy lại test trên trạng thái hiện tại.

Tiêu chí:

- Ground truth, dataset split, license/provenance, checksum.
- Candidate parity, preprocessing, budget và hardware.
- Raw predictions, per-unit metrics, failure denominator.
- CI, paired test, effect size, multiple-comparison correction.
- Leakage, proxy/fallback/synthetic status.
- Khả năng tái lập và khả năng truy vết từ notebook đến kết quả.
- Tính phù hợp với đề cương và khả năng tích hợp end-to-end.

Chuẩn đối chiếu: NeurIPS Paper Checklist yêu cầu chi tiết split/hyperparameter, lệnh và môi trường tái lập, error bars/CI/significance kèm nguồn biến thiên; tài liệu ACL nhấn mạnh chọn kiểm định theo task/setup/metric và tránh misuse của significance testing.

## 2. Phát hiện chặn toàn bộ

### 2.1 Notebook 01–07 không thực thi code

Generator dùng:

```python
"source": source.split("\n")
```

nhưng không giữ newline ở từng phần tử. Theo cách notebook ghép trường `source`, mỗi cell trở thành một dòng duy nhất. Vì mọi code cell bắt đầu bằng `# Step ...`, toàn bộ cell là comment/no-op.

Bằng chứng hiện tại:

- Notebook 01–07: mọi `execution_count = null`, không output.
- 01–06 có cùng code hash.
- Mỗi notebook có 7/7 code cell khi đọc bằng `nbformat` chỉ còn một physical line bắt đầu bằng `#`.
- Compile vẫn “pass” vì một dòng comment là Python hợp lệ; đây là false pass, không phải chạy thành công.
- `execute_all_notebooks.py` còn bỏ qua `02b` và `07`.

### 2.2 Tất cả notebook stage chạy sai task và dùng mock nếu sửa newline

Notebook 01–06 đều chứa:

```python
TASK = TaskID.RQ1  # CHANGE THIS per task
DRY_RUN = True
```

Hệ quả:

- ASR, visual, object detection, summarization, QA, efficiency đều trỏ về chaptering RQ1.
- `DRY_RUN=True` gọi `_mock_metrics()`, sinh metric từ hash và seed; không chạy model.
- Runtime `0.01s`, VRAM `0.0` có thể được ghi như kết quả thành công.
- Python built-in `hash()` còn phụ thuộc process salt, nên sampling được gọi “reproducible” chưa chắc lặp lại giữa process.

### 2.3 Real mode vẫn không tạo bake-off

`ablation_runner.py` chỉ log toggle, không truyền toggle/candidate vào runner. Mọi combo của cùng task chạy lại một baseline command giống nhau.

Ngoài ra:

- CLI option giữa dispatcher và runner không khớp (`--data-dir` so với `--data_dir`, seed string so với `nargs="+"`).
- Parser output mong một contract mà runner không in.
- Subprocess exit 0 có thể thành `success=True` dù metrics rỗng.
- Candidate registry, notebook scope và candidate thực thi không nhất quán.

### 2.4 Leaderboard và thống kê không hợp lệ

- Notebook lấy mean qua seed trước, rồi tái tạo đúng một `ComboResult`/combo với `seed=42`.
- CI của winner vì vậy có thể thành `[0, 0]`.
- `holm_bonferroni_family` được import nhưng không gọi.
- `pairwise_comparisons` để trống.
- Bootstrap trên 3 seed/composite không thay thế hierarchical bootstrap theo video/talk.
- Missing metric bị điền `0.0`; normalizer có thể thưởng dữ liệu thiếu.
- Pareto hiện so scalar composite, không phải frontier đa chiều quality–latency–VRAM–cost.
- Cross-task composite so các metric khác dataset/GT/đơn vị, không chứng minh tính tương thích của một pipeline.

### 2.5 Validation gate 15/15 là false assurance

Đã chạy lại:

```text
15 passed in 109.97s
HEAD 4d2a33e30213d7e07a89416454f12fceb0376d33
```

Nhưng gate không chứng minh benchmark hiện tại:

- Test “no mock” chỉ cấm 3 chuỗi: `synthetic_test_qa`, `mock_features`, `uniform_gold`.
- Không cấm `DRY_RUN=True`, `_mock_metrics`, hard-coded result hay fallback/proxy.
- Không kiểm tra `02b` và `07`.
- Nhiều test chỉ đọc aggregate JSON và assert số vượt ngưỡng; không tái chạy model hoặc truy raw prediction.
- Report validation cũ ngày 2026-09-05 không xác nhận notebook untracked mới ngày 2026-09-21.

### 2.6 Dataset/cache có lỗi nghiêm trọng

Audit 20 `.pt` cached features phát hiện:

- 10/20 có visual features toàn zero.
- 17/20 có GT timestamp vượt quá duration khai báo.
- 5/20 không có positive target.
- 579 raw GT timestamps bị collapse thành 25 target labels.
- Ví dụ `CA01`: duration khai báo 11 giây nhưng GT tới 1068 giây; visual toàn zero.

Feature extractor cho phép:

- Hash embedding fallback.
- Acoustic proxy thay vì acoustic representation đo được.
- Boundary từ CLIP/SSIM hoặc fallback mỗi 30 giây.
- Zero visual placeholder.
- OCR feature xấp xỉ từ phrase trong transcript.

Do đó tuyên bố `0 synthetic labels, 100% authentic multimodal features` hiện không đứng vững.

### 2.7 Notebook 00 chỉ đủ cho EDA mô tả

Notebook 00 đã chạy và profiling được TED-LIUM, EduVidQA, SlideVQA, IIIT-CVid, cached core và TVSum metadata. Đây là phần có ích.

Nhưng “quality audit” mạnh nhất bị hard-code:

- `keep_count = total_lectures`.
- `keep_rate_pct = 100.0`.
- source support và coverage đều `2.0/2.0`.
- `flagged_count = excluded_count = 0`.
- zero-leakage và equal-budget tự gán PASS.

Không có audit sheet, reviewer labels, annotation instructions, disagreement resolution hay inter-rater agreement để sinh các số này.

Provenance cũng chưa đủ:

- TED-LIUM có citation/license nhưng thiếu revision/checksum gắn run.
- SlideVQA trỏ tới checksum manifest không tồn tại.
- IIIT-CVid có SHA256 và cảnh báo research-only, khá hơn các bộ khác.
- EduVidQA, TVSum và cached core thiếu source-rights record đầy đủ.
- Frozen v2 chỉ là 5 item `ytseg_dry_*`; v1 có placeholder-looking checksums và ID `eduvidqa_train_syn_001`.

## 3. Đánh giá từng notebook

| Notebook | Trạng thái | Kết luận khoa học |
|---|---|---|
| `00_dataset_eda_and_quality_audit` | Partial | EDA thực; audit/provenance claims chưa đo độc lập |
| `01_audio_asr_benchmark` | Invalid/not_run | No-op, sai task, dry mock; standalone runner chỉ là pilot 15 mẫu |
| `02_visual_scene_ocr_benchmark` | Invalid/not_run | Scene GT vòng tròn; OCR không có accuracy GT/candidate comparison |
| `02b_object_detection_benchmark` | Scaffold only | Không có box GT; P/R/mAP là `None`; chưa có tracking |
| `03_multimodal_chaptering_benchmark` | Proxy only/not_run | Cached GT/proxy lỗi; ablation không chạy thật; CI/stat invalid |
| `04_hierarchical_summarization_benchmark` | Invalid/not_run | Chạy nhầm RQ1; runner dùng GT boundary như prediction và reference summary heuristic |
| `05_evidence_retrieval_qa_benchmark` | Invalid/not_run | Chạy nhầm RQ1; thiếu evidence timestamp; metric có fallback constant |
| `06_efficiency_pareto_error_cascading` | Invalid/not_run | Chạy nhầm RQ1; latency/VRAM/quality hard-code; không perturb và rerun pipeline |
| `07_cross_task_leaderboard` | Invalid/not_run | Load JSON không kiểm provenance/status; có thể overwrite RQ1 bằng dry output |

### 3.1 ASR

Standalone runner có nền tảng: TED-LIUM local test, WER/CER/RTF/latency, per-sample score, hardware metadata và bootstrap code. Artifact cũ cho thấy từng chạy 15 mẫu trên RTX 4050.

Chưa đủ chọn model vì:

- Notebook, registry và runner liệt kê candidate khác nhau.
- Runner thực tế chỉ so Faster-Whisper `base.en`, `small.en` GPU và `small.en` CPU.
- DeepFilterNet là preprocessing toggle, không phải ASR decoder độc lập.
- 15 mẫu đầu tiên không random/stratify theo talk/speaker/duration/noise.
- Seed lặp deterministic inference không tạo 3 observation độc lập.
- WER/CER bị cap 100%; WER hợp lệ có thể >100%.
- “p-value” không phải paired permutation/bootstrap chuẩn.
- Không lưu sample ID, reference, hypothesis, failure per sample.
- Quality comparison và deployment comparison CPU/GPU bị trộn.

Trạng thái: **pilot engineering result**, chưa phải model-selection evidence.

### 3.2 Scene detection và OCR

- Scope nói ≥5 EduVidQA videos; runner dùng 1 video `CA01`.
- Output ContentDetector được dùng làm reference rồi chấm ContentDetector với chính nó: circular GT/leakage.
- Candidate tuyên bố và candidate chạy không khớp.
- OCR chỉ chạy PaddleOCR trên tối đa 10 frame được ContentDetector chọn.
- OCR chỉ đếm word/character và tốc độ; không có CER/WER/exact match/detection F1 hay model khác.

Trạng thái: timing pilot; **quality benchmark invalid**.

### 3.3 Object detection và tracking

- `ground_truth_objects` không được điền.
- Precision, Recall, mAP50 được trả `None`.
- Sampling 8 frame đều theo thời gian, không theo scene/object density.
- Không có raw boxes, per-class AP, confidence calibration, failure log.
- Chưa có output benchmark chính thức.
- Hoàn toàn chưa có tracker candidates, track GT, HOTA, IDF1, MOTA, ID switches hoặc fragmentation.

Tài liệu `OUTLINE_MAPPING.md` ghi Object Detection & Tracking “done” và P/R/mAP “sẽ đo” nhưng đánh dấu done. Đây là implemented-feature status bị trộn với scientific-evidence status.

### 3.4 Chaptering

- Scope C1–C6 nhưng ablation chỉ C1/C3/C5.
- Cached boundaries có lỗi thời gian và proxy từ scene/keyframe.
- Split random lại theo seed trên 20 video, thiếu lecturer/source-disjoint guard.
- Không có raw per-video boundary predictions.
- Kết quả cũ tự ghi Holm-corrected p-value không significant; không được kết luận superiority.

### 3.5 Summarization

Runner hiện có các shortcut làm mất giá trị benchmark:

- `pred_boundaries = gt_boundaries`.
- Reference summary tạo heuristic từ câu đầu/giữa/cuối.
- Hallucination rate bị gán các hằng số theo system.
- Thiếu BERTScore thực thi, human factuality, blind rating, inter-rater agreement và raw generated summaries.

ROUGE/BERTScore là cần nhưng chưa đủ; với multimodal summary cần claim-level support/factuality và coverage.

### 3.6 Retrieval/QA

- Nhiều QA không có evidence timestamp/span.
- Khi thiếu GT, Recall@k có fallback constant theo tên model.
- “OCR” cho Q3 được tổng hợp từ transcript, không phải modality độc lập.
- Không lưu ranked list theo query, retrieved evidence, answer, citation correctness.

### 3.7 System/Pareto/error cascade

- Latency/VRAM/failure/quality có phần hard-code.
- Error cascade nội suy từ baseline, không thêm nhiễu thật rồi rerun.
- Không có length buckets, repeated cold/warm runs, timeout/OOM denominator.
- Không có end-to-end video-level raw result cho một config pipeline cố định.

## 4. Đối chiếu với đề cương

| Yêu cầu đề cương | Hiện trạng | Cần bổ sung |
|---|---|---|
| Speech-to-Text: WER | Pilot 15 mẫu | Frozen test, full candidate bake-off, per-talk CI, CER/RTF/failure |
| Scene/video segmentation | Circular GT | Human/official boundary GT, multi-video, collar F1, over/under-segmentation |
| OCR/visual representation | Descriptive/timing | OCR GT, CER/WER/word accuracy, detection/recognition tách riêng |
| Object Detection: P/R/mAP | `None` | Box/class GT, mAP50-95, AP50, per-class AP, calibration |
| Object Tracking | Missing | Tracker bake-off, trajectory GT, HOTA/IDF1/MOTA/IDSW |
| Video summarization: ROUGE/BERTScore | Aggregate legacy/proxy | Real generated summaries, native references, factuality + human eval |
| LLM/multimodal analysis | Code paths/fallbacks | Fixed prompt/model revision, raw outputs, failure/fallback accounting |
| System time/success/video lengths | Hard-coded/aggregate | Direct E2E measurement, cold/warm, length strata, timeout/OOM/failure |
| Compare models/methods | Registry/scaffold | Same split/budget/hardware, real execution, paired statistics |
| Select and integrate components | Not demonstrated | Stage shortlist + compatibility bake-off + E2E ablation/error cascade |

Kết luận đối chiếu: đề cương được **phủ về tên module**, nhưng chưa được **đáp ứng về bằng chứng khoa học**. Tỷ lệ “~93% đáp ứng đề cương” trong `OUTLINE_MAPPING.md` không nên dùng cho phần nghiên cứu/thực nghiệm.

## 5. Vì sao “best từng stage” chưa chắc tạo “best pipeline”

Chiến lược đúng không phải chọn độc lập một winner rồi ghép ngay. Error distribution giữa stage tương tác:

- ASR có WER thấp nhất có thể làm mất timestamp/word confidence cần cho chaptering.
- Scene detector F1 cao nhất có thể tạo quá nhiều keyframe, làm OCR/VLM chậm hoặc vượt budget.
- OCR accuracy cao nhất trên word crops có thể không tốt nhất trên keyframe thực tế.
- Summarizer tốt với oracle chapters có thể suy giảm mạnh với predicted chapters.
- Retriever tốt trên clean transcript có thể yếu khi nhận ASR lỗi.

Quy trình cần hai tầng:

1. **Stage-level Pareto shortlist:** giữ 2–3 candidate không bị dominate theo quality, latency, memory/cost và failure rate.
2. **Compatibility/end-to-end bake-off:** ghép shortlist có kiểm soát, chạy trên cùng video, thêm oracle/predicted conditions và ablation để đo error propagation.

Kết quả cuối cần tách:

- `research_best`: ưu tiên chất lượng, đủ significance/practical effect.
- `deployable_best`: nằm trên Pareto frontier và thỏa resource/SLA.
- `no_selection`: bằng chứng chưa đủ.

## 6. Protocol khoa học đề xuất

### 6.1 Gate 0 — Sửa tính thực thi và evidence status

- Sửa notebook source giữ newline/cell ID.
- Gán đúng task cho từng notebook.
- Default official notebook là `DRY_RUN=False`; mock chỉ ở test riêng và watermark rõ.
- Mỗi run tạo `run_id`, status `real|dry|proxy|failed|partial`.
- Không overwrite legacy report khi run chưa pass evidence gate.
- Execution script phải bao gồm đủ notebook 00, 01, 02, 02b, 03–07.

### 6.2 Gate 1 — Freeze protocol trước test

Mỗi endpoint phải có:

- Dataset source/revision/license/access/right-to-redistribute.
- SHA256/checksum, schema version, sample manifest.
- Train/validation/test frozen; lecturer/source-disjoint nếu có thể.
- Unit độc lập: video/talk, không inflate `n` bằng frames/words/chunks/questions.
- Primary/secondary metrics và practical-significance threshold định trước.
- Candidate, model weight revision, preprocessing, prompt, token/frame budget.
- Hardware/software/container/command/seed.
- Missing/failure policy: `not_run`, `not_eligible`, `proxy_only`, `failed`; không điền 0.

### 6.3 Stage benchmark tối thiểu

| Stage | GT và unit | Candidate design | Primary metrics |
|---|---|---|---|
| ASR | TED-LIUM test theo talk/speaker; thêm corpus phù hợp ngôn ngữ đích | ASR decoder × denoise × VAD factorial | Corpus WER, macro WER, CER, RTF, latency, failure |
| Scene | Human/official boundaries; video là unit | Content/Adaptive/Threshold/TransNetV2 cùng input | P/R/F1 tại collar, over/under-segmentation, FPS |
| OCR | IIIT-CVid/LectureVideoDB hoặc annotated frames | Paddle/EasyOCR/Tesseract, detection và recognition tách | CER, WER, exact/word accuracy, det P/R/F1, latency |
| OD | Lecture-domain box/class GT; video là unit | YOLO/RT-DETR/open-vocab với common taxonomy | mAP50-95, AP50, per-class AP, P/R, latency/failure |
| Tracking | Trajectory/identity GT | Detector+tracker pairs | HOTA, IDF1, MOTA, IDSW, fragmentation |
| Chaptering | Human boundaries; lecturer-disjoint video | Text/acoustic/visual/OCR/fusion | WindowDiff, Pk, boundary F1, duration bias |
| Summary | Native reference + claim support annotation | Flat/map-reduce/oracle/predicted/multimodal | ROUGE-L, BERTScore, factuality, coverage, human rating |
| Retrieval/QA | Evidence span/timestamp + answer GT | Flat/hierarchy/multimodal RRF | Recall@k, MRR/nDCG, answer EM/F1, citation accuracy |

### 6.4 Raw artifact bắt buộc

Mỗi run phải lưu:

- `run_manifest.json`.
- `per_unit_predictions.jsonl` hoặc CSV.
- Reference + prediction + IDs.
- Per-unit metrics và failure/error message.
- Aggregate tables được sinh từ raw file, không nhập tay.
- Logs, duration, actual hardware, peak memory, cost nếu API.
- Config/prompt/model/dataset/code hashes.

### 6.5 Thống kê

- Paired comparison trên cùng independent units.
- Hierarchical bootstrap tối thiểu 10,000 resamples ở video/talk level.
- Omnibus trước, post-hoc paired test sau; Holm correction theo family.
- Báo effect size, CI của delta và practical threshold, không chỉ p-value.
- Tuning chỉ trên validation; final test chạy sau khi freeze.
- Human eval: blind, randomized, rubric cố định, ít nhất 2 annotator và agreement.

### 6.6 End-to-end benchmark

Ít nhất các condition:

- Audio-only.
- Visual-only nếu task cho phép.
- Audio + visual.
- Oracle transcript/chapters/evidence.
- Predicted transcript/chapters/evidence.
- Best stage candidates và Pareto alternatives.

Đo:

- Summary quality/factuality/coverage.
- Evidence retrieval/QA.
- Wall-clock latency, RTF, peak RAM/VRAM, API cost.
- Success/failure/timeout/OOM.
- Buckets theo duration/resolution/codec/noise.
- Error cascade bằng perturb input thật rồi rerun, không nội suy.

## 7. Thứ tự ưu tiên sửa

### P0 — Chặn mọi claim

1. Sửa notebook no-op/newline và task mapping.
2. Tắt official dry-run; không cho mock ghi vào report production.
3. Ngăn overwrite artifact khi metrics rỗng/failed/proxy.
4. Sửa cached duration/GT alignment và loại zero/proxy features khỏi official denominator.
5. Gỡ/hạ cấp các câu `100% PASS`, `best`, `accepted hypothesis`, `93% complete` chưa có bằng chứng.

### P1 — Có benchmark stage hợp lệ

1. Freeze dataset registry và split.
2. Sửa runner để inject candidate/toggle thật.
3. Chuẩn hóa output contract + raw predictions.
4. Hoàn tất ASR, scene, OCR, OD và tracking trước.
5. Tạo native GT cho chaptering/summary/retrieval hoặc ghi `not_eligible`.

### P2 — Ghép pipeline

1. Stage Pareto shortlist.
2. Oracle-vs-predicted degradation matrix.
3. E2E factorial/ablation trong budget.
4. Error-cascade rerun.
5. Chỉ sau đó chốt `research_best` và `deployable_best`.

## 8. Tiêu chí hoàn thành

Chỉ được nói “đủ khoa học cho đồ án/demo có benchmark” khi:

- [ ] Mọi notebook official chạy từ clean environment và có output.
- [ ] Không có mock/hard-coded/proxy trong official result path.
- [ ] Dataset/GT/license/checksum/split được freeze.
- [ ] Mọi candidate chạy cùng input, budget, hardware và preprocessing.
- [ ] Có raw prediction, per-unit metric, failure denominator.
- [ ] Có paired CI/test/effect size đúng independent unit.
- [ ] OD có box GT; tracking có trajectory GT và metric riêng.
- [ ] Summary có real outputs + native references + factuality/human protocol.
- [ ] RAG có evidence GT và ranked retrieval output.
- [ ] E2E chạy thật trên nhiều duration strata.
- [ ] Stage winner được kiểm lại sau integration.
- [ ] Report phân biệt `real`, `proxy`, `fallback`, `not_run`, `failed`.

## 9. Nguồn tham khảo

- NeurIPS Paper Checklist: https://neurips.cc/public/guides/PaperChecklist
- Dror et al., *The Hitchhiker's Guide to Testing Statistical Significance in NLP*: https://aclanthology.org/P18-1128/
- Magnusson et al., *Reproducibility in NLP: What Have We Learned from the Checklist?*: https://aclanthology.org/2023.findings-acl.809/
- Luiten et al., *HOTA: A Higher Order Metric for Evaluating Multi-Object Tracking*: https://arxiv.org/abs/2009.07736

## 10. Câu hỏi chưa giải quyết

- Ngôn ngữ đích chính của ASR là tiếng Anh, tiếng Việt hay song ngữ?
- Scene, OCR, object boxes, tracking trajectories, chapter boundaries và summary references sẽ dùng dataset chính thức hay nhóm tự annotation?
- 20 video/883 QA có source-rights, split chính thức và evidence timestamp nào?
- Có log chạy trực tiếp E1–E4 trên cùng hardware hay các số ngày 2026-09-05 là placeholder/legacy?
- Tiêu chí chọn cuối là quality-first hay Pareto quality–latency–cost theo hardware deploy?
