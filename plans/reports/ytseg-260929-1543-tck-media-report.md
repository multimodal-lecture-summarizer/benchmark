# YTSeg `tCKk22kaZi4`: kiểm media toàn file

**Trạng thái:** media kỹ thuật `pass`; resource tổng thể `hold`. [Receipt JSON](./ytseg-260929-1543-tck-media-receipt.json) ghi URL, hash, decode và sáu điểm căn chỉnh.

MIT OCW xác nhận bài 14.01 Fall 2018 và transcript có chính `video_id`; [MIT DSpace](https://dspace.mit.edu/entities/publication/dd0b94b3-283f-4fb9-b6b8-a66e52cdb2f1) xác nhận khóa và giảng viên Jonathan Gruber. [Archive item](https://archive.org/details/MIT14.01F18) do `MIT OpenCourseWare`/`ocw-prod@mit.edu` phát hành chứa lecture 2. Trang OCW 2018 hiện không mở được, nên ánh xạ publisher MP4 dựa trên transcript OCW, metadata item và nội dung SRT; không dựa riêng vào thời lượng.

Đã tải đủ 98.407.054 byte MP4 và 76.025 byte SRT. SHA-256 MP4 `fcd4a38165cd2abf4eb244faa2f67d00da2fefd3d7418935812f705c2a88737d`; SHA-1 file khớp metadata Archive. File H.264 640×360/AAC dài 2.483,412 giây. `ffmpeg` giải mã toàn bộ hai stream exit 0; 74.427 frame video và 116.410 frame audio có PTS giải mã tăng đều. PTS packet video bị đảo thứ tự do B-frame, nên kiểm bằng PTS frame giải mã.

TRAIN row 1607 của Parquet ghim có duration 2.483 giây và 12 `raw_chapters`. Tại 10/50/90% và boundary nội bộ 11/928/2071 giây, SRT publisher nói đúng chủ đề tương ứng: model assumptions, marginal utility, prices of different sizes of goods; mở bài; chuyển sang utility functions; và chuyển sang ví dụ kích cỡ hàng hóa. Hình tại 928 giây cũng cho thấy Gruber giảng trên bảng. Đây là kiểm sáu vị trí của chính file, chưa chứng minh mọi boundary hoặc độ đúng mốc đến mức giây.

Giữ `hold_gt` vì không có mã chuyển đổi YTSeg upstream để giải thích đầy đủ title/timestamp relationship; giữ `hold_rights` vì chưa kiểm mọi thành phần hình ảnh trong file và MIT DSpace ghi BY-NC 3.0 US trong khi Archive item ghi BY-NC-SA 4.0; giữ `hold_duplicate` vì chưa có fingerprint nội dung từng cặp với MITFLD pilot. Không đưa file này vào D2 hay official RQ1.

## Câu hỏi chưa giải quyết

1. Có mã upstream cho phép xác nhận phép đọc GT của bản phát hành không?
2. Các thành phần hình ảnh trong toàn file và bản đăng lại khác ID có vượt cổng quyền/trùng nội dung không?
