# RQ1 Open Yale: video 640×360, link PHYS 201, và trần cohort sau sàng lọc

**Kiểm:** 2026-09-28, Asia/Bangkok. Tiếp nối [báo cáo Yale đầu tiên](./rq1-yale-qualification-260928-1916-publisher-media-gt-rights-report.md). Official RQ1 chỉ dùng chapter GT có sẵn của publisher; MITFLD 35 vẫn là pilot. Chỉ kiểm trang Yale, HTTP metadata/byte-range, `ffprobe` trên URL và một frame mẫu; không tải toàn bộ 226 video, không niêm phong D2.

**Cập nhật 19:52:** [QA mẫu 9 khóa](./rq1-yale-qa-260928-1952-nine-course-rights-visual-gt-sample-report.md) phát hiện thêm ba bài văn học có rủi ro quyền thành phần từ transcript/handout dù trang không có thông báo Credits; 177 vẫn chỉ là tập ưu tiên metadata. Đã kiểm 18 frame và 9 clip boundary trên MOV, chưa xác nhận bài official eligible.

**Phạm vi sử dụng chốt 20:04:** video Yale chỉ xử lý nội bộ, công bố số liệu/biểu đồ, không phát hành media hoặc trích xuất. Đánh giá quyền theo phạm vi này; tiếp tục giữ điều kiện phi thương mại/ghi công và kiểm cơ sở xử lý thành phần bên thứ ba. Không suy từ việc không phát hành media thành quyền tự động dùng mọi thành phần.

## Kết luận

1. **Có bản video Yale 640×360:** 226/226 đường `.mov` suy ra từ video mobile cùng số bài trả `HEAD 200` trên `openmedia.yale.edu`. `ffprobe` xác nhận H.264 640×360 trên 11 bài mẫu phủ cả 9 khóa, gồm PHYS 201 L24–L25. [Yale Help](https://oyc.yale.edu/help) mô tả bản QuickTime băng thông cao; các trang bài hiện hành chủ yếu lộ YouTube và MP3, nên đường `.mov` là đường publisher-hosted **đã xác minh HTTP**, không phải link tải hiển thị trực tiếp trên trang bài. 640×360 có bốn lần pixel so với mobile 320×180; độ đọc được của bảng/slide và OCR trên toàn cohort **chưa được kiểm**.
2. **Hai link 404 đã tìm được đường khác:** [index PHYS 201](https://openmedia.yale.edu/projects/iphone/departments/phys/phys201.html) ghi nhầm `011910`/`012110`; trang [L24](https://oyc.yale.edu/physics/phys-201/lecture-24) và [L25](https://oyc.yale.edu/physics/phys-201/lecture-25) dùng stem MP3 `041910`/`042110`. Video `.m4v` và `.mov` với hai stem này đều tồn tại. Đây là sửa **truy cập media**, chưa phải xác minh đồng bộ GT hay quyền.
3. **Số đủ điều kiện official vẫn 0 đã xác nhận.** 226 bài có đường HD ở mức HEAD; 224 có GT không vướng hai lỗi cấu trúc đã thấy; 10 bài có thông báo rõ nội dung bên thứ ba không thuộc CC; sau khi giữ thêm 37 bài còn lại có chapter cuối >20 phút để review, **177 bài / 9 khóa / 8 giảng viên** là tập *ưu tiên thẩm tra sâu*, không phải cohort đã được cấp quyền hay đạt D2.

## Cách kiểm và bằng chứng media

[HEAD ledger 226 dòng](./rq1-yale-260928-1937-higher-resolution-mov-head-scan.csv), SHA-256 `D56C6555FF00B99753826A7CAFF1A2DBD5DE0A1749A676C3B09DBCB7EB677A1B`. Tạo đường `.mov` bằng cách giữ nguyên course, số bài, date stem của [ledger mobile](./rq1-yale-260928-1916-nine-course-metadata-ledger.csv), thay thư mục `iphone`/`m4v` thành `mov`; riêng PHYS 201 L24–L25 sửa date stem theo MP3 Yale. Kiểm `HEAD`, content type và Content-Length cho cả 226; 226 trả `200 video/quicktime`. Tổng dung lượng **HTTP khai báo** 136,34 GiB (mỗi file 350 MB–1,00 GB; median khoảng 618 MB), không phải số byte đã tải hay hash. `ffprobe` trên 11 URL mẫu phủ 9 khóa đọc H.264 640×360. Một file `.mov` PHYS 200 L1 trả `Range 206`; chưa thử giải mã toàn file ở 226 bài.

| Mẫu | MOV Yale đã kiểm | Kết quả |
|---|---|---|
| [PHYS 200 L1](https://oyc.yale.edu/physics/phys-200/lecture-1) | [MOV](https://openmedia.yale.edu/projects/courses/fall06/phys200/mov/phys200_01_090606.mov) | 640×360, H.264/AAC; 4400,901 s, khớp thời lượng mobile |
| [PHYS 201 L1](https://oyc.yale.edu/physics/phys-201/lecture-1) | [MOV](https://openmedia.yale.edu/projects/courses/spring10/phys201/mov/phys201_01_011110.mov) | 640×360, H.264/AAC; 3961,495 s |
| [ENGL 300 L10](https://oyc.yale.edu/english/engl-300/lecture-10) | [MOV](https://openmedia.yale.edu/projects/courses/spring09/engl300/mov/engl300_10_021209.mov) | 640×360, H.264/AAC; 3102,703 s |
| [PHYS 201 L24](https://oyc.yale.edu/physics/phys-201/lecture-24) | [M4V](https://openmedia.yale.edu/projects/courses/spring10/phys201/m4v/phys201_24_041910.m4v) / [MOV](https://openmedia.yale.edu/projects/courses/spring10/phys201/mov/phys201_24_041910.mov) | HEAD 200, range 206 cho M4V; MOV 640×360, 4458,825 s |
| [PHYS 201 L25](https://oyc.yale.edu/physics/phys-201/lecture-25) | [M4V](https://openmedia.yale.edu/projects/courses/spring10/phys201/m4v/phys201_25_042110.m4v) / [MOV](https://openmedia.yale.edu/projects/courses/spring10/phys201/mov/phys201_25_042110.mov) | HEAD 200, range 206 cho M4V; MOV 640×360, 3222,990 s |

MP3 trên trang L24/L25 có duration lệch video tương ứng khoảng 0,07–0,08 s; hỗ trợ nhận diện cùng buổi ghi, **không chứng minh** từng chapter boundary nằm đúng ±3 s. Một frame PHYS 200 L1 ở 1290 s từ MOV cho thấy lớp học và bảng không có chữ tại thời điểm đó; không thể dùng frame này để kết luận hiệu quả OCR.

## Quyền trang bài và chất lượng GT: phép đếm không chồng lặp

[Scan trang 226 dòng](./rq1-yale-260928-1937-page-credits-scan.csv), SHA-256 `4C86460D98C5BC2D1D04E56C6B13D7AE5CD638271D824B1ADE3417331E9B66E7` (ledger chỉ giữ cờ, không chép notice): 226/226 trang trả HTTP 200. Mười trang **ENGL 310 L2, L3, L5, L6, L15, L19, L21, L22, L24, L25** ghi rõ tác phẩm được dùng theo phép riêng và không thuộc CC; ví dụ [L2](https://oyc.yale.edu/english/engl-310/lecture-2), [L19](https://oyc.yale.edu/english/engl-310/lecture-19). Đặt 10 bài này `rights_hold` cho việc xử lý nguyên video tới khi xác định cơ sở quyền theo phạm vi sử dụng; không suy rằng 216 trang còn lại tự động sạch quyền. [Yale Terms](https://oyc.yale.edu/terms) chỉ cấp CC BY-NC-SA 3.0 cho phần lớn nội dung và loại nội dung bên thứ ba nếu Credits không nói khác; nghiên cứu phải đáp ứng phi thương mại, ghi công và kiểm từng thành phần dùng thực tế.

[ENGL 220 L1](https://oyc.yale.edu/english/engl-220/lecture-1) có chapter độ dài 0 tại 1443 s; [L18](https://oyc.yale.edu/english/engl-220/lecture-18) có 5 title nhưng 4 timestamp. Giữ hai bài `review_gt` tới khi có publisher correction hoặc quyết định loại trước D2. 38 bài có chapter cuối >20 phút sau khi thêm duration PHYS 201 L24: 1 bài là ENGL 220 L1 đã nằm trong `review_gt`, còn **37 bài** cần kiểm nội dung mốc cuối. Không tự coi chapter dài là sai. Ngoài 3 cửa sổ âm thanh kiểm ở [báo cáo trước](./rq1-yale-qualification-260928-1916-publisher-media-gt-rights-report.md), chưa có audit GT trực tiếp đủ mẫu và đủ timeline.

| Khóa | HD HEAD 200 | `rights_hold` công bố | `review_gt` cấu trúc | >20 phút đuôi GT | Không có cờ trong các phép quét này* |
|---|---:|---:|---:|---:|---:|
| ECON 159 | 24 | 0 | 0 | 4 | 20 |
| ECON 251 | 26 | 0 | 0 | 5 | 21 |
| ECON 252 (2008) | 26 | 0 | 0 | 2 | 24 |
| ENGL 220 | 24 | 0 | 2 | 8 | 15 |
| ENGL 291 | 26 | 0 | 0 | 1 | 25 |
| ENGL 300 | 26 | 0 | 0 | 0 | 26 |
| ENGL 310 | 25 | 10 | 0 | 4 | 11 |
| PHYS 200 | 24 | 0 | 0 | 3 | 21 |
| PHYS 201 | 25 | 0 | 0 | 11 | 14 |
| **Tổng** | **226** | **10** | **2** | **38** | **177** |

\* `177` chỉ là thứ tự ưu tiên để kiểm quyền video, mốc GT giải mã và OCR; không phải 177 eligible. Các cờ không chồng lặp ngoại trừ ENGL 220 L1 vừa `review_gt` vừa >20 phút.

## Khả năng split và quyết định

[Danh sách khóa Yale](https://oyc.yale.edu/courses) xác nhận 9 khóa này có 8 giảng viên: PHYS 200/201 đều Ramamurti Shankar; 7 khóa còn lại có giảng viên khác. Cả 9 khóa vẫn còn ít nhất 11 bài không có cờ trong các phép quét, nên **split course-disjoint hoặc instructor-disjoint có khả năng về mặt metadata**. Mọi bài vẫn cùng nhà xuất bản Yale; không gọi đó là độc lập giữa các nhà xuất bản. Chưa đánh giá số bài đạt quyền/GT/OCR thật, năng lực thống kê, trùng nội dung giữa khóa, hay D2, nên **không chốt số bài cuối cùng hoặc split ấn định**.

Hướng tiếp: lấy mẫu đa khóa được khai báo trước từ 177 bài ưu tiên; kiểm Credits và frame/content thực tế, đo chữ bảng/slide có đọc được trên MOV 640×360, đối chiếu nhiều boundary giải mã kể cả đuôi dài; ghi lý do loại từng bài. Sau đó mới xác định cohort, group theo giảng viên, amend [master RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md), hash file đầy đủ và freeze D2. **Không chạy official 04a/04b lúc này.**

## Câu hỏi chưa giải quyết

1. Từng file video được chọn có thành phần bên thứ ba nào ngoài mười thông báo trên trang, và mục đích sử dụng thực tế có đáp ứng BY-NC-SA/ngoại lệ không?
2. MOV 640×360 có đủ chất lượng hình/OCR cho các khóa ưu tiên không?
3. Bao nhiêu boundary đạt ±3 s sau kiểm giải mã có kiểm mẫu, gồm 37 đuôi GT dài?
4. Sau lọc quyền, GT, OCR và trùng nội dung, còn bao nhiêu course/instructor group thực sự đủ cho split và CI đã đăng ký trước?
