# ECON 159 L2: kiểm MOV Yale đã tải tại máy

**Kiểm:** 2026-09-28, khoảng 21:50–21:57 Asia/Bangkok. **File người dùng cung cấp:** `C:\Users\hung\Downloads\econ159_02_091007.mov`. Đây là một bài trong [mẫu Yale 9 khóa đã cố định](./rq1-yale-260928-1952-nine-course-qa-sample.csv). Giữ chapter GT sẵn có của [Yale ECON 159 L2](https://oyc.yale.edu/economics/econ-159/lecture-2). [Biên nhận máy đọc được](./rq1-yale-260928-2157-econ159-l2-local-mov-receipt.json) chỉ lưu thông số/hash, không lưu media hoặc nội dung trích xuất.

## Kết quả file và timeline

| Kiểm | Kết quả |
|---|---|
| Kích thước và định danh | 601.595.188 byte; SHA-256 `A25DBE7B4DE66F7978C6C503DA1B20548D301C116A9D4B9FD6224D7889113EDF`. |
| Đối chiếu nguồn | HTTP `HEAD 200`, `Content-Length` 601.595.188 byte, ETag opaque `"23db9d34-5cafcedcaa1ee"`, Last-Modified `2021-09-02 06:02:33 GMT`. Trùng kích thước, filename và metadata bài Yale; server không cung cấp SHA-256 tham chiếu nên không tuyên bố so khớp byte với server. |
| Video/audio | H.264 640×360, 123.732 frame, 4.128,528529 s; AAC stereo, 4.128,528526 s. Format container 4.129 s do làm tròn. Bắt đầu PTS 0. |
| Giải mã toàn bài | `ffmpeg -xerror` giải mã cả video và audio đến cuối, exit 0, không báo lỗi. |
| Liên tục thời gian | 123.732 packet video, 177.801 packet audio, không có bước PTS lùi; bước PTS lớn nhất lần lượt 0,033367 s và 0,023220 s. |

Từ file local, trích **trong bộ nhớ** cửa sổ audio 50 s quanh cả bốn chapter start nội bộ. Faster-Whisper `tiny.en` offline ước lượng câu mở chủ đề; đối chiếu với tên chapter và transcript trên trang Yale, không đổi GT:

| Chapter start Yale (s) | Câu mở chủ đề theo ASR local (s) | Lệch ước lượng (s) | Nhận xét |
|---:|---:|---:|---|
| 407 | 407,58 | +0,58 | Chuyển từ recap sang thành phần hình thức của trò chơi. |
| 961 | 961,42 | +0,42 | Chuyển từ phần ký hiệu sang ví dụ về chiến lược. |
| 2129 | 2129,78 | +0,78 | Kết thúc ví dụ Hannibal rồi trở lại trò chơi trước đó. |
| 3937 | 3937,18 | +0,18 | Mở phần minh họa về common knowledge. |

**Kết luận GT cho đúng file này:** cả 4 mốc có tín hiệu chuyển nội dung gần mốc publisher và ước lượng ASR dưới 1 s. Đây là bằng chứng local mạnh hơn remote seek trước đó. `tiny.en` vẫn có lỗi từ và ASR không phải nhãn onset độc lập; chưa gán `gt_pass` official ±3 s trước khi khóa rubric và rà độc lập trên media gốc. Không suy rộng sang 8 bài còn lại.

**Kiểm chéo 22:00:** chạy thêm Faster-Whisper `base.en` cache offline trên cùng bốn cửa sổ, không chỉnh GT. Onset ước lượng lần lượt `407,32 / 961,02 / 2129,74 / 3937,04 s`, lệch Yale `+0,32 / +0,02 / +0,74 / +0,04 s`. Hai mô hình đồng ý về vị trí chuyển chủ đề trong phạm vi dưới 1 s; đây vẫn là hai ước lượng ASR, không thay nhãn độc lập.

## Visual/OCR và quyền thành phần

Đã xem contact sheet một frame mỗi phút trên toàn bài (~69 frame) ở độ phân giải nguồn. Trong mẫu thấy giảng viên, sinh viên, bảng và chữ phấn; không phát hiện slide/hình bên ngoài. Sampling này có thể bỏ sót thành phần xuất hiện ngắn và không thay kiểm quyền toàn file. Contact sheet/frame tạm đã xóa.

Chạy PaddleOCR English trên 13 frame bổ sung ở mốc 300–3900 s, cách nhau 300 s. Phần lớn frame cho một dòng là watermark Yale. Frame bảng tại 600 s có 9 dòng OCR, 3 dòng vượt proxy confidence, nhưng nội dung học thuật đọc sai khi so bằng mắt; không được tính là 3 dòng hữu ích. [Mẫu OCR 5 thời điểm trước](./rq1-yale-260928-2013-ocr-frame-metrics.csv) cũng chỉ phát hiện một dòng/frame tại bài này. Chưa có bản chép tham chiếu để tính CER. **Video có tín hiệu bảng thật nhưng OCR tự động ở 640×360 rất yếu**; không dùng confidence làm cổng chất lượng.

[Trang Yale](https://oyc.yale.edu/economics/econ-159/lecture-2) không nêu Credits/ngoại lệ cụ thể, và mẫu frame không phát hiện tác phẩm bên ngoài. Metadata MOV vẫn cảnh báo một số thành phần của dự án có thể bị hạn chế theo thỏa thuận với bên thứ ba. Theo [Yale Terms](https://oyc.yale.edu/terms), giấy phép chung không tự bao phủ thành phần ấy. Phạm vi người dùng là xử lý nội bộ, chỉ công bố số liệu/biểu đồ; vẫn giữ `full_mov_rights_unverified`, không tự gán `rights_pass` từ mẫu hình hoặc metadata.

## Quyết định D2

**Cổng file integrity và giải mã của ECON 159 L2 đã có bằng chứng; 1/9 bài mẫu nay có full-file SHA-256.** [Quyết định D2 trước](./rq1-yale-260928-2045-d2-blocked-decision.json) là snapshot tại 20:45; biên nhận mới bổ sung một file, không sửa ngược snapshot. D2 official vẫn `blocked_decision`: quyền thành phần chưa khép, chất lượng OCR chưa có policy/CER, GT chưa có rà độc lập theo rubric, còn 8 bài chưa có full-file hash và chưa có cohort/split độc lập theo khóa/giảng viên. Không chạy official 04a/04b hoặc amendment master plan dựa trên một bài.

## Câu hỏi chưa giải quyết

1. Có cơ sở quyền cụ thể cho toàn MOV theo xử lý nội bộ phi thương mại, kể cả thành phần xuất hiện ngắn mà sampling chưa thấy không?
2. Ngưỡng OCR/coverage nào là điều kiện official RQ1, và có cần chép tham chiếu để đo CER cho chữ bảng 640×360?
3. Ai rà độc lập bốn mốc onset theo rubric ±3 s, và các bài/khóa còn lại có chất lượng tương tự không?
4. Sau khi kiểm đủ file, còn bao nhiêu khóa/giảng viên đủ điều kiện cho split course-disjoint?
