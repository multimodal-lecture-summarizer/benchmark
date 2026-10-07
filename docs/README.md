# Tài liệu benchmark

Điểm vào cho tài liệu còn dùng và hồ sơ nghiên cứu. Quy trình hiện hành: [chọn dataset bài giảng có nhãn đúng tác vụ và họ ứng viên → EDA đúng cohort → đánh giá cùng thang đo](BENCHMARK.md#quy-trình-nghiên-cứu-hiện-hành). Không dùng video tổng quát làm benchmark dự phòng. Chỉ tạo notebook khi sắp chạy bước EDA hoặc đánh giá tương ứng; không duy trì notebook khung hay luồng notebook smoke. Manifest ở chế độ `on_demand` hiện không có notebook hoạt động. `01a`/`01b` đã rời danh sách chạy, còn `01c` là kết quả ASR diagnostic lịch sử. Báo cáo có số liệu được giữ nguyên; tài liệu định hướng cũ nằm trong `archive/`.

## Tài liệu chính

| Tài liệu | Nội dung |
|---|---|
| [BENCHMARK.md](BENCHMARK.md) | Giao thức, điều kiện đánh giá và giới hạn kết luận. |
| [DATASET_EDA.md](DATASET_EDA.md) | Phạm vi, nguồn và bằng chứng EDA. |
| [HYBRID_MODEL_GUIDE.md](HYBRID_MODEL_GUIDE.md) | Hướng dẫn mô hình kết hợp. |
| [MODEL_SELECTION_README.md](MODEL_SELECTION_README.md) | Cách đọc kết quả lựa chọn mô hình. |
| [OUTLINE_MAPPING.md](OUTLINE_MAPPING.md) | Đối chiếu đề cương với mã và bằng chứng. |
| [SPRINT_QUALITY_DEPLOYMENT.md](SPRINT_QUALITY_DEPLOYMENT.md) | Báo cáo triển khai bộ lọc chất lượng. |
| [florence-2-cpu-reproducibility.md](florence-2-cpu-reproducibility.md) | Chẩn đoán tái lập Florence-2. |

## Kết quả và hiện vật

- [Đánh giá ASR `01c`](results/asr-architecture-evaluation-2026-10-05.md): sáu kiến trúc đã chạy đủ 507 validation và 1.155 native-test unit; Qwen3-ASR 0.6B đứng đầu validation WER 3,91%. Native test chỉ là diagnostic. Xem thêm [ghi nhận lỗi transcript rỗng](results/asr-architecture-empty-transcript-recovery-2026-10-05.md) và [chẩn đoán MIT001](results/MIT001_CHAPTERING_DIAGNOSTIC.md).
- [Sơ đồ cây thư mục hiện tại](visuals/benchmark-directory-tree.drawio) được tạo từ `scripts/generate_benchmark_directory_tree_drawio.py`.
- [Bản Word EDA](exports/DATASET_EDA.docx) là bản xuất lịch sử; dùng [DATASET_EDA.md](DATASET_EDA.md) cho quy trình và trạng thái hiện hành.

## Lưu trữ lịch sử

- [Hồ sơ chiến lược lịch sử](archive/strategy/research-strategy-archive.md): nguyên văn bốn bản định hướng, lộ trình và so sánh stack, kèm hash từng nguồn.
- `archive/visuals/`: hai báo cáo HTML cũ.
- [Ghi nhận chuyển repo](archive/research-migration-2026-10-06.md), [nhật ký benchmark đầu kỳ](journals/260922-260925-early-benchmark-journal.md), [nhật ký sửa bằng chứng](workspace/260926-research-evidence-journal.md) và `workspace/`: nhật ký, tài liệu luận văn và bản thảo trình bày. Ba nhật ký có tên và SHA-256 trong manifest vẫn là tệp riêng trong `journals/`.

`benchmarks/references/` không có ground truth cục bộ đã xác minh. Không dùng các ví dụ trong tài liệu như nhãn đánh giá.
