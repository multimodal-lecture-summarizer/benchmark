---
phase: 3
title: "Expand candidate families for every task"
status: pending
priority: P1
dependencies: [2]
effort: "3-5 days registry and feasibility spike"
---

# Phase 3: Expand candidate families for every task

## Overview

Sửa hiện tượng registry trông đa dạng nhưng runner chỉ chạy một họ mô hình. Mỗi task phải có baseline đơn giản, ít nhất hai họ learned khác nhau khi khả thi, và candidate phải có adapter runnable hoặc bị ghi `not_eligible`.

## Candidate Matrix

| Task | Minimum candidate families | Notes |
|---|---|---|
| ASR | Faster-Whisper/Whisper; Wav2Vec2/XLS-R CTC; NeMo Parakeet/Canary hoặc transducer tương đương; Sherpa-ONNX Zipformer/Vosk lightweight | Chọn checkpoint theo ngôn ngữ; AssemblyAI/API là deployment track riêng. DeepFilterNet=denoise, WhisperX=alignment, không phải decoder độc lập. |
| Scene | Fixed/uniform; PySceneDetect Content/Adaptive; TransNetV2; CLIP/DINOv2 embedding change-point | Chấm cùng human GT; threshold tune trên validation. |
| Keyframe | Scene midpoint; temporal dedup; CLIP/DINOv2 k-medoids/diversity; OCR-aware salience | Giữ cùng frame budget. |
| OCR | Tesseract; EasyOCR; PaddleOCR; TrOCR/transformer recognition | Tách end-to-end OCR và recognition-only nếu detector input khác. |
| Caption/VLM | BLIP/BLIP-2; Florence-2; Qwen2.5/3-VL hoặc LLaVA/InternVL feasible | Cùng frame/prompt/token budget; quantized row tách deployment profile. |
| Detection | YOLOv8/11; RT-DETR; GroundingDINO; Florence-2 grounding | Closed-vocab và open-vocab leaderboard tách hoặc mapping taxonomy pre-registered. |
| Tracking | ByteTrack; BoT-SORT; OC-SORT hoặc DeepSORT | Tracker-only dùng fixed detections; detector+tracker pairs là bước sau. |
| Chaptering | Fixed-window; TextTiling/C99 lexical; learned text/acoustic; visual change-point; multimodal fusion | C1–C6 giữ làm modality ablation. |
| Summary | TextRank/LexRank; BART/PEGASUS/LongT5/LED; flat LLM; hierarchical LLM; multimodal/VLM | Chọn 1 checkpoint feasible mỗi family; S0–S4 là context/evidence ablation. |
| Retrieval | BM25; dense bi-encoder; hybrid RRF; cross-encoder/ColBERT reranked | Reader/generator đánh giá tách khỏi retrieval. |
| QA | Extractive reader; text LLM generator; evidence-grounded multimodal generator | Q0–Q3 là architecture ablation, không phải model-family bake-off. |

## Requirements

- Candidate có `family`, `task`, `model_revision`, `license`, `language`, `input_contract`, `resource_profile`, `adapter`, `eligibility_reason`.
- Tối thiểu một non-neural/classical baseline cho task có baseline hợp lý.
- Candidate chỉ xuất hiện trong official registry khi adapter smoke test chạy được.
- Model policy: open-source by default. Groq/OpenRouter is allowed only for LLM stages with explicit scientific/deployment justification and an API-specific resource profile; API and local efficiency rows never share one leaderboard.
- Hardware routing: heavy feasible candidates target `colab_t4`; light candidates additionally target `local_rtx4050_6gb`. Eligibility is profile-specific.

## Related Code Files

- Modify: `multimodal-lecture-summarizer/experiments/registry/candidates.yaml`
- Modify: `multimodal-lecture-summarizer/experiments/scripts/registry_loader.py`
- Modify/create adapters under `multimodal-lecture-summarizer/experiments/evaluation/` and `multimodal-lecture-summarizer/ai_workers/modules/`
- Modify: task benchmark scripts under `multimodal-lecture-summarizer/benchmarks/scripts/`

## Implementation Steps

1. Thêm candidate taxonomy: `model`, `algorithm`, `preprocessing`, `ablation`, `system_composition`.
2. Chuyển DeepFilterNet/VAD/WhisperX khỏi ASR model table sang preprocessing/alignment factors.
3. Chuyển C1–C6, S0–S4, Q0–Q3 sang ablation/architecture track; E1–E4 sang system composition.
4. Chốt 3–5 candidate/task theo English suitability, license, T4/RTX4050-6GB feasibility, VRAM/RAM và download size; không đăng ký model không thể chạy.
5. Implement uniform adapter interface: load, predict, serialize raw output, resource telemetry, failure reason.
6. Pin revision/weights/dependencies; ghi API provider/model date cho cloud candidate.
7. Smoke test mỗi adapter trên 1–2 eligible units; status phải phân biệt `runnable`, `blocked_resource`, `blocked_license`, `not_eligible`.
8. Tạo candidate coverage test: registry family diversity và runner dispatch phải khớp.
9. Với Groq/OpenRouter LLM candidate, record provider/model revision or dated model ID, justification versus open-source local alternative, privacy/data-transfer scope, token/cost/rate cap and deterministic fallback; missing field makes candidate `blocked_decision`.

## Success Criteria

- [ ] ASR không còn chỉ là các biến thể Whisper; có ít nhất 3 decoder families runnable hoặc lý do không đủ điều kiện được ghi rõ.
- [ ] Scene/keyframe, OCR/caption, chaptering, summary và retrieval có model/algorithm bake-off độc lập với ablation.
- [ ] GroundingDINO và mọi candidate registry khác thực sự dispatch vào adapter hoặc bị loại khỏi eligible set.
- [ ] Tracking có candidate riêng và metric contract riêng, không còn được coi là “done” nhờ detection.
- [ ] Mỗi registry row có revision/license/resource/input contract và smoke-test status.
- [ ] Every eligible row names `colab_t4`, `local_rtx4050_6gb` or an API profile; cross-profile latency/cost results are never ranked as if measured on the same hardware.
- [ ] Không có fallback heuristic được báo cáo như model candidate.

## Risk Assessment

- Quá nhiều model gây nổ compute: cap 3–5 family representatives/task và dùng validation elimination trước final test.
- Candidate khác label space/language: tách track hoặc pre-register mapping; không ép chung leaderboard thiếu công bằng.
