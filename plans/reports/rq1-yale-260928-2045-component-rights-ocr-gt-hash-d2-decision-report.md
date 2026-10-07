# RQ1 Yale: quyền thành phần, OCR, GT trên MOV và quyết định D2

**Kiểm:** 2026-09-28, Asia/Bangkok. **Mẫu cố định:** [9 bài từ 9 khóa](./rq1-yale-260928-1952-nine-course-qa-sample.csv), 8 nhóm giảng viên. Chapter GT là mốc/tiêu đề Yale có sẵn; không tạo hoặc sửa GT. MITFLD 35 vẫn là pilot chẩn đoán. Phạm vi người dùng chốt: xử lý video nội bộ, chỉ công bố số liệu/biểu đồ; không phát hành video, frame, clip, ASR, caption hay dữ liệu trích xuất.

## Quyết định

**Chưa thể khóa Yale thành D2 `eligible` cho official RQ1.** [Phiếu quyết định](./rq1-yale-260928-2045-d2-blocked-decision.json) ghi `blocked_decision`, `scientific_selection_eligible=false`, **0 unit official**. Không chạy official 04a/04b và không tính 9 bài mẫu hay 177 dòng sàng lọc là eligible. Quyết định này giữ nguyên danh sách mẫu và hash hồ sơ để có thể tiếp tục kiểm, không thay master plan hoặc official GT.

| Cổng | Bằng chứng hiện có | Trạng thái |
|---|---|---|
| Quyền toàn MOV theo dùng nội bộ | 3 bài có đoạn trích/hình cần cơ sở quyền; 2 bài cần truy nguồn biểu đồ; 4 bài ít tín hiệu hơn nhưng chưa kiểm toàn media. | **0/9 `rights_pass`** |
| Giải mã và visual | 45/45 frame cố định giải mã 640×360; chỉ 1 frame có slide chữ được OCR đọc rõ khi so bằng mắt. | Giải mã mẫu đạt; **OCR chưa đạt ngưỡng chất lượng xác định** |
| Chapter GT trên media | 9/9 mốc đầu có audio 36 s; 4/18 mốc giữa/cuối có audio đủ hai phía, 14 chưa đánh giá; không mốc nào được xác minh ±3 s. | **0/9 `gt_pass`** |
| SHA-256 media đầy đủ | Range request ECON 159 L2 trả `206` và khai báo 601,595,188 byte; tải toàn file không hoàn tất. | **0/9 full MOV SHA-256** |
| Split và protocol | Có 9 khóa nhưng chỉ 8 nhóm giảng viên; chưa có cohort vượt các cổng, split course/instructor-disjoint, GT freeze hoặc amendment từ nguồn YTSeg trong master plan. | **Chưa khóa D2** |

## Quyền thành phần trong phạm vi chỉ công bố số liệu

[Yale Terms](https://oyc.yale.edu/terms) nói *phần lớn* bài giảng thuộc CC BY-NC-SA và loại thành phần bên thứ ba khỏi giấy phép mặc định trừ khi Credits quy định khác; trang cũng yêu cầu mục đích phi thương mại và ghi công. Sử dụng nội bộ, chỉ xuất số liệu giảm phạm vi phân phối nhưng không tự chứng minh quyền đối với từng thành phần. Yale nêu có thể dựa vào giấy phép riêng hoặc fair use của họ mà không chuyển cơ sở đó cho người dùng. Việc áp dụng fair use phụ thuộc tình huống; [U.S. Copyright Office](https://www.copyright.gov/fair-use/) không xem đây là kết luận tự động. Đây là phân loại nghiên cứu cho cổng dữ liệu, không phải kết luận pháp lý về vi phạm.

[Ledger 9 bài](./rq1-yale-260928-2025-component-rights-internal-use-ledger.csv), SHA-256 `D4EBBF3023BD8DD5C20D3D9AB9BD4F2D8DC1370728E2DF58FC0CD0EBA795707C`:

- `rights_hold` 3: [ENGL 291 L10](https://oyc.yale.edu/english/engl-291/lecture-10) có đọc tác phẩm văn học hiện đại; [ENGL 300 L16](https://oyc.yale.edu/english/engl-300/lecture-16) và [handout](https://oyc.yale.edu/sites/default/files/jaussbakhtin_0.pdf) có trích lý thuyết hiện đại; [ENGL 310 L4](https://oyc.yale.edu/english/engl-310/lecture-4) và [handout](https://oyc.yale.edu/sites/default/files/handout4_0.pdf) có thơ và hình từ nguồn ngoài.
- `visual_source_review` 2: [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1) nhắc biểu đồ thị trường/nhà ở; [ECON 252 (2008) L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6) có biểu đồ cổ phiếu trong [slide Yale](https://oyc.yale.edu/sites/default/files/Lecture06_0.pdf). Chưa khẳng định biểu đồ hiện trong MOV hoặc xác định tác giả nguồn.
- `full_mov_rights_unverified` 4: ECON 159 L2, ENGL 220 L23, PHYS 200 L19, PHYS 201 L10. Trang kiểm không hiện ngoại lệ cụ thể, nhưng chưa rà toàn bộ MOV và tài liệu kèm theo. Không nâng trạng thái thành `rights_pass` từ sự im lặng của Credits.

## Chất lượng visual và mốc GT

[Báo cáo OCR](./researcher-260928-2013-yale-nine-course-ocr-feasibility-report.md) và [ledger 45 frame](./rq1-yale-260928-2013-ocr-frame-metrics.csv), SHA-256 `D7078EAA489F61564B9A09282BBAD58DC4EE04B1CF5FCAD610C17437AAB96C9D`: lấy 10/30/50/70/90% thời lượng mỗi bài, 45/45 frame decode; 41/45 có ít nhất một kết quả OCR, 7/45 vượt proxy ba dòng confidence cao. So bằng mắt, chỉ frame ECON 251 L1 ở 70% rõ ràng có slide chữ được OCR đọc tốt. Watermark, số trục và công thức/chữ phấn sai khiến confidence không phải độ chính xác. Chưa có bản chép tham chiếu, do đó **không có CER** và chưa chốt ngưỡng OCR cho official cohort. Không ngoại suy tỷ lệ 1/45 cho 226 bài.

[Kiểm GT mốc đầu](./rq1-yale-260928-1952-nine-course-boundary-audio-qa.csv): 9/9 clip 36 s giải mã; 5 mốc có chuyển chủ đề cục bộ, 2 chỉ phù hợp chủ đề rộng, 2 chưa xác định. [Kiểm mốc giữa/cuối](./researcher-260928-2025-yale-multi-boundary-decoded-media-gt-audit-report.md) dùng 18 mốc Yale chọn trước, nhưng chỉ [4/18 cửa sổ](./rq1-yale-260928-2025-multi-boundary-decoded-media-gt-audit.csv) có audio hai phía mốc (3 clip 48 s; 1 clip 40.347 s); 3/4 gợi chuyển chủ đề trong clip, 1/4 chủ đề rộng. Ledger giữa/cuối SHA-256 `9FD4C2D449EEEF6FC025DEE193E5BB98D217B7DCDC07766FA7756C20113B29FE`. ASR `tiny.en` và remote seek không xác nhận onset ±3 s hoặc PTS nguồn; 14 mốc thiếu không được tính là đạt hay không đạt GT. **0 mốc được xác minh ±3 s, 0 bài `gt_pass`.** Không lấy caption MOV chưa chuẩn hóa PTS làm GT thay thế.

## Hash file và giới hạn truy cập

Thử SHA-256 của toàn bộ MOV ECON 159 L2 (`econ159_02_091007.mov`, 601,595,188 byte theo HTTP range) bằng tải byte range vào thư mục tạm. Các request đầu trả `206`/`Content-Range`, nhưng sau đó luồng tải lớn không hoàn tất trong thời gian kiểm; thử 8 phần đồng thời cũng không tạo được phần hoàn chỉnh. Đã dừng tác vụ và xóa thư mục tạm. **Không có SHA-256 của media đầy đủ**, không lấy `Content-Length`, ETag, URL hoặc hash clip làm thay thế. Hash của manifest mẫu là `5A5963776FB754A01C7968492C3FD5712C70F1F185E1E8B26625EA012C63853D`; hash các ledger và phiếu quyết định chỉ cố định hồ sơ kiểm, không xác minh byte video.

Toàn bộ 226 URL MOV được sàng lọc trước có tổng kích thước khai báo khoảng 136.34 GiB, vượt trần peak 50 GiB trong D2 contract nếu thu tất cả cùng lúc. Tập 9 mẫu khoảng vài GiB nhưng quyền/GT/hash vẫn chưa đủ. Cần chốt cohort nhỏ đã qua quyền trước khi thu và hash đầy đủ từng file; chỉ khi đó mới kiểm PTS, toàn timeline, trùng lặp và split độc lập. Không thay bài sau khi xem kết quả mô hình. [Master plan RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) phải được amendment trước khi dùng Yale làm nguồn official thay YTSeg.

## Câu hỏi chưa giải quyết

1. Trong các bài ít cờ quyền, quyền cụ thể nào bao phủ toàn MOV và các thành phần bên thứ ba khi xử lý nội bộ phi thương mại, chỉ công bố số liệu?
2. Cohort nào đạt ngưỡng visual/OCR đã định trước, và cần bản chép tham chiếu bao nhiêu frame để đo CER?
3. Khi lấy được file đầy đủ, mốc chapter Yale lệch bao nhiêu so với onset được rà độc lập trên PTS nguồn, kể cả mốc giữa/cuối và đoạn đuôi dài?
4. Sau các cổng quyền, GT, hash, trùng lặp và giới hạn D2, còn bao nhiêu bài/nhóm giảng viên đủ để khóa split course-disjoint có sức thống kê?
