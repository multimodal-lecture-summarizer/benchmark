# RQ1 SSLectures: truy snapshot chapter gốc cho một video

**Kiểm:** 2026-09-29 14:40, Asia/Bangkok. Mục tiêu chính `zMlEb29UlKw` (Atomic and Optical Physics I, lecture 10, dòng 4 CSV); đối chiếu thêm `TgrNa_Guigs` (Laboratory Chemistry, lecture 11, dòng 740) vì kết quả tìm kiếm hiển thị mô tả từ kênh MIT OpenCourseWare. Chỉ tìm nguồn đã phát hành; không tạo/sửa mốc, không tải video, không truy cập YouTube bằng pipeline tự động. Kế thừa [ledger chín bài](./rq1-sslectures-260929-1431-nine-row-provenance-ledger.csv) và [receipt gói](./rq1-sslectures-260929-1431-nine-row-provenance-receipt.json).

## Kết quả

**Chưa tìm được snapshot chapter gốc hoặc quy trình thu thập đã phát hành nối đúng video ID với mốc/title trong CSV.** Không có cặp mốc/title nào được chứng nhận là `creator_provided`. Trạng thái 9/9 `gt_provenance_hold`, **0 GT official, 0 D2**. Đây là kết quả tìm trong các nguồn liệt kê dưới, không phải chứng minh rằng snapshot không tồn tại.

| Đối chiếu | `zMlEb29UlKw` | `TgrNa_Guigs` | Kết luận |
|---|---|---|---|
| Nhãn SSLectures | `0 Intro`, `230 Weak Field`, `771 Clicker Questions`, …; 19 cặp ở [Zenodo CSV](https://zenodo.org/records/10498680), dòng 4 | `0 Intro`, `27 The Catalase Lab`, `36 Catalase Lab`, `50 Catalase Is an Enzyme`, …; 33 cặp, dòng 740 | Bản ghi annotation có thật, hash đã khóa trong [receipt](./rq1-sslectures-260929-1431-nine-row-provenance-receipt.json). |
| ID và media publisher | [Trang MIT OCW](https://ocw.mit.edu/courses/8-421-atomic-and-optical-physics-i-spring-2014/resources/lecture-10-atoms-in-external-fields-ii/) nhúng đúng ID và liên kết MP4 | [Trang MIT OCW](https://ocw.mit.edu/courses/5-310-laboratory-chemistry-fall-2019/resources/lecture-11-catalase-part-1/) nhúng đúng ID và liên kết MP4 | Xác minh danh tính ở mức trang; không có timed TOC nguồn trên hai trang. |
| Mô tả video chính thức | Tìm kiếm theo ID + chapter title chỉ thấy transcript MIT OCW, không thấy timestamp/title list phát hành riêng | [Kết quả tìm kiếm video kênh MIT OpenCourseWare](https://www.youtube.com/watch?v=TgrNa_Guigs) hiển thị mô tả bài và giảng viên, **không có danh sách timestamp/title trong phần được trả về** | Mô tả qua chỉ mục tìm kiếm không phải snapshot đầy đủ/đã khóa; không dùng để khẳng định chapter creator đã có hoặc chưa từng có. |
| Tài liệu quy trình | [Zenodo record](https://zenodo.org/records/10498680) nói scrape dữ liệu; [abstract paper tác giả](https://link.springer.com/chapter/10.1007/978-981-97-9255-9_4) nói GPT-3.5 sinh summary, không nêu nguồn boundary/title | Cùng gói/phương pháp | Không xác định ai tạo mốc chapter và cách tạo. Paper toàn văn không có trong phần truy cập công khai đã kiểm. |
| Bản lưu/repository | Wayback CDX cho ID chính trả HTTP 503; Wayback availability trả 429 cho hai ID. GitHub public repository search `SSLectures` không thấy repo liên quan nhóm tác giả; Zenodo API không có `related_identifiers` | Không có snapshot kiểm được | Các lỗi 503/429 không chứng minh bản lưu không tồn tại. Không lấy transcript PDF làm chapter GT. |

## Kiểm cấu trúc với quy tắc chapter YouTube

[YouTube Help hiện hành](https://support.google.com/youtube/answer/9884579?hl=en) phân biệt chapter do người đăng nhập trong mô tả với chapter tự động; danh sách do người đăng cần mỗi chương dài ít nhất 10 giây. [Receipt khoảng cách](./rq1-sslectures-260929-1439-manual-chapter-gap-receipt.json) tính trực tiếp từ `true_chapters_start` của đúng chín dòng khóa trước: **9 cặp mốc liên tiếp cách dưới 10 giây trong 4/9 bài**. Ví dụ ID chính có `2888 Perturbation Theory` → `2892 Perturbation Operator` (4 giây); `TgrNa_Guigs` có `27 The Catalase Lab` → `36 Catalase Lab` (9 giây), và thêm bốn cặp ngắn khác.

Điều này **không tương thích với việc coi nguyên danh sách CSV là danh sách chapter thủ công hợp lệ theo quy tắc YouTube hiện hành**. Nó không xác định danh sách đến từ chapter tự động, từ nhóm SSLectures, hoặc từ một hệ thống publisher khác; cũng không chứng minh quy tắc YouTube ở thời điểm thu thập giống hiện nay. Không gắn `creator_provided` hoặc `auto_generated` dựa trên phép kiểm này.

## Quyết định và bước kế tiếp

Đường công khai đã kiểm đến nay chỉ chứng minh: file nhãn → ID nguồn → trang OCW/media link. Thiếu mắt xích **file/snapshot chapter nguồn hoặc protocol thu thập**. Không so mốc CSV với nội dung nói trong transcript để tự xác nhận GT; không dịch mốc sang timebase MP4; không chọn bài thay thế sau HOLD.

Yêu cầu cung cấp bằng chứng đã tồn tại từ maintainer/nhà phát hành, nếu được người dùng cho phép liên hệ, là bước hợp lý tiếp theo: hỏi chính chín ID, file/snapshot chứa mốc/title, nguồn manual/automatic/algorithmic, ngày lấy, mã thu thập/QC. Không yêu cầu họ tạo chapter mới. [Bản nháp câu hỏi](./rq1-sslectures-260929-1432-package-provenance-nine-row-report.md) đã chuẩn bị; **chưa gửi ra ngoài**.

## Câu hỏi chưa giải quyết

1. Có snapshot description, chapter metadata hoặc tài liệu quy trình thời điểm thu thập khớp nguyên mốc/title của ít nhất một ID không?
2. Nếu mốc được biến đổi khi tạo CSV, phép biến đổi nào và nguồn gốc mốc đầu vào là gì?
3. Có căn cứ để phân biệt nhãn do creator/publisher phát hành với chapter tự động hoặc nhãn do nhóm dataset tạo cho từng ID không?
