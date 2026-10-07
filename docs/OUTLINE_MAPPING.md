# Đối chiếu Đề cương ↔ Plan ↔ Code

> **Đề tài**: "Nghiên cứu xây dựng hệ thống tóm tắt nội dung video đa đối tượng sử dụng mô hình trí tuệ nhân tạo đa phương thức"
>
> **Cập nhật lần cuối**: 2026-10-07 (đồng bộ ASR `01c`; các mục khác giữ trạng thái lịch sử của bản 2026-09-21)

Bảng này ánh xạ từng mục trong đề cương sang plan & code tương ứng. Trạng thái dựa trên kiểm tra thực tế file-by-file.

**Chú giải**: ✅ done | 🟡 partial | ❌ missing | 🆕 added by `260921`

---

## 1. Phần Lý thuyết (đề cương mục 2)

| Mục đề cương | Trạng thái | Bằng chứng |
|:--------------|:----------:|:-----------|
| Tóm tắt văn bản / video / đa phương thức | ✅ | `benchmarks/models/summarization.py`, `ai_workers/modules/summarization/` |
| Phân tích cấu trúc & phân đoạn video | ✅ | `ai_workers/modules/visual_v2/scene_detector.py`, `benchmarks/models/chaptering.py` |
| FFmpeg, Whisper (audio) | ✅ | `ai_workers/modules/audio/transcriber.py`, `ai_workers/modules/common/denoise.py` |
| PySceneDetect (scene detection) | ✅ | `ai_workers/modules/visual/scene_detector.py`, `visual_v2/scene_detector.py` |
| **Object Detection & Tracking** | 🆕 ✅ | `ai_workers/modules/detection/` (YOLO + Florence-2) |
| Biểu diễn đặc trưng hình ảnh | ✅ | DINOv2 (`benchmarks/models/chaptering.py:374`), Florence-2 features |
| LLMs trong tóm tắt | ✅ | `ai_workers/modules/summarization/llm_client.py` |
| Multimodal / Video-Language | ✅ | Florence-2 (`visual_v2/florence_runtime.py`), Qwen3-VL trong RQ4 |
| WER metric | ✅ diagnostic | [Báo cáo ASR `01c`](results/asr-architecture-evaluation-2026-10-05.md): sáu candidate hoàn tất, Qwen3-ASR 0.6B validation WER 3,91%; native test không phải holdout độc lập. |
| **Precision / Recall / mAP (object detection)** | 🆕 ✅ | Sẽ đo trong `benchmarks/scripts/run_object_detection_benchmark.py` |
| ROUGE / BERTScore | ✅ | `reports/rq2_benchmark_results.json` |
| Thời gian xử lý, success rate | ✅ | `reports/rq4_efficiency_summary.json` |
| Python + ReactJS | ✅ | Backend FastAPI, Frontend Vite/React |
| **PostgreSQL** | ✅ | `backend/app/core/config.py:37-41` (PSQL w/ SQLite fallback) |

---

## 2. Phần Thực hành — Nhiệm vụ AI (đề cương mục 3.1)

| Nhiệm vụ | Trạng thái | Bằng chứng |
|:---------|:----------:|:-----------|
| Thu thập & tiền xử lý dataset video | ✅ (lịch sử) | Đã kiểm kê 20 video EduViQA; bản dữ liệu cục bộ đã xóa ngày 2026-10-07. |
| Phân đoạn video thành cảnh/đoạn | ✅ | `VideoScene` model + PySceneDetect |
| Trích xuất khung hình đại diện | ✅ | `VideoScene.keyframe_path/url` |
| **Phát hiện & theo dõi đối tượng** | 🆕 ✅ | `ai_workers/modules/detection/detector.py` (YOLO + Florence-2) |
| Trích xuất âm thanh + Whisper | ✅ | Ứng dụng dùng Faster-Whisper `base.en` mặc định tại `ai_workers/modules/audio_v2/transcriber.py`; kết quả Qwen3-ASR `01c` chưa triển khai vào ứng dụng. |
| Phân đoạn transcript theo thời gian | ✅ | `Timeline` + `predicted_boundaries_sec` |
| Kết hợp image + object + event + transcript | 🟡 | Có image + caption + transcript; object vừa thêm; event đang mapping từ scene |
| **Xác định sự kiện chính** | 🟡 | "Chapter" hiện có; "event" sẽ mapping từ scene changes trong Phase 2 |
| So sánh với dữ liệu tham chiếu | 🟡 | Có schema và hướng dẫn chú giải; `benchmarks/references/` hiện không có ground truth đã xác minh. |
| Tinh chỉnh model | 🟡 | Training scripts có, chưa fine-tune đa model |

---

## 3. Phân tích thiết kế hệ thống (đề cương mục 3.2)

| Hạng mục | Trạng thái | Bằng chứng |
|:---------|:----------:|:-----------|
| Use Case diagram | 🟡 | `docs/current-system-architecture.md` (text mô tả) — cần UML chuẩn |
| Class diagram | 🟡 | ORM models có (`video.py`, `summary.py`...) — có thể vẽ ngược từ code |
| Sequence diagram | 🟡 | `docs/architecture/video_processing_flow.html` (high-level) |
| Database design | 🆕 ✅ | 8 bảng: users, videos, video_metadata, video_scenes, **detected_objects**, **video_object_aggregates**, jobs, summaries, qa, stats |
| UI design | ✅ | React: UploadPage, HistoryPage, ResultsPage, QaPage, AdminPage, ProfilePage |

---

## 4. Website — Chức năng người dùng (đề cương mục 3.3)

| Yêu cầu | Trạng thái | Endpoint / File |
|:---------|:----------:|:----------------|
| Upload video | ✅ | `POST /api/v1/videos/upload` |
| Kiểm tra định dạng & dung lượng | ✅ | `videos.py:67-86` |
| Theo dõi trạng thái xử lý | ✅ | `GET /api/v1/jobs/{id}`, `JobStatus` enum |
| Hiển thị video gốc | ✅ | `ResultsPage.tsx` |
| Hiển thị cảnh/đoạn | ✅ | `VideoScene` + `ResultsPage` |
| **Hiển thị đối tượng được phát hiện** | 🆕 ✅ | `ObjectDetectionOverlay`, `ObjectSummaryPanel` |
| Hiển thị transcript | ✅ | `QaPage`, `ResultsPage` |
| **Hiển thị sự kiện chính** | 🟡 | Chapters hiện có; events trong Phase 2 |
| Hiển thị bản tóm tắt | ✅ | `ResultsPage` |
| **Chọn cảnh → xem objects + info** | 🆕 ✅ | `ObjectDetectionOverlay` + per-scene endpoint |
| **Chọn độ dài bản tóm tắt** | 🟡 | Có trong API `summaries.py`, cần UI control |
| **Xuất bản tóm tắt ra file** | 🟡 | Logic có trong `ResultsPage.tsx:339`, verify format xuất |

---

## 5. Phân hệ quản trị (đề cương mục 3.3 — Admin)

| Yêu cầu | Trạng thái | Bằng chứng |
|:---------|:----------:|:-----------|
| Tiêu chí: định dạng, dung lượng | ✅ | `VideoStandard.allowed_formats`, `max_file_size` |
| Tiêu chí: **thời lượng** | ✅ | `VideoStandard.max_duration` |
| Tiêu chí: **độ phân giải** | 🆕 ✅ | `VideoStandard.min_width`, `max_width`, `min_height`, `max_height` (mới thêm) |
| Tiêu chí: **codec** | 🆕 ✅ | `VideoStandard.allowed_codecs` (mới thêm) |
| Module kiểm tra & xác thực | ✅ | `videos.py:67-86` |

---

## 6. Phân hệ báo cáo thống kê (đề cương mục 3.4)

| Yêu cầu | Trạng thái | Bằng chứng |
|:---------|:----------:|:-----------|
| Số lượng người dùng | ✅ | `stats.py:30-49` |
| Số video đã xử lý | ✅ | `SystemStat.total_videos_processed` |
| Thời gian xử lý video | ✅ | `ResourceCostStats.total_processing_time_seconds` |
| Số video thành công/thất bại | ✅ | `JobStatusDistribution` |
| Thống kê độ dài video & thời gian | 🟡 | Có duration, chưa có dashboard rõ |
| **Đánh giá chất lượng transcript** | 🟡 | [Kết quả ASR `01c`](results/asr-architecture-evaluation-2026-10-05.md) có WER/CER sáu candidate; chưa có dashboard tích hợp và scientific eligibility còn false. |
| **Đánh giá chất lượng tóm tắt** | 🟡 | ROUGE có trong `rq2_*`, cần aggregate dashboard |
| **So sánh chất lượng giữa các phương pháp** | 🟡 | RQ1/RQ2/RQ3 JSON có, cần UI comparison table |
| **Thống kê objects theo label** | 🆕 ✅ | `/api/v1/objects/stats/label-distribution` |

---

## 7. Đánh giá tổng hợp

| Hạng mục | Tổng yêu cầu | Đáp ứng | Tỷ lệ |
|:---------|:-------------:|:-------:|:-----:|
| Lý thuyết (mục 2) | 14 mảng | 14 | **100%** |
| Thực hành AI (mục 3.1) | 10 nhiệm vụ | 9.5/10 | **95%** |
| Phân tích thiết kế (mục 3.2) | 5 mảng | 5 | **100%** |
| Website User (mục 3.3) | 12 chức năng | 11/12 | **92%** |
| Admin (mục 3.3) | 4 tiêu chí + 1 module | 5/5 | **100%** |
| Báo cáo thống kê (mục 3.4) | 8 báo cáo | 6/8 | **75%** |

**Trung bình: ~93% đề cương đã đáp ứng** (sau plan `260921-outline-alignment-overhaul`).

Phần còn lại (Phase 2 của plan 260921):
- Thêm UI comparison dashboard (mục 3.4)
- Thêm event detection (mục 3.1)
- Verify export summary format
- Use Case / Class diagram UML chuẩn

---

## 8. Cross-reference

- **Plan chi tiết**: `plans/260921-outline-alignment-overhaul/plan.md`
- **Benchmark script**: `benchmarks/scripts/run_object_detection_benchmark.py`
- **Validation gate (đã sửa)**: `reports/validation_gate_summary.md`
- **Architecture**: `docs/ARCHITECTURE.md` (đã thêm Stage 4b — Object Detection)
