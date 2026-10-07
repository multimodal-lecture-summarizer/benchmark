# Rà khung có chủ đích cho hai bài còn nghi vấn quyền

Ngày 2026-09-28. Bổ sung cho [ledger quyền 35 bài](./mitfld-rq1-35-260928-1214-content-rights-ledger.csv). Các khung được giải mã trực tiếp từ MP4 do trang OCW dẫn; ảnh tạm chỉ dùng để quan sát và không đưa vào artifact công bố.

| ID | MP4 OCW | Mốc đã xem | Quan sát trực tiếp | Kết luận quyền |
|---|---|---:|---|---|
| `9uqKU5ZDwfM` | [Lecture 28](https://archive.org/download/MIT22.01F16/MIT22_01F16_Lec28_300k.mp4) | 516, 1297, 1679 s | Slide chứa ảnh tư liệu công nghiệp/Chernobyl, ảnh nhóm người và ảnh công trình; không thấy dòng ghi nguồn đủ đọc ở các khung 640 px. | Nguồn từng ảnh chưa xác định. Giữ `photo_origin_unverified`; ba khung không chứng minh toàn video có hay không có ngoại lệ CC. |
| `neBeTYziSLo` | [Singapore–Malaysia Water Conflict](https://archive.org/download/MIT11.382S21/MIT11_382S21_6-singapore-malaysia_300k.mp4) | 1600 s | Khung có gương mặt người trình bày, slide “Improve Negotiations by Utilizing WDF” và biểu trưng Liên Hợp Quốc. | Quyền slide, hình người và phạm vi dùng biểu trưng chưa xác định. Giữ `student_presentation_rights_unverified`; biểu trưng xuất hiện không tự chứng minh vi phạm hay ngoại lệ giấy phép. |

Lệnh lấy mẫu dùng `ffmpeg -ss <seconds> -i <ocw_mp4_url> -frames:v 1 -vf scale=640:-2`. Mẫu này **không phải** rà toàn bộ hình, âm thanh hay credit. Một ảnh/video có thể được cấp quyền riêng hoặc dùng theo ngoại lệ pháp luật mà khung đơn lẻ không thể xác nhận.

## Câu hỏi chưa giải quyết

1. Nguồn/credit và phạm vi quyền của các ảnh trong bài Chernobyl là gì?
2. Những thành phần trong bài Water Diplomacy được OCW/người trình bày cấp phép đến mức nào?
