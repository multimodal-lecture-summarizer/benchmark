# PHYS 200 L19: MOV local, sáu chapter GT và visual

**Kiểm:** 2026-09-29, khoảng 08:19–08:27 Asia/Bangkok. File người dùng cung cấp: `C:\Users\hung\Downloads\phys200_19_111306.mov`. Đây là bài thứ hai có media đầy đủ trong [mẫu Yale 9 khóa đã cố định](./rq1-yale-260928-1952-nine-course-qa-sample.csv). Giữ nguyên 7 chapter/6 mốc nội bộ của [Yale PHYS 200 L19](https://oyc.yale.edu/physics/phys-200/lecture-19). [Biên nhận JSON](./rq1-yale-260929-0827-phys200-l19-local-mov-receipt.json) chỉ lưu số liệu và hash, không chứa media, frame hoặc lời ASR.

## Toàn file và đồng hồ media

| Kiểm | Kết quả |
|---|---|
| Kích thước/SHA-256 | 639.913.047 byte; `47DBC049C2C7998E84325D5819FF4257F32D992BE2E275FA10C2F0FE26A6DDB9`. |
| Nguồn Yale | HTTP `HEAD 200 video/quicktime`, `Content-Length` 639.913.047 byte; ETag opaque `"26244c57-5cafc47016adf"`, Last-Modified `2021-09-02 05:15:55 GMT`. Kích thước/filename khớp; Yale không cung cấp SHA-256 tham chiếu để chứng minh byte-identical với server. |
| Luồng chính | H.264 640×360, 129.277 frame, 4.313,546880 s; AAC stereo, 4.313,546871 s, cùng start PTS 0. |
| Giải mã toàn bài | `ffmpeg -xerror` map video+audio đến EOF, exit 0, không báo lỗi. |
| PTS | 129.277 packet video và 185.769 packet audio; 0 bước PTS lùi, bước tối đa 0,033367 s và 0,023220 s. |

## Mốc chapter trên audio cục bộ

Hai mô hình ASR cache offline (`base.en`, `tiny.en`) kiểm cửa sổ 50 s quanh **cả sáu** mốc. Bảng là thời điểm bắt đầu câu **chuyển đoạn** theo ASR, so với mốc Yale; nó không phải nhãn onset semantic độc lập.

| Yale (s) | `base.en` lệch (s) | `tiny.en` lệch (s) | Cách hiểu |
|---:|---:|---:|---|
| 531 | +0,72 | +0,68 | Kết recap, mở phần phân tích tính tuần hoàn. |
| 1059 | +0,06 | +0,32 | Chuyển sang năng lượng của sóng. |
| 1802 | −0,02 | +0,50 | Chuyển sang hiệu ứng Doppler. |
| 2338 | −0,02 | +0,04 | Khép Doppler, mở phần còn lại về tính chồng chất/giao thoa. |
| 2937 | +0,68 | +1,08 | Chuyển sang bài toán hai sóng/khe đôi. |
| 3690 | +0,26 | +0,28 | Mở ứng dụng nhạc cụ. |

**Cảnh báo GT:** mốc publisher rất sát câu chuyển đoạn, nhưng khái niệm trong tên chapter có thể được nói rõ muộn hơn: mốc 531 → câu đặt câu hỏi về tham số sóng khoảng **+9,58 s**; mốc 2338 → nêu giao thoa khoảng **+12,48 s**; mốc 2937 → nêu thí nghiệm khe đôi khoảng **+12,82 s**. Đây là hai định nghĩa khác nhau của “boundary”: biên tập đoạn và lần nhắc khái niệm. [Transcript Yale](https://oyc.yale.edu/physics/phys-200/lecture-19) cũng đặt tiêu đề tại câu mở đoạn. Không lấy offset ASR ~1 s để tuyên bố mọi mốc là onset semantic ±3 s. Official RQ1 phải giữ publisher GT đã đăng ký, mô tả ý nghĩa nhãn này và có rà onset độc lập theo rubric trước `gt_pass`.

## Visual/OCR và quyền

Xem contact sheet **72 frame, mỗi phút một frame** của toàn bài: phần lớn là giảng viên, bảng phấn, công thức và sơ đồ sóng; không thấy slide/hình bên ngoài trong mẫu. Tín hiệu hình vật lý có thật và liên quan bài, nhưng sampling phút có thể bỏ sót thành phần ngắn. Contact sheet/frame tạm đã xóa; không đưa vào repo.

Chạy PaddleOCR English trên **14 frame bổ sung** mỗi 300 s (300–4200 s), ngoài 5 frame đã kiểm trước: 14/14 có ít nhất một detection, **3/14** vượt proxy ≥3 dòng confidence cao. Kiểm nội dung của ba khung proxy dương tại 2700/3300/3600 s thấy watermark, ký hiệu toán/chữ phấn đọc sai đáng kể; không tính 3/14 là độ chính xác OCR. Không có bản chép tham chiếu nên chưa có CER. OCR không phải điều kiện loại bài đã đăng ký trong [master RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md); nếu OCR yếu, phải ghi coverage/missingness trước khi chấm model, không chọn bài theo score OCR sau khi xem kết quả.

[Trang Yale](https://oyc.yale.edu/physics/phys-200/lecture-19) không hiện Credits/ngoại lệ cụ thể; ảnh mẫu chủ yếu là bảng và giảng viên. [Yale Terms](https://oyc.yale.edu/terms) loại thành phần bên thứ ba khỏi CC mặc định. Chưa xem từng giây hoặc xác minh toàn bộ hình/tài liệu kèm theo, nên `full_mov_rights_unverified` vẫn chính xác cho phạm vi xử lý nội bộ, chỉ công bố số liệu. Không suy “không thấy trong 72 frame” thành `rights_pass`.

## D2 và việc tiếp

**2/9 file mẫu đã có full-file SHA-256, giải mã toàn bài và PTS sạch**: ECON 159 L2 và PHYS 200 L19, thuộc hai giảng viên/khóa khác nhau. PHYS 200 cung cấp visual bảng/sơ đồ nhiều hơn ECON 159, nhưng OCR văn bản vẫn yếu. Sáu biên tập chapter có bằng chứng cục bộ phù hợp; chưa có human/independent GT-pass. D2 official vẫn `blocked_decision`: quyền thành phần toàn file chưa khép, quy trình GT/quality chưa freeze, 7 file còn lại chưa hash và chưa có split course/instructor-disjoint đã xác nhận. Không chạy official 04a/04b.

Theo [thứ tự qualification](./rq1-yale-260928-2206-next-media-qualification-shortlist-report.md), bài tiếp theo có giá trị phân biệt visual cao nhất là ECON 251 L1, nhưng phải giữ `visual_source_review` cho biểu đồ; ENGL 220 L23 là dự phòng ít dữ liệu hơn. Không tải toàn bộ 226 bài từ trạng thái 2 file này.

## Câu hỏi chưa giải quyết

1. Có thành phần bên thứ ba xuất hiện ngắn hoặc trong tài liệu đi kèm không, và cơ sở quyền nào áp dụng cho xử lý nội bộ?
2. Rubric official đánh giá ranh giới biên tập Yale hay onset khái niệm, và việc dẫn nhập 9–13 s được ghi như thế nào trong phân tích lỗi?
3. OCR/missingness sẽ được biểu diễn và báo cáo theo file/course ra sao khi chữ bảng 640×360 khó đọc?
4. Sau quyền/GT/hash các khóa khác, còn đủ giảng viên để tạo split D2 độc lập không?
