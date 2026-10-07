# Nghiên cứu tiếp: nguồn tải MITFLD, ngữ nghĩa GT và split độc lập

Kiểm tra: 2026-09-28 (Asia/Bangkok). Mẫu cố định: 10 video MITFLD đã ánh xạ với MIT OCW trong [báo cáo trước](./research-260928-1006-mitfld-rights-course-map-ytseg-api-report.md). Chỉ đọc HTML, mã nguồn và HTTP `HEAD`; không tải hay giải mã media. Kết quả là bằng chứng nghiên cứu, không phải xác nhận pháp lý cho toàn bộ 538 video.

## Kết luận

**Cả 10/10 trang tài nguyên OCW mẫu đều có link MP4 tải video; 10/10 đích trả `HEAD 200` và `Content-Type: video/mp4`.** Hai link nằm trên `ocw.mit.edu`, tám link trỏ tới `archive.org`. Đây là đường tải được **trang OCW công bố**, mạnh hơn việc chỉ biết video tồn tại trên YouTube hoặc kho MITFLD. Tuy nhiên OCW [cảnh báo](https://ocw.mit.edu/courses/8-962-general-relativity-spring-2020/download/) các trang ngoài có thể có điều khoản/quyền khác. Chưa kiểm tra điều khoản Archive.org cho từng item hoặc bản MP4 MITFLD có đồng nhất với file OCW liên kết. Không đưa cả 10 vào `rights_cleared` chỉ từ `HEAD`.

Mã nguồn tác giả [MITFLD loader](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/mitfld.py) đọc mỗi `frags/<id>.json` như dãy số; [base dataset](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/base_dataset.py) xử lý chúng như **ranh giới các fragment**, thêm/sửa mốc 0 và mốc cuối theo thời lượng video nếu thiếu. Điều này làm rõ cách **code diễn giải GT**, nhưng nguồn tạo nhãn, quy trình gán nhãn, quyền của nhãn và độ khớp với bản OCW vẫn chưa được tài liệu công khai đã kiểm xác nhận. `random_split` trong cùng file xáo trộn **từng video**, không group theo `course_id`; không thể dùng nguyên hàm đó để tuyên bố split độc lập theo khóa học.

## Kiểm tra link MP4 do OCW công bố

| MITFLD ID | Khóa | Trang nguồn OCW | Host MP4 được trang dẫn tới | `HEAD` |
|---|---|---|---|---|
| `-Pg11JHzUTo` | 24.900 | [Lecture 9](https://ocw.mit.edu/courses/24-900-introduction-to-linguistics-spring-2022/resources/ocw_24900_lecture09_2022mar03/) | `ocw.mit.edu` | 200, `video/mp4` |
| `6MssatXXAzc` | 8.962 | [Lecture 6](https://ocw.mit.edu/courses/8-962-general-relativity-spring-2020/resources/lecture-6-the-principle-of-equivalence/) | `archive.org` | 200, `video/mp4` |
| `EXYw8_pnKr0` | 11.165J | [Lecture 8](https://ocw.mit.edu/courses/11-165j-urban-energy-systems-and-policy-fall-2022/resources/ocw_11165_lecture08_2022sep30_mp4/) | `ocw.mit.edu` | 200, `video/mp4` |
| `LMSTMBX_2F4` | 3.091 | [Lecture 32](https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/resources/lecture-32/) | `archive.org` | 200, `video/mp4` |
| `R2vL2wLqGYg` | 8.962 | [Lecture 16](https://ocw.mit.edu/courses/8-962-general-relativity-spring-2020/resources/lecture-16-gravitational-radiation-i/) | `archive.org` | 200, `video/mp4` |
| `Z2ScgFh81Dc` | 7.05 | [Lecture 21](https://ocw.mit.edu/courses/7-05-general-biochemistry-spring-2020/resources/lecture-21-glycolysis-ii-regulation/) | `archive.org` | 200, `video/mp4` |
| `g0bXSXuLVb0` | 6.006 | [Problem Session 3](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/resources/problem-session-3/) | `archive.org` | 200, `video/mp4` |
| `mhQebe1Y4d0` | MAS.S62 | [Lecture 6](https://ocw.mit.edu/courses/mas-s62-cryptocurrency-engineering-and-design-spring-2018/resources/lec6-spv-and-wallet-types/) | `archive.org` | 200, `video/mp4` |
| `smHwRzk81b0` | 9.40 | [Lecture 10](https://ocw.mit.edu/courses/9-40-introduction-to-neural-computation-spring-2018/resources/10/) | `archive.org` | 200, `video/mp4` |
| `z_xyx-z6arc` | 22.01 | [Lecture 11](https://ocw.mit.edu/courses/22-01-introduction-to-nuclear-engineering-and-ionizing-radiation-fall-2016/resources/radioactivity-and-series-radioactive-decays/) | `archive.org` | 200, `video/mp4` |

Đọc text hiển thị của cả 10 trang không thấy chuỗi “credits” hoặc “all rights reserved” riêng cho video. Đây là **kết quả rà HTML có giới hạn**; không chứng minh media không chứa nội dung bên thứ ba. [Điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) và ngoại lệ quyền vẫn phải áp dụng cho từng tài nguyên. Link OCW trỏ tới Archive.org không tự xác nhận giấy phép của trang Archive item.

## GT và giao thức khoa học

- [Card MITFLD](https://huggingface.co/datasets/robotwang/MITFLD) gọi `frags` là ground truth fragment annotations, nhưng không mô tả ai gán nhãn, tiêu chí ranh giới, kiểm định liên chủ thể hay giấy phép riêng. [Repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation) chỉ dẫn tải dataset và trích dẫn bài báo; mã loader xác nhận cấu trúc dãy ranh giới, không xác nhận provenance. Bản công khai tìm được của [bài báo](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) có abstract, không cung cấp phương pháp gán nhãn chi tiết trong nội dung đọc được.
- Loader của tác giả tự chèn 0 nếu mốc đầu >1 giây và thêm duration nếu mốc cuối cách cuối video >=2 giây. Vì vậy số lượng/giá trị ranh giới **sau khi load** có thể khác JSON gốc. Benchmark phải lưu cả JSON raw lẫn quy tắc chuẩn hóa GT đã đóng băng; không gọi raw `frags` là chapter GT độc lập hoặc nhãn chuyên gia khi chưa có provenance.
- Mẫu có 9 lecture-like từ **8 khóa** sau loại Problem Session. Hai lecture 8.962 phải cùng phía split. Hàm `random_split` của tác giả [xáo trộn index video](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/base_dataset.py), nên chỉ dùng nếu đánh giá theo video thông thường; official RQ1 cần split riêng theo group khóa/nguồn, khai báo trước và đủ số group.
- YTSeg là tác vụ khác: [bài báo gốc](https://aclanthology.org/2024.eacl-long.25.pdf) nêu chapter do người đăng cung cấp; câu transcript được căn theo closed captions, và split gốc phân tầng theo channel identifier. Do đó chapter YTSeg là nhãn biên tập, không tự trở thành expert GT; subset CC BY chỉ có train/14 kênh nên không cung cấp held-out độc lập sẵn có.

## Quyết định tiếp theo

1. Với pilot visual có quyền rõ hơn, ưu tiên **hai file trên host OCW** trước; kiểm điều khoản/credits của đúng tài nguyên và chỉ tải sau khi ghi ledger. Tám file Archive.org cần thêm kiểm tra item-level terms/provenance. Không dùng `yt-dlp` để thay thế đường OCW.
2. Hỏi tác giả MITFLD về phương pháp và giấy phép của `frags`, transcript, bản MP4; xin bảng `video_id → course_id`, nếu có. Đây là phần không thể suy ra chắc chắn từ code hoặc HTTP.
3. Trước một phép so sánh điểm số mới, khóa schema GT: raw boundary hay normalized boundary, endpoint tolerance, duration nguồn, và cách xử lý lệch thời lượng. Sau đó mới chọn group-disjoint split/D2 theo master protocol.

## Câu hỏi chưa giải quyết

- Tám item trên Archive.org có điều khoản/quyền cụ thể gì; MP4 MITFLD có hash/thời lượng/nội dung khớp đúng bản OCW không?
- Ai tạo `frags`, theo tiêu chí nào, có kiểm định chất lượng và giấy phép sử dụng/tái phân phối riêng không?
- Trong đủ 538 video, bao nhiêu lecture từ bao nhiêu khóa còn lại sau lọc loại bài, quyền, media và GT; có đủ group cho train/validation/final test độc lập không?
