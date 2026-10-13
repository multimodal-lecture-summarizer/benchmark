# IIIT-CVID OCR: EDA bổ sung và notebook so sánh

## Sản phẩm

Phạm vi repository: notebook có output, source/runtime và tests được lưu cùng tài liệu. Dữ liệu tải xuống, output bổ sung bị ignore và artifact Drive giữ ngoài Git; audit artifact Drive và replay tuần tự vẫn còn pending.

- EDA đã có output: `benchmark/experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb` — 17 code cells có execution count, 16 PNG, không có saved error. Giữ output lịch sử; thêm 5 code cells thực thi bằng in-process IPython. Fresh-kernel replay chưa xác minh do kernel startup bị treo.
- Notebook Colab độc lập: [iiit_cvid_ocr_comparison_colab.ipynb](../../experiments/notebooks/iiit_cvid_ocr_comparison_colab.ipynb). Có source nhúng, tải nguồn ở revision cố định, kiểm SHA-256/CRC, EDA crop, môi trường Python 3.11 riêng, tải và kiểm trọng số, inference preflight, chạy tuần tự hai engine, checkpoint, receipts, failure ledger, micro CER, exact-word accuracy, bootstrap theo video, feature strata và error galleries.
- Các phân tích/PNG bổ sung: `benchmark/experiments/outputs/ocr_eda_261013/` (ignored, không commit).

## Tiến độ Colab hiện tại — 2026-10-13

Notebook so sánh đã có output Colab mới lưu trong file: mount Drive, kiểm 15.379 crop / 15.384 source files, preflight import và load model; subprocess EasyOCR và PaddleOCR đều có `returncode=0`. Thư mục kết quả được ghi là `/content/drive/MyDrive/OCR/ocr-validation-261013-v1`.

| Kết quả Colab đã lưu | EasyOCR | PaddleOCR |
|---|---:|---:|
| Crop được chấm | 15.379 | 15.379 |
| Ký tự reference | 73.654 | 73.654 |
| Edit distance tổng | 17.999 | 8.630 |
| Micro CER | 24,4372% | 11,7169% |
| Exact-word accuracy | 54,9386% | 71,6757% |
| Inference failures | 0 | 0 |
| Empty predictions | 8 | 18 |

Chênh lệch PaddleOCR − EasyOCR là **−12,7203 điểm phần trăm**, bootstrap 95% theo 140 video clusters / 2.000 draws: **[−15,5847; −9,9783] điểm phần trăm**. Đây là so sánh mô tả trên validation word crops đã được xem trước; không phải OCR spotting, unseen-test generalization hay quyết định chọn model production.

Notebook hiện có **18 cells / 12 code cells**, trong đó **11 code cells có execution count**, **10 PNG**, không có saved error. Một cell phân tích trung gian chưa có saved output/execution count; vì vậy chưa xác nhận toàn bộ notebook chạy tuần tự từ fresh kernel. Output inference và bảng/đồ thị cuối đã lưu, nhưng **audit độc lập Drive receipts, prediction từng crop, môi trường và hash source/model vẫn còn pending**. Gallery có output đã lưu.

## Nhận xét từ dữ liệu CPU lịch sử đã kiểm tra

Toàn bộ 15.379 crop validation, 5 course, 140 video folders được ghép đúng với nhãn và prediction cũ. SHA-256 ZIP và hai prediction JSONL khớp; 15.384 file crop/label được đối chiếu ZIP. Không sửa nhãn.

| Kết quả CPU lịch sử | EasyOCR 1.7.2 | PaddleOCR 2.8.1 |
|---|---:|---:|
| Micro CER | 24,44% | 11,72% |
| Exact-word accuracy | 54,94% | 71,68% |
| Inference failures | 0 | 0 |
| Empty predictions | 8 | 18 |

Paddle có ít edit hơn ở 4.982 crop; Easy ở 462; bằng nhau ở 9.935. Paddle thấp hơn ở cả 5 course. Chênh lệch micro CER là −12,72 điểm phần trăm, khoảng bootstrap 95% theo video khoảng [−15,58; −9,98] điểm phần trăm. Đây là phân tích CPU lịch sử, tách biệt với output Colab mới ở trên. EasyOCR lịch sử có 18.000 edits, còn output Colab ghi 17.999; không coi prediction hai run là giống hệt nhau.

Course 19 chiếm 7.757/15.379 crop (50,44%), và có CER thấp ở cả hai engine. Vì vậy phải đọc cả bảng course/video thay vì chỉ điểm gộp. Nhãn một ký tự có CER cao hơn nhóm dài hơn; nhóm chứa chữ số và dấu câu cũng khó hơn trong mẫu này. Ví dụ nhóm có dấu câu: Easy 38,98%, Paddle 21,12% CER. Các nhóm bị confound bởi course, độ dài và hình ảnh; không suy ra nguyên nhân.

537 crop được dHash gắn cờ khác nhãn chỉ là ứng viên xem xét, không chứng minh nhãn sai. Phân tích độ nhạy bỏ nhóm này cho CER 24,75% và 11,74%; kết luận mô tả vẫn cùng hướng. Điểm chính giữ đủ 15.379 crop. Screening dHash lịch sử không đầy đủ và không phải quyết định loại dữ liệu.

## Cách chạy

1. Upload notebook so sánh lên Colab, chọn CPU, chạy theo thứ tự. Tải ZIP khoảng 2,43 GB; cần thêm dung lượng cho cache, môi trường và dữ liệu giải nén.
2. Mount Drive. `RUN_ID` mặc định tạo thư mục `MyDrive/OCR/ocr-validation-261013-v1`; kết quả được lưu trực tiếp tại đây.
3. Ngắt rồi resume: dừng phiên cũ, chạy lại các cell với cùng RUN_ID. Nếu môi trường/source/model không khớp, tạo RUN_ID mới. Nếu còn `<engine>.lock` do kill, chỉ xóa file lock sau khi chắc chắn phiên cũ đã dừng. Không chạy hai phiên cùng engine/output.
4. Giữ notebook có output và thư mục kết quả để phân tích sau chạy. Run OCR này dùng CPU.

## Giới hạn xác minh

10 focused tests của runner/runtime đã qua; schema, syntax và source nhúng của notebook hợp lệ. Ba cell EDA/paired-analysis/gallery của notebook mới cũng đã thực thi trên dữ liệu và prediction lịch sử thật, ghi sang thư mục kiểm tra riêng. Sau đó notebook đã lưu preflight import/model và output inference Colab cho cả hai engine như mục tiến độ hiện tại. Kiểm tra local lịch sử không thay thế audit độc lập các artifact Drive hoặc sequential fresh-kernel replay.

Đây chỉ là recognition trên released validation word crops đã được xem trước. Không chứng minh frame detection, end-to-end lecture OCR, unseen-test generalization hoặc tốc độ tương đối (hai run lịch sử chạy chồng thời gian). Notebook mới đặt CPU/thread cụ thể nhưng batch engine khác nhau và không tự tuyên bố engine nhanh hơn.

Dependencies tham chiếu [PaddleOCR v2.8.1 requirements](https://github.com/PaddlePaddle/PaddleOCR/blob/v2.8.1/requirements.txt), [EasyOCR 1.7.2](https://pypi.org/project/easyocr/1.7.2/), [PaddlePaddle 2.6.2](https://pypi.org/project/paddlepaddle/2.6.2/). Trọng số thực tế có hash riêng trong runtime receipt.

Không còn câu hỏi cần người dùng quyết định. Gate tiếp theo là audit độc lập artifact Drive và xác minh replay tuần tự; không cần suy diễn rằng mọi cell đã chạy chỉ từ output cuối.

## Bổ sung hiển thị bảng và đồ thị

Notebook so sánh hiện có 18 cells; phần phân tích cuối gồm:

- Bảng/đồ thị tổng thể CER, exact-word accuracy, failures và empty predictions.
- Bảng theo course, bảng đủ 140 video, thống kê mô tả video; histogram CER, paired scatter và histogram chênh lệch theo video.
- Bảng/đồ thị 7 nhóm: độ dài nhãn, chiều rộng, chiều cao, tương phản, chữ số, dấu câu, cờ review. Có số crop và mẫu số ký tự, giữ thứ tự số của các khoảng.
- Bảng/đồ thị số crop có ít edit hơn và exact-word agreement của hai engine.
- Bảng/đồ thị độ nhạy: toàn bộ cohort, flagged-only và unflagged-only; không tự loại hay sửa nhãn.
- Bảng khoảng tin cậy, histogram 2.000 bootstrap draws và hình point/interval cho chênh lệch CER theo video cluster.

Helper `ocr_comparison_visualization.py` được nhúng trực tiếp vào notebook; chạy cell phân tích sẽ hiện inline và ghi CSV/PNG vào Drive. Kiểm tra trên prediction lịch sử thật đã xuất **6 PNG và 15 CSV bổ sung** tại `benchmark/experiments/outputs/ocr_visualization_verification_261013/` (ignored). Bootstrap khớp báo cáo gốc và mọi nhóm phủ đủ 15.379 crop. Đây là xác minh phân tích lịch sử, không phải lần inference mới. Notebook hiện đã lưu output inference Colab riêng như mục tiến độ; còn pending audit artifact Drive và replay tuần tự từ fresh kernel.

## Sửa lỗi ABI ở kernel Colab Python 3.13

Traceback người dùng cho thấy `numpy.random.mtrand` báo `numpy.dtype size changed`. Cell cài đặt cũ có pin NumPy <2 ngay trong kernel chính, không phù hợp Python 3.13 và dễ trộn module đã nạp với thư viện mới trên đĩa. Không có package/version inventory trực tiếp từ Colab để khẳng định mọi chi tiết trạng thái cài đặt; đây là lỗi cấu hình native dependency đã xác định và loại bỏ.

Bản sửa giữ nguyên scientific stack của kernel; kiểm import NumPy random, Pandas, render PNG Matplotlib/Pillow trong subprocess mới rồi đối chiếu kernel hiện tại trước tải dữ liệu. NumPy 1.26.4 chỉ cài trong inference Python 3.11 riêng. Không còn API `include_groups` phụ thuộc phiên bản Pandas trong gallery. Có cell phục hồi ABI opt-in cuối notebook: cài lại bộ wheel hỗ trợ CPython 3.13 rồi yêu cầu **Restart session**, giữ ZIP và dữ liệu /content. Không chọn Delete runtime. Các module source nhúng và inference identity không đổi, không cần đổi RUN_ID chỉ vì bản sửa này.

Preflight mới đã chạy thành công trên scientific stack NumPy 2/Pandas 3 tại máy local; notebook schema, 12 code cells và 4 source nhúng hợp lệ. Focused regression tests kiểm không còn native binary pins và thực thi preflight thật. Output Colab hiện tại đã lưu preflight thành công và inference hai engine; nhánh recovery opt-in chưa được xác minh độc lập. Replay tuần tự từ fresh kernel vẫn pending. Tham chiếu: [NumPy ABI troubleshooting](https://numpy.org/doc/stable/user/troubleshooting-importerror.html); bộ recovery có CPython 3.13 wheels trên PyPI.
