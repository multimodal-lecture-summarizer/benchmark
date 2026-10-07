# Kiểm mốc GT Yale trên media giải mã: mốc giữa và cuối

**Kiểm:** 2026-09-28, khoảng 20:25–20:39 Asia/Bangkok. **Phạm vi:** 9 bài cố định trong [manifest mẫu](./rq1-yale-260928-1952-nine-course-qa-sample.csv). Đây là kiểm nguồn cục bộ, chưa phải official RQ1 hoặc D2.

## Phương pháp và kết quả

- Giữ nguyên mốc chapter có sẵn trên 9 trang Yale; mỗi bài chọn mốc giữa và mốc nội bộ cuối (18 vị trí). Tiêu đề và timestamp kiểm từ trang bài giảng của nhà xuất bản, ví dụ [ECON 159 L2](https://oyc.yale.edu/economics/econ-159/lecture-2), [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1); URL của cả 9 trang ở manifest mẫu. Không sửa GT theo nội dung giải mã.
- FFmpeg đọc trực tiếp URL MOV Yale, xin cửa sổ PCM 48 s bắt đầu 18 s trước mỗi mốc. `ffprobe` xác nhận ba clip 48.000 s và một clip 40.347 s vẫn chứa 18 s trước cùng 22 s sau mốc. Dùng Faster-Whisper `tiny.en` offline để định hướng kiểm chủ đề. Chỉ lưu [ledger số liệu và trạng thái](./rq1-yale-260928-2025-multi-boundary-decoded-media-gt-audit.csv); không lưu media, frame, ASR hoặc nguyên văn transcript trong repo.
- Sau khoảng 9 phút đọc từ xa bị nghẽn, dừng toàn bộ tác vụ. **4/18 vị trí** có audio giải mã đủ hai phía mốc để kiểm chủ đề: ECON 159 L2 tại 961 và 3937 s; ECON 251 L1 tại 2027 và 3502 s. **3/4** clip đủ 48 s; clip 2027 s chỉ có 40.347 s. **14/18** không được đánh giá: bốn artifact âm thanh thiếu trước/sau, một artifact rỗng, chín vị trí không có artifact tại lúc dừng. Byte của artifact chưa hoàn chỉnh chỉ mô tả tiến độ I/O, không phải clip hợp lệ.
- Trong 4 vị trí có thể xem, 3 có dấu chuyển chủ đề gần khu vực GT ở cấp clip, 1 chỉ phù hợp chủ đề rộng. Riêng mốc 2027 s của ECON 251 chuyển từ bối cảnh trước sang ví dụ tài chính sau mốc; clip ngắn vẫn bao phủ hai phía. Những quan sát này **không** xác lập onset tới ±3 s. ASR `tiny.en` có lỗi từ, phân đoạn dài, remote seek chưa đối chiếu PTS nguồn và không có nhãn onset độc lập. **0/9 bài được gán GT-pass; 0/18 mốc được xác minh sai số ±3 s.**

## Quyết định theo mức tin cậy

| Cách kiểm tiếp | Chất lượng thời gian | Chi phí/độ phức tạp | Rủi ro | Ưu tiên |
|---|---|---|---|---|
| Hash và giải mã file MOV đầy đủ đã được kiểm quyền, kiểm PTS rồi rà nhiều mốc độc lập | Cao nhất nếu file và PTS hợp lệ | Tải/lưu lớn, cần rà thủ công | Quyền thành phần và giới hạn D2 còn mở | **1, sau khi qua cổng quyền** |
| Remote seek thêm nhiều clip | Thấp trong điều kiện mạng quan sát được | Ít lưu trữ, nhiều timeout | Mẫu thiếu lệch về vị trí cuối; timestamp seek chưa chứng thực | 2, chỉ chẩn đoán |
| Phụ đề MOV làm mốc thay thế | Chưa xác định | Xử lý codec/PTS | 5/9 codec chưa giải được; caption không phải chapter GT độc lập | 3 |

**Kết luận cập nhật:** Giữ Yale ở trạng thái candidate. Không khóa D2 `eligible` và không chạy official 04a/04b từ phép kiểm này. Theo yêu cầu hiện hành, không dùng người rà độc lập hoặc tự tạo mốc/nhãn. Khi quyền thành phần được giải quyết, dùng file đầy đủ có SHA-256 và PTS để kiểm provenance, thứ tự và vị trí mốc Yale trong media; không diễn giải ASR thành GT, không sửa chapter GT Yale để tăng điểm.

## Giới hạn và câu hỏi chưa giải quyết

1. Remote MOV có thể tải và hash đầy đủ với quyền thành phần phù hợp cho cohort nào? Hiện không có bằng chứng full-file tại 9 bài này.
2. Phân bố sai số GT trên tất cả chapter và course độc lập là gì? Bốn mốc đánh giá cục bộ không cho phép suy rộng.
3. PTS sau remote seek và caption track có khớp timeline của MOV nguồn không?
