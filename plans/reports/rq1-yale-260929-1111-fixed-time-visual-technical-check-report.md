# RQ1 Yale: kiểm hình kỹ thuật trên sáu MOV, không tạo nhãn

Ngày kiểm: 2026-09-29. Mục đích: đo tín hiệu hình theo lịch cố định trên cohort qualification. **Không chép OCR, không tạo GT, không chọn hoặc loại bài theo kết quả bộ phát hiện.** [Receipt tổng hợp](./rq1-yale-260929-1111-fixed-time-text-box-detection-receipt.json) chỉ giữ số liệu mỗi bài; không giữ frame, chữ OCR, tọa độ hộp hay record từng frame.

## Cách đo

- Sáu MOV đã băm trong [receipt media/GT](./rq1-yale-260929-publisher-gt-mov-structural-receipt.json) đều có video stream **640×360, 29,97 fps**. Lấy một frame tại `t=60+120k` giây, `k≥0`, cho đến trước điểm kết thúc stream 30 giây; cùng lịch cho mọi file. Tổng **198 frame**.
- Chạy PaddleOCR 2.8.1, model phát hiện chữ tiếng Anh `en_PP-OCRv3_det` đã có sẵn, CPU, chế độ **detection only**. Chỉ đếm hộp; không chạy bước nhận dạng chữ. Runtime cần shim tạm `numpy.sctypes` do PaddleOCR/imgaug cũ không nhập được với NumPy 2.4.6 hiện tại; không thay package/mã dự án.
- Sau khi thấy số đếm thô gần bão hòa, tính thêm tỷ lệ frame có hộp ngoài vùng góc phải dưới (tâm hộp không đồng thời ở `x≥0,65` và `y≥0,80` theo kích thước chuẩn hóa). **Ngưỡng này đặt sau khi xem số thô**, chỉ là chẩn đoán thăm dò, không phải gate đã định trước.

| Bài | Frame lấy | Có ≥1 hộp, thô | Có ≥1 hộp ngoài vùng góc, thăm dò |
|---|---:|---:|---:|
| ECON 159 L2 | 34 | 33 | 14 |
| ECON 251 L1 | 37 | 37 | 37 |
| ECON 252 (2008) L6 | 34 | 34 | 16 |
| ENGL 220 L23 | 22 | 22 | 0 |
| PHYS 200 L19 | 36 | 36 | 28 |
| PHYS 201 L10 | 35 | 35 | 35 |

Số hộp thô gần như có ở mọi frame vì bộ phát hiện cũng bắt chữ cố định ở góc; phép đếm **không đo chữ có ích**. Bộ lọc hình học có thể bỏ cả chữ thật ở góc và giữ nhiễu ở nơi khác. Không có GT OCR đã công bố để tính precision, recall hoặc CER. Không thể từ bảng này kết luận bài nào đủ chất lượng visual cho official RQ1. Không sửa mốc/tiêu đề Yale, không chuyển bất kỳ MOV nào sang `rights_pass` hoặc D2.

## Câu hỏi chưa giải quyết

1. Có nguồn GT OCR hoặc tiêu chí chất lượng visual khách quan đã đăng ký trước đủ để làm gate D2 không? Nếu không, chỉ báo các phép đo này là diagnostic.
2. Chứng cứ quyền toàn thành phần cho sáu MOV sẽ được xác lập bằng nguồn nào khi trang lecture không có Credits công khai?
