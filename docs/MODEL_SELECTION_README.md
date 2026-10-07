# Lựa chọn mô hình và trạng thái bằng chứng

Tài liệu này phân biệt kết quả đã chạy với ứng viên chưa có phép so sánh hợp lệ. Quy trình hiện hành nằm trong [BENCHMARK.md](BENCHMARK.md#quy-trình-nghiên-cứu-hiện-hành): chọn dataset bài giảng có nhãn phù hợp từng tác vụ, chạy EDA trên cohort định dùng, rồi đánh giá các họ ứng viên trên cùng đơn vị và metric. Mã bảng đánh giá tổng quát cũ (`run_eval_tables.py` cùng các module `datasets.py`, `runners.py`, `aggregate.py`, `report.py`, `model_compare.py`, `schemas.py`) đã được gỡ ngày 2026-10-07. Không dùng tên hàm hoặc lệnh từ luồng đó như chỉ dẫn chạy mới.

## Kết quả đã có: ASR `01c`

[Notebook ASR trên Colab](../experiments/notebooks/asr_architecture_colab_t4.ipynb) đã hoàn tất sáu ứng viên trên 507 đơn vị validation và 1.155 đơn vị native test của TED-LIUM. Qwen3-ASR 0.6B đứng đầu validation với WER 3,91%. Native-test WER 3,53% và CER 1,85% là **diagnostic** vì lịch sử tiếp xúc test; `scientific_selection_eligible=false`. Các ứng viên khác checkpoint, dữ liệu huấn luyện, kích thước và toolchain, nên chênh lệch WER không cô lập tác động riêng của kiến trúc. Xem [báo cáo ASR và giới hạn bằng chứng](results/asr-architecture-evaluation-2026-10-05.md).

Ứng dụng vẫn dùng Faster-Whisper `base.en` mặc định. Lựa chọn nghiên cứu `01c` chưa được triển khai vào ứng dụng. Các run ASR `01a`/`01b` là hồ sơ diagnostic lịch sử và không được gộp vào bảng sáu kiến trúc.

## Các tác vụ còn lại

Scene, keyframe, OCR, caption, detection, tracking, summarization và retrieval/QA có [ma trận dataset–ứng viên–metric](BENCHMARK.md#quy-trình-nghiên-cứu-hiện-hành). Đây là **danh sách dự kiến cần xác minh**, không phải kết quả chọn model. Các số liệu từng dẫn từ `outputs/model_choice/`, `outputs/eval_tables_real/` và luồng bảng cũ không có đủ tệp nguồn trong checkout hiện tại; không dùng chúng để xếp hạng hoặc biện minh model.

- RQ2: [EDA TIB toàn train/valid/test](../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) đã chuẩn bị nhưng chưa chạy trên toàn bộ dữ liệu; cohort và reference đánh giá chưa chốt. Output đánh giá Qwen cũ đã được xóa; chưa có kết quả để chọn phương pháp tóm tắt. VISTA cũng chưa hoàn tất qualification. Xem [DATASET_EDA.md](DATASET_EDA.md).
- RQ1: kết quả chẩn đoán chia chương MIT001 đã được rút để phân tích lại; chưa có phép chọn mô hình hợp lệ.
- Những tác vụ chưa có nhãn bài giảng phù hợp hoặc chưa chạy cùng cohort phải ghi `not_eligible`/`no_selection`, không suy diễn từ model production hay bảng proxy cũ.

Khi cần một so sánh mới, tạo notebook riêng cho dataset và tác vụ đã chốt; lưu dự đoán, lỗi từng đơn vị, metric, receipt và giới hạn. Không tái tạo pipeline bảng tổng quát cũ chỉ để sinh bảng luận văn.
