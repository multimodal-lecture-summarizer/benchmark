# RQ1: Open Yale GT publisher và file video do Yale cung cấp

**Kiểm:** 2026-09-28, Asia/Bangkok. Tiếp nối [so sánh nguồn](./rq1-dataset-research-260928-1902-preexisting-chapter-gt-candidates-report.md). Official RQ1 giữ GT có sẵn; [MITFLD 35](./rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md) chỉ pilot. Lượt này chỉ dùng request metadata/byte-range và ba clip audio 32–40 s từ file Yale; **không tải toàn video, không hash toàn file, không freeze D2, không chấm 04a/04b**.

**Cập nhật 19:37:** [follow-up HD/quyền/GT](./rq1-yale-followup-260928-1937-hd-media-rights-gt-split-report.md) tìm được MOV Yale 640×360 cho 226/226 đường suy ra, sửa hai link PHYS 201 404 bằng stem đúng, và phát hiện 10 bài ENGL 310 có thông báo nội dung không thuộc CC. Các con số truy cập và candidate sau đây là trạng thái tại lượt kiểm 19:16; dùng follow-up cho trạng thái mới nhất. Official eligible vẫn 0 đã xác nhận.

## Kết luận

**Đã xác minh đường video trực tiếp do Yale liên kết** cho sáu bài mẫu thuộc sáu khóa, cùng chapter starts do Yale công bố. Sáu file `.m4v` `HEAD 200`, `GET Range 206`, H.264/AAC giải mã được, mốc cuối nằm trong thời lượng file. Ba mốc thuộc ba khóa có lời nói giải mã phù hợp với tên/chữ transcript chapter gần thời điểm publisher ghi. Sàng lọc mở rộng 226 vị trí bài trên 9 khóa tìm được 224 link MP4 đọc được metadata, đồng thời lộ hai link 404 và hai lỗi GT rõ. **Chưa có bài nào đủ toàn bộ quyền thành phần, chất lượng GT trên cả timeline, hash file và D2**, nên official eligible vẫn **0 confirmed**.

## Bằng chứng theo đúng bài

Trang chapter được dẫn trong cột GT; link media lấy từ danh mục [Open Yale mobile media](https://openmedia.yale.edu/projects/iphone/departments/phys/phys200.html) cùng tên khóa/bài, đổi `http` sang `https` và kiểm đáp ứng thực tế. `0` là đầu video, không tính internal boundary. Thời lượng từ MP4 `mvhd` ở byte-range đầu, được `ffprobe` xác nhận sai khác dưới 0,02 s; đây **không phải** kiểm đồng bộ nội dung toàn file.

| Khóa / bài | GT Yale (s) | File Yale trực tiếp | HEAD / range / codec | Thời lượng file; phần sau mốc cuối |
|---|---|---|---|---|
| [PHYS 200 L1](https://oyc.yale.edu/physics/phys-200/lecture-1) | `0,1285,1700,2276,3157,4122` | [M4V](https://openmedia.yale.edu/projects/courses/fall06/phys200/iphone/phys200_01_090606.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/phys/phys200.html) | 200 / 206; H.264+AAC, 320×180 | 4400,901 s; 278,901 s |
| [PHYS 201 L1](https://oyc.yale.edu/physics/phys-201/lecture-1) | `0,921,1271,1576,2001` | [M4V](https://openmedia.yale.edu/projects/courses/spring10/phys201/m4v/phys201_01_011110.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/phys/phys201.html) | 200 / 206; H.264+AAC, 320×180 | 3961,495 s; **1960,495 s** (review chapter cuối) |
| [ENGL 300 L10](https://oyc.yale.edu/english/engl-300/lecture-10) | `0,393,565,1020,1359,1693,2022,2554` | [M4V](https://openmedia.yale.edu/projects/courses/spring09/engl300/iphone/engl300_10_021209.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/engl/engl300.html) | 200 / 206; H.264+AAC, 320×180 | 3102,700 s; 548,700 s |
| [ENGL 310 L17](https://oyc.yale.edu/english/engl-310/lecture-17) | `0,420,1703,2158` | [M4V](https://openmedia.yale.edu/projects/courses/spring07/engl310/iphone/engl310_17_040207.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/engl/engl310.html) | 200 / 206; H.264+AAC, 320×180 | 2606,173 s; 448,173 s |
| [ENGL 220 L6](https://oyc.yale.edu/english/engl-220/lecture-6) | `0,424,1604,2007` | [M4V](https://openmedia.yale.edu/projects/courses/fall07/engl220/iphone/engl220_06_092407.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/engl/engl220.html) | 200 / 206; H.264+AAC, 320×180 | 3111,278 s; **1104,278 s** (review chapter cuối) |
| [ENGL 291 L1](https://oyc.yale.edu/english/engl-291/lecture-1) | `0,487,823,1771,2638` | [M4V](https://openmedia.yale.edu/projects/courses/spring08/engl291/iphone/engl291_01_011408.m4v) qua [index](https://openmedia.yale.edu/projects/iphone/departments/engl/engl291.html) | 200 / 206; H.264+AAC, 320×180 | 2855,322 s; 217,322 s |

Sáu bài không đủ chứng minh chất lượng toàn bộ khóa. PHYS 200 và 201 cùng giảng viên; khi xét source independence nên giữ chúng trong cùng group hoặc kiểm rủi ro phụ thuộc, không dùng chúng làm hai mẫu độc lập một cách máy móc. ENGL 300/310/220/291 thuộc bốn khóa/giảng viên khác nhau nhưng nội dung văn học có thể có thành phần bên thứ ba.

### Kiểm nội dung tại ba boundary

Trích 32–40 s audio bằng FFmpeg từ URL Yale, chạy Faster-Whisper `tiny.en` offline; so với tiêu đề và đoạn đầu chapter trong transcript publisher. Đây là **kiểm chủ đề cục bộ**, ASR nhỏ và cắt cửa sổ không phải phép đo sai số GT chuẩn hóa.

| Bài / publisher start | Chỉ dấu nội dung trên file Yale | Đánh giá |
|---|---|---|
| PHYS 200 L1 / 1285 s | Lời chuyển “Let's start now” bắt đầu khoảng 1283,8 s; “Newtonian mechanics” khoảng 1287 s, đúng [Chapter 2](https://oyc.yale.edu/physics/phys-200/lecture-1). | Phù hợp cục bộ khoảng ±3 s. |
| ENGL 300 L10 / 393 s | Sau lời kết đoạn trước, lời mở về Derrida xuất hiện trong segment ASR 388,62–395,28 s, đúng [Chapter 2](https://oyc.yale.edu/english/engl-300/lecture-10). | Phù hợp chủ đề; chưa định được onset từ ASR segment đủ chính xác để khẳng định F1@3s. |
| ENGL 310 L17 / 420 s | Lời bắt đầu xét bài thơ “A Grave” ở khoảng 420,64 s, đúng [Chapter 2](https://oyc.yale.edu/english/engl-310/lecture-17). | Phù hợp cục bộ khoảng ±3 s. |

Một khung PHYS 200 quanh 1290 s đã giải mã: lớp học/chalkboard nhìn thấy, chữ bảng không đủ rõ ở 320×180. **OCR và caption chi tiết có nguy cơ chất lượng thấp** trên bản mobile này; cần đo đọc chữ/OCR trên một mẫu định trước hoặc tìm bản publisher độ phân giải cao trước khi khóa visual RQ1. FFprobe báo `Referenced QT chapter track not found` nhưng đọc được H.264/AAC và duration; mốc GT lấy từ trang Yale, không dựa vào track QT đó.

## Sàng lọc metadata mở rộng: 9 khóa, 226 vị trí bài

**Bổ sung cùng ngày.** [Ledger 226 dòng](./rq1-yale-260928-1916-nine-course-metadata-ledger.csv), SHA-256 `2E41667D311EAD604D2CCBEF191E672C1489DAA4F68CA2202CCA2F0836B8FE64`. Mỗi dòng ghép số bài trên trang GT `oyc.yale.edu` với link video cùng số bài trong *index mobile của Yale*; đọc GT HTML, kiểm `GET Range: bytes=0-65535` và duration MP4 `mvhd` trong phần trả về. Đây là sàng lọc metadata, **không xác thực trọn file, nội dung toàn timeline hay quyền từng bài**. `media_bytes` là kích thước khai báo bởi HTTP, không phải số byte đã tải.

| Khóa | Vị trí bài | File trả 206 + đọc được duration | Internal boundaries | Đuôi sau GT cuối >20 phút, cần review |
|---|---:|---:|---:|---:|
| ECON 159 | 24 | 24 | 94 | 4 |
| ECON 251 | 26 | 26 | 114 | 5 |
| ECON 252 (2008) | 26 | 26 | 138 | 2 |
| ENGL 220 | 24 | 24 | 74 | 8 |
| ENGL 291 | 26 | 26 | 103 | 1 |
| ENGL 300 | 26 | 26 | 142 | 0 |
| ENGL 310 | 25 | 25 | 97 | 4 |
| PHYS 200 | 24 | 24 | 121 | 3 |
| PHYS 201 | 25 | 23 | 72 | 10 |
| **Tổng** | **226** | **224** | **955** | **37** |

GT HTML đọc được ở 226/226 vị trí; 224/226 link video trả `206 video/mp4` và có duration trong 64 KiB đầu. **PHYS 201 L24–L25**: link `.m4v` do [index Yale](https://openmedia.yale.edu/projects/iphone/departments/phys/phys201.html) cung cấp hiện trả `404`; trang [L24](https://oyc.yale.edu/physics/phys-201/lecture-24) vẫn có chapter GT. Hai dòng này là `blocked_access` theo đường file đang xét; không suy ra video không tồn tại ở nguồn khác. Ledger dùng cờ `mvhd_not_in_first_64k` cho hai response lỗi HTML vì không có MP4 để đọc; nguyên nhân thực tế là `404`, không phải bằng chứng MP4 đặt `mvhd` muộn.

Hai bất thường GT rõ trên chính trang publisher: [ENGL 220 L1](https://oyc.yale.edu/english/engl-220/lecture-1) có hai chapter liên tiếp cùng start `1443 s`, tạo chapter độ dài 0; [ENGL 220 L18](https://oyc.yale.edu/english/engl-220/lecture-18) có 5 tiêu đề nhưng chỉ 4 timestamp, không thể gán đủ boundary theo cách hiện tại. Giữ cả hai dưới `review_gt`, không tự sửa GT. 37 đuôi >20 phút chỉ là cờ rà soát; **chưa kết luận lỗi** vì chapter cuối dài vẫn có thể đúng. Những số này là trần candidate metadata, không phải số bài eligible cho official.

## Quyền và điều kiện D2 còn thiếu

[Yale Terms](https://oyc.yale.edu/terms) cấp CC BY-NC-SA 3.0 cho **phần lớn** bài giảng/tài liệu, giới hạn dùng phi thương mại và yêu cầu ghi công; Yale nêu rõ không nhất thiết sở hữu từng thành phần, nội dung bên thứ ba không nằm trong CC trừ khi phần Credits ghi khác. [Yale Help](https://oyc.yale.edu/help) mô tả tải video `.mov` trên session page, nhưng **sáu trang bài hiện kiểm chỉ lộ YouTube embed và MP3**, còn `.m4v` ở danh mục mobile Yale cũ vẫn trả 200. Sự tồn tại đường tải Yale trực tiếp chứng minh quyền truy cập kỹ thuật; **chưa xác nhận ngoại lệ/clearance của toàn nội dung từng file** hoặc dùng file đó dưới mọi điều kiện benchmark. Không lấy file YouTube bằng downloader để thay bản Yale.

Điều kiện trước official D2: (1) chốt mục đích phi thương mại và nghĩa vụ ghi công; (2) kiểm Credits + nội dung của từng video chọn, loại/giữ đúng lý do; (3) hash toàn file và giải mã/mốc trên đúng bản sẽ dùng; (4) kiểm chất lượng visual/OCR của 320×180 hoặc chọn bản Yale tốt hơn; (5) lập cohort nhiều khóa, kiểm trùng video/talk và rủi ro cùng giảng viên, khóa split trước scoring; (6) sửa [master protocol](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) bằng amendment có ngày vì thay nguồn YTSeg chính; chạy D0/D1/00c-D2 và niêm phong final_test. Sáu bài hiện là **candidate metadata**, chưa phải train/validation/test official.

## Câu hỏi chưa giải quyết

1. Các file mobile 320×180 có đủ thông tin visual/OCR cho hypothesis RQ1, hay Yale còn bản video publisher độ phân giải cao có đường tải hiện hành?
2. Sau kiểm Credits, nội dung bên thứ ba và quyền dùng dự kiến, bao nhiêu bài/khóa còn eligible?
3. Mốc chapter có đạt sai số ±3 s trên một mẫu ngẫu nhiên nhiều khóa, đặc biệt các bài có chapter cuối dài bất thường?
4. Sau lọc/nhóm phụ thuộc, còn đủ khóa độc lập cho split D2 và thống kê theo course không?
5. PHYS 201 L24–L25 có đường file Yale khác còn truy cập được không, và hai bài ENGL 220 bất thường có bản publisher correction không?
