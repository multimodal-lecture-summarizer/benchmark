# Ngoại lệ quyền nội dung trong 35 video RQ1 MITFLD

Kiểm ngày 2026-09-28, theo đúng [35 ID đã chọn](./mitfld-rq1-35-260928-1120-selected.csv). [Ledger cấp ID](./mitfld-rq1-35-260928-1214-content-rights-ledger.csv), SHA-256 `7e499e20fdc747ee44853cad55c081efd9a77a4773f31bde57db70a426b35a92`. Đây là rà nguồn và mẫu nhỏ, không phải xác nhận quyền toàn video.

## Phát hiện

| Phạm vi | Kết quả | Mức kết luận |
|---|---|---|
| 35/35 trang tài nguyên OCW | HTTP 200; trích nội dung phần trang cụ thể và quét từ khóa quyền. | Trang công bố video, nhưng không liệt kê mọi thành phần bên trong. |
| 32/35 bài có transcript PDF liên kết | Trích text và quét từ khóa của 34 PDF URL (hai bài `6.801` mỗi bài có hai bản URL cùng nội dung). Ba bài không có PDF transcript liên kết trên trang đã kiểm. | Tìm marker `copyright`, `courtesy`, `permission`, `source` và tương tự. Kết quả âm trên transcript không kiểm slide/hình/âm thanh. |
| `JuKKBf-uSDI` / 15.S08 | [Slide Class 7 trang 5](https://ocw.mit.edu/courses/15-s08-fintech-shaping-the-financial-world-spring-2020/bf6652b320e525192082e047279ed17d_MIT15-S08S20_class7.pdf) ghi nội dung Tabul8tor được loại rõ khỏi CC của OCW. Khung giải mã từ [MP4 OCW](https://archive.org/download/MIT15.S08S20/MIT15_S08S20_Class07_300k.mp4) tại **900 s** hiển thị cùng slide “Libra vs. China DCEP”, cùng nguồn The Digital Currency Race/Tabul8tor. | **Một ngoại lệ CC được xác nhận là nằm trong video. Giữ bài này ở trạng thái hold**, không coi cả MP4 đã được cấp CC. |
| Cùng PDF Class 7 | Trang 8, 10, 12, 13, 15, 19–21, 24–25 đánh dấu nội dung bên thứ ba khác bị loại khỏi CC; trang 6, 9, 18 ghi used with permission. | Các trang này thuộc tài liệu giảng dạy liên kết; chưa đối chiếu riêng vị trí của từng trang trong video. |
| `9uqKU5ZDwfM` / 22.01 | [OCW mô tả](https://ocw.mit.edu/courses/22-01-introduction-to-nuclear-engineering-and-ionizing-radiation-fall-2016/resources/chernobyl-trip-report-by-jake-hecla/) Jake Hecla trình chiếu nhiều ảnh từ chuyến đi Chernobyl. | Nguồn và quyền từng ảnh chưa xác minh; cần rà frame/credit có chủ đích. |
| `neBeTYziSLo` / 11.382 | [OCW Selected Videos](https://ocw.mit.edu/courses/11-382-water-diplomacy-spring-2021/pages/selected-videos/) xác định đây là bài trình bày sinh viên của Flora Klise. | Chưa rõ quyền slide/ảnh và quyền người trình bày cho mọi cách dùng. |

Khung mẫu `JuKKBf-uSDI` tại 300, 450, 600 s hiển thị trang Study Questions, và 900 s hiển thị trang có ngoại lệ. Chỉ bốn khung, không phải rà toàn timeline. Lượt thử lấy thêm bốn khung ở Chernobyl và Water Diplomacy bị FFmpeg timeout 50 s; **không có kết quả hình mới** ở hai video này.

[Điều khoản OCW cập nhật 2026-08-11](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) công bố CC BY-NC-SA 4.0, đồng thời cảnh báo giấy phép có thể không đủ mọi quyền khác; OCW cũng mô tả quy trình rà quyền trước khi công bố. Đây là căn cứ đáng tin cho quyền của phần OCW sở hữu, nhưng không ghi đè loại trừ cụ thể trên slide. Transcript của `7LyvAVjQUR8` nhắc tài liệu có bản quyền đăng ở nơi phải đăng nhập; lời nói này chưa chứng minh tài liệu đó xuất hiện trong video.

## Kết luận cho cohort

**1/35 video có ngoại lệ CC bên trong được xác nhận; 34/35 còn chưa xác định đầy đủ**, gồm hai bài có cờ nội dung cần rà sâu. Không được suy ra 34 video đó không có ngoại lệ. `JuKKBf-uSDI` nên được giữ ngoài D2 cho đến khi có cơ sở sử dụng thành phần bị loại, hoặc thay bằng reserve cùng khóa theo quy tắc đã khóa. Không tự loại bài chỉ vì slide tài liệu có cờ; ở đây có chứng cứ frame video tại 900 s.

| Thứ tự xử lý `JuKKBf-uSDI` | Công sức / tính khớp benchmark | Rủi ro áp dụng |
|---|---|---|
| **1. Hold, kiểm reserve kế tiếp cùng 15.S08** | Ít thay đổi protocol; giữ split theo khóa và timebase MP4 nguyên bản. | Reserve có thể có ngoại lệ tương tự; phải kiểm cấp file trước khi thay. |
| 2. Xin phép cho thành phần bị loại hoặc được OCW xác nhận phạm vi dùng | Giữ đúng video đã chọn. | Chờ phản hồi, quyền có thể chỉ giới hạn cách dùng; không mặc nhiên cho phép công bố bản sao. |
| 3. Che/cắt slide bị loại | Có thể tạo bản media mới. | Phức tạp, thay input và có nguy cơ lệch GT; chỉ dùng nếu định nghĩa lại protocol và kiểm toàn timeline. |

Ưu tiên 1 phù hợp thiết kế cohort có reserve cùng khóa và tránh sửa input sau khi chọn. Đây là quyết định tạm về **quy trình xác minh**, chưa phải quyết định loại bài hay giấy phép cuối cùng.

## Câu hỏi chưa giải quyết

1. Những trang slide loại khỏi CC còn lại của 15.S08 xuất hiện tại mốc nào trong MP4, và quyền nào cho phép đúng cách sử dụng benchmark dự kiến?
2. Nguồn ảnh/đối tượng xuất hiện trong `9uqKU5ZDwfM`, `neBeTYziSLo` và 32 video khác có ngoại lệ nào không?
3. Có cần thay `JuKKBf-uSDI` bằng reserve cùng khóa ngay, hay chờ xác nhận phạm vi sử dụng hợp lệ của hình bên thứ ba?
