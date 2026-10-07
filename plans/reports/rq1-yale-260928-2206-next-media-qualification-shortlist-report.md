# RQ1 Yale: kiểm chéo GT ECON 159 và thứ tự tải MOV tiếp

**Kiểm:** 2026-09-28, khoảng 22:00–22:06 Asia/Bangkok. **Mục đích:** chọn ít file nhất để quyết định liệu Yale có đáng theo đuổi cho official RQ1 đa phương thức. Đây là **pilot đánh giá nguồn** trên [mẫu 9 bài đã cố định](./rq1-yale-260928-1952-nine-course-qa-sample.csv), không phải chọn unit official theo kết quả OCR/GT. Chỉ xử lý media nội bộ; báo cáo số liệu, không phát hành media hoặc nội dung trích xuất.

## ECON 159 L2: bằng chứng mới

[MOV local đã hash và giải mã](./rq1-yale-260928-2157-econ159-l2-local-mov-d2-gates-report.md) có SHA-256 `A25DBE7B4DE66F7978C6C503DA1B20548D301C116A9D4B9FD6224D7889113EDF`. Chạy thêm mô hình offline `base.en` trên cùng bốn cửa sổ audio local: onset chủ đề ước lượng lệch [mốc Yale](https://oyc.yale.edu/economics/econ-159/lecture-2) `+0,32 / +0,02 / +0,74 / +0,04 s`, so với `tiny.en` `+0,58 / +0,42 / +0,78 / +0,18 s`. Cả hai đồng ý về chuyển chủ đề cục bộ, nhưng không thay rà onset độc lập. **Một bài đã có full-file hash; `gt_pass` official và `rights_pass` vẫn chưa gán.**

## Thứ tự tải đề xuất

Các link dưới đây là MOV nguyên file từ host Yale. HEAD được kiểm lại ngày 2026-09-28: cả ba trả `200 video/quicktime` và kích thước trong bảng. Quyền chung theo [Yale Terms](https://oyc.yale.edu/terms) áp dụng cho phần lớn nội dung nhưng không tự bao phủ thành phần bên thứ ba. Không xem `HEAD 200` hay trang không có Credits là quyền toàn file.

| Ưu tiên | Bài và lý do | MOV, kích thước | Rủi ro còn lại |
|---|---|---|---|
| **1 — tải tiếp** | [PHYS 200 L19](https://oyc.yale.edu/physics/phys-200/lecture-19): giảng viên khác ECON 159; 7 chapter, mốc đầu remote có chuyển chủ đề; hình bảng/công thức giúp thử visual khác loại ECON 159. | [MOV Yale](https://openmedia.yale.edu/projects/courses/fall06/phys200/mov/phys200_19_111306.mov), **639.913.047 byte (~610 MiB)**. | Chưa rà toàn video và thành phần quyền; OCR công thức/chữ nhỏ trên mẫu chưa đáng tin. |
| **2 — probe visual có điều kiện** | [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1): giảng viên thứ ba; trong 45 frame mẫu, chỉ bài này có một slide chữ OCR đọc rõ. Tải đầy đủ để xác định coverage slide và nguồn biểu đồ, đồng thời kiểm 6 mốc chapter. | [MOV Yale](https://openmedia.yale.edu/projects/courses/fall09/econ251/mov/econ251_01_090309.mov), **939.375.786 byte (~896 MiB)**. | Transcript có biểu đồ thị trường/Case-Shiller; phải xác minh nguồn và sự hiện diện trong MOV. Mốc đầu remote mới khớp chủ đề rộng. Giữ `visual_source_review`, không gọi rights-pass. |
| **Dự phòng, chưa cần tải** | [ENGL 220 L23](https://oyc.yale.edu/english/engl-220/lecture-23): giảng viên thứ tư, không có cờ quyền cụ thể trên trang mẫu và mốc đầu remote hợp chủ đề. | [MOV Yale](https://openmedia.yale.edu/projects/courses/fall07/engl220/mov/engl220_23_120307.mov), **386.792.955 byte (~369 MiB)**. | Khung hình mẫu phần lớn là giảng viên/bảng trống, nên ít giá trị cho phép thử OCR ngay. Vẫn cần quyền toàn media và GT. |

Không ưu tiên PHYS 201 L10 ngay: cùng giảng viên Ramamurti Shankar với PHYS 200, thêm ~842 MiB mà không tạo nhóm giảng viên độc lập mới. ECON 252 (2008) L6 cũng có biểu đồ cần truy nguồn và OCR mẫu chủ yếu là số trục. ENGL 291/300/310 hiện giữ `rights_hold` do đoạn trích/hình đã nhận diện. Các trạng thái dựa vào [ledger quyền 9 bài](./rq1-yale-260928-2025-component-rights-internal-use-ledger.csv) và [kiểm OCR 45 frame](./researcher-260928-2013-yale-nine-course-ocr-feasibility-report.md); không suy ra số unit eligible trên toàn 226 bài.

## Chính sách qualification trước D2

Master plan RQ1 hỏi liệu transcript + acoustic + visual/OCR có cải thiện chaptering so với transcript-only, dùng F1 collar ±3 s chính. Nó **không định nghĩa ngưỡng CER tối thiểu cho mỗi file**. Vì vậy OCR yếu ở ECON 159 là bằng chứng về giới hạn modality, **không tự động là lý do loại file**. Trước official cần chốt cách biểu diễn OCR vắng/yếu, coverage, quality strata và attrition **trước khi xem điểm mô hình**; nếu lọc bài theo OCR pilot mà không đăng ký trước sẽ thiên lệch kết quả. Tương tự, các file tải tiếp là source-feasibility probes; cohort official và split theo course/instructor phải được chọn bằng luật độc lập rồi mới đóng D2.

Khi hai file ưu tiên có ở máy, kiểm theo cùng hợp đồng: SHA-256 toàn byte, HEAD/metadata, full audio+video decode, PTS, chapter GT đầu/giữa/cuối và các mốc khó, sample visual/OCR, quyền thành phần; không lưu media/ASR/frame vào repository. Chỉ cân nhắc amendment Yale thay YTSeg trong [master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) khi đủ nhiều nhóm qua quyền, GT và khả năng split. [D2 hiện tại](./rq1-yale-260928-2045-d2-blocked-decision.json) vẫn `blocked_decision`, 0 unit official.

## Câu hỏi chưa giải quyết

1. PHYS 200 có đủ visual hữu ích và không có thành phần bên thứ ba ngắn mà mẫu remote chưa thấy không?
2. Ai sở hữu biểu đồ xuất hiện thực tế trong ECON 251, và cơ sở nào cho phép xử lý nội bộ phi thương mại để chỉ công bố số liệu?
3. Ngưỡng coverage/quality OCR và quy trình rà onset GT độc lập nào sẽ được đăng ký trước khi chọn cohort official?
4. Sau lọc toàn bộ nguồn, có đủ khóa và giảng viên để chia split và thống kê RQ1 không?
