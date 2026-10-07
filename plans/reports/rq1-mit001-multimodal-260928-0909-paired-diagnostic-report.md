# RQ1 MIT001: paired chaptering diagnostic

Artifact: `C:\Users\hung\Documents\GitHub\multimodal-lecture-summarizer\multimodal-lecture-summarizer\experiments\outputs\diagnostic\rq1_mit001_local_runs\20260928T022609Z`
Dataset: `avlectures_mit001_local_diagnostic`; 35 matched lectures from one course.
Metric: macro mean of per-lecture `collar_f1_3s` (3-second boundary collar).
Paired deltas and win/tie/loss compare each lecture with the 04b `transcript` variant.

| Variant | Macro F1@3s | Mean paired delta | Wins / ties / losses |
| --- | ---: | ---: | ---: |
| `fixed_window_300s` | 0.0198 | -0.0096 | 5 / 2 / 28 |
| `lexical_texttiling` | 0.0294 | +0.0000 | 0 / 35 / 0 |
| `multimodal_scene_aligned` | 0.0486 | +0.0192 | 23 / 0 / 12 |
| `transcript` | 0.0294 | +0.0000 | 0 / 35 / 0 |
| `transcript+ocr` | 0.0502 | +0.0208 | 13 / 2 / 20 |
| `transcript+scene` | 0.0486 | +0.0192 | 23 / 0 / 12 |
| `transcript+visual` | 0.0416 | +0.0122 | 20 / 1 / 14 |
| `transcript+acoustic` | 0.0637 | +0.0343 | 29 / 0 / 6 |
| `all_modalities` | 0.0488 | +0.0194 | 26 / 0 / 9 |

## Scope and limitations

- Local diagnostic only; these are descriptive scores, not an official or held-out result.
- Diagnostic only: single course; no course-disjoint train/test; all lecture labels appeared in an earlier pilot
- All 35 videos are from MIT18.01JF07; this run cannot measure transfer to another course.
- OCR and scene features are sampled/extracted from local media; this report makes no claim about unsampled visual content.
- Visual means sparse source-frame change and acoustic means source-audio energy change; neither is a learned visual-caption or prosody model.
- The full-modality row is a fixed heuristic fusion, not a C5/C6 learned checkpoint.
- No statistical significance or population-level conclusion is inferred from these paired descriptions.
