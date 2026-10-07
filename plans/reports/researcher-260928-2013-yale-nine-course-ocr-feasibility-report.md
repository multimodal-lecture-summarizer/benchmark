# Yale MOV 640×360: OCR feasibility trên 9 bài mẫu

## Phương pháp và bằng chứng

- Tập cố định: 9 dòng trong `rq1-yale-260928-1952-nine-course-qa-sample.csv`, mỗi khóa 1 bài. Lấy đúng 5 frame/bài tại `floor(duration × 10/30/50/70/90%)` giây. FFmpeg seek trực tiếp URL MOV Yale; không tải toàn bộ file. 45/45 frame giải mã ở 640×360.
- Chạy PaddleOCR English với model đã cache, không phóng ảnh hay hiệu chỉnh. `confident_line`: từ 4 ký tự, confidence ≥0,70. Chỉ số này là proxy phát hiện chữ, **không phải** độ chính xác OCR hay CER.
- [Ledger số liệu từng frame](rq1-yale-260928-2013-ocr-frame-metrics.csv) lưu thời điểm, số dòng/ký tự và confidence, không lưu nội dung chữ. SHA-256: `d7078eaa489f61564b9a09282bbad58dc4ee04b1cf5fcad610c17437aab96c9d`. Frame/contact sheet chỉ ở thư mục tạm để xem, không đưa vào repository.
- PaddleOCR cài sẵn xung đột NumPy 2 ở `np.sctypes`; phép đo dùng shim chỉ trong tiến trình Python. Không sửa code hay model. Đây là yếu tố tái lập cần ghi khi làm runner chính thức.

## Kết quả

| Phép đo | Kết quả | Cách hiểu |
|---|---:|---|
| Frame giải mã | 45/45 | Video truy cập được tại 5 vị trí/bài mẫu. |
| Có ít nhất 1 dòng OCR | 41/45 | Bao gồm watermark/nhãn không liên quan; không phải tỷ lệ frame có chữ bài giảng. |
| ≥3 dòng `confident_line` | 7/45 | Proxy thô: ECON 251 1, ECON 252 1, ENGL 300 3, PHYS 200 2. |
| Slide chữ rõ và OCR đọc tốt khi đối chiếu bằng mắt | 1/45 chắc chắn | ECON 251 L1 tại 70%; 10 dòng confident, 171 ký tự, mean confidence 0,973. |

Xem contact sheet 45 frame: ECON 159, ENGL 220/291/310 chủ yếu là giảng viên và bảng trống; ENGL 300 có chữ phấn nhưng OCR sai đáng kể; PHYS 200/201 có sơ đồ/công thức lớn, OCR văn bản hỏng nhiều; ECON 252 có đồ thị nhưng OCR chủ yếu đọc số trục. Đầu ra confidence cao vẫn có thể là watermark, ký hiệu toán sai hoặc chữ phấn sai. Do đó 7/45 **không** là 7 frame có OCR học thuật dùng được. Chưa có bản chép tay chuẩn để tính CER.

## Kết luận cho D2

Media 640×360 cung cấp visual ở một số bài, nhưng **chưa chứng minh OCR ổn định trên cohort**. Không dùng tỷ lệ 1/45 hay 7/45 để ngoại suy 226 bài vì mẫu 9 bài được chọn theo luật riêng và chỉ 5 thời điểm/bài. Không lấy OCR yếu làm lý do sửa GT publisher hay tự tạo GT. Nếu OCR là điều kiện bắt buộc cho official RQ1, cần chốt ngưỡng và khảo sát toàn bộ cohort đã chọn trước với chép tham chiếu độc lập; nếu OCR chỉ là nhánh ablation, ghi rõ coverage theo file và không quảng bá chất lượng OCR chưa kiểm.

## Câu hỏi còn mở

1. Protocol official RQ1 yêu cầu OCR đạt ngưỡng theo mỗi video hay chỉ chạy được/ghi coverage? Ngưỡng chưa được freeze.
2. Cần chép tay vùng chữ tham chiếu ở bao nhiêu frame và sampling nào để ước lượng CER không thiên lệch?
