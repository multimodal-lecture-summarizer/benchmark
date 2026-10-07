# RQ1 Yale: quyền biểu đồ, nguồn GT công bố, split theo giảng viên

Ngày kiểm: 2026-09-29. Phạm vi sử dụng do chủ dự án xác nhận: xử lý MOV nội bộ, chỉ công bố số liệu và biểu đồ tổng hợp; không phát hành video, frame, clip, slide hoặc văn bản OCR. Đây là qualification; **chưa khóa D2, chưa chạy official RQ1**. Quy tắc official GT vẫn là nhãn chương có sẵn từ nguồn độc lập; cohort MITFLD 35 giữ vai trò pilot.

**Điều chỉnh theo yêu cầu người dùng:** không tạo chapter GT, không đề xuất mốc thay thế và không yêu cầu người gán nhãn. [Handoff hiện hành](./rq1-readiness-260929-1013-official-gt-d2-handoff-report.md) dùng duy nhất mốc do Yale phát hành.

## 1. Quyền của các thành phần biểu đồ

[Điều khoản Yale](https://oyc.yale.edu/terms) §§3–6 và [trợ giúp của Yale](https://oyc.yale.edu/help) nói phần lớn bài giảng/nội dung do Yale tạo thuộc CC BY-NC-SA 3.0, nhưng tài liệu bên thứ ba trong bài giảng không tự động thuộc giấy phép này nếu Credits không nói rõ. Yale có thể dựa vào cho phép riêng hoặc fair use khi đăng bài; quyền đó không mặc nhiên chuyển cho nghiên cứu này. Cả [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1) và [ECON 252 (2008) L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6) hiện không có Credits riêng chỉ rõ quyền các biểu đồ đã rà. Nội bộ và chỉ xuất số liệu tổng hợp giảm phạm vi tái sử dụng, nhưng không chứng minh quyền nguồn biểu đồ.

| Video, vị trí MOV đã xem mẫu | Thành phần | Chứng cứ và kết luận cho xử lý nội bộ |
|---|---|---|
| ECON 251, ~13:00–17:30 | Excel/chart Dow, log/returns, S&P | Giảng viên nói về hai chỉ số trong [transcript Yale](https://oyc.yale.edu/economics/econ-251/lecture-1). Không thấy nguồn người vẽ biểu đồ và điều kiện dữ liệu. **Chưa rõ**. |
| ECON 251, ~19:00–20:30 | Case–Shiller National Home Price Index và đồ thị nhà ở/đòn bẩy | Transcript nêu tên Shiller; ghi công tên chỉ số chưa giải quyết quyền của hình đồ thị cụ thể. **Chưa rõ**. |
| ECON 251, ~25:00 | Đồ thị chỉ số subprime | Transcript mô tả chỉ số; nguồn hình và dữ liệu chưa xác định. **Chưa rõ**. |
| ECON 252, ~48:00–56:00 | Đồ thị chứng khoán so với random walk/AR(1) | Hình khớp [slide Yale do Robert Shiller đứng tên, tr. 4–5](https://oyc.yale.edu/sites/default/files/Lecture06_0.pdf); transcript mô tả mô phỏng bằng Excel. **Có căn cứ cho phần đồ họa do giảng viên tạo, nhưng chưa thông qua toàn bộ** vì nguồn chuỗi giá chứng khoán chưa rõ. |
| ECON 252, ~60:00 | Workbook lịch sử giá/cổ tức/lợi nhuận/CPI từ 1871 | [Transcript Yale](https://oyc.yale.edu/economics/econ-252-08/lecture-6) và [trang dữ liệu của Shiller](https://www.econ.yale.edu/~shiller/data.htm) nhận diện bộ sưu tập; thành phần chỉ số S&P/CPI và điều kiện dữ liệu chưa xác minh. **Chưa rõ**. |

**Quyết định quyền:** giữ `visual_source_review` / **HOLD** cho cả hai MOV; không nâng lên rights-pass hay đưa vào D2. Việc xem frame mới là lấy mẫu, chưa rà toàn bộ timeline. Cần định danh nguồn và điều kiện dùng nội bộ của mỗi biểu đồ, hoặc quyết định phạm vi phân tích không đụng đến thành phần còn nghi vấn và chứng minh cách loại trừ đó thực sự được áp dụng. Không xuất frame/slide/OCR trong artifact công bố.

## 2. GT chương do Yale phát hành

[ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1) công bố sáu mốc nội bộ `616;1074;2027;2773;3013;3502` giây; [ECON 252 (2008) L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6) công bố năm mốc `388;1200;2504;3090;3419` giây. Đây là `publisher_timed_toc` có sẵn, đúng loại nguồn GT mà [dataset contract](../../multimodal-lecture-summarizer/experiments/evaluation/dataset_contracts.py) chấp nhận. [Receipt cấu trúc sáu MOV](./rq1-yale-260929-publisher-gt-mov-structural-audit.md) xác nhận số mốc/tiêu đề, hash file, thứ tự và phạm vi thời lượng; không xác nhận nghĩa/onset của chương. Không có mốc, tiêu đề hoặc nhãn nào do dự án tạo mới được dùng làm GT.

Đợt trước có tạo các mốc ứng viên bằng AI để so nghĩa; **toàn bộ phần đó đã rút khỏi tài liệu và không được dùng để chọn bài, sửa GT hoặc tính metric**. Các phép cấu trúc vừa hoàn tất không chứng minh độ chính xác ngữ nghĩa ±3 giây; phải báo giới hạn đó khi dùng publisher GT nguyên trạng. [Snapshot nguồn](./rq1-yale-260929-1111-source-gt-snapshot-receipt.json) đã cố định 34 cặp tiêu đề/mốc do Yale đăng ở sáu trang ngày 2026-09-29, cùng ETag, Last-Modified và hash HTML. Không yêu cầu người kiểm độc lập và không tạo nhãn thay thế.

**Kiểm Credits trên nguồn:** ngày 2026-09-29, cả sáu trang lecture có 0 heading/link ghi `Credits` trong HTML công khai. [Terms §4](https://oyc.yale.edu/terms) và [Help §2](https://oyc.yale.edu/help) nói nội dung bên thứ ba không được CC của Yale bao phủ nếu Credits không nói rõ. Do vậy không thể suy từ giấy phép chung của bài giảng rằng mọi biểu đồ/hình/tài liệu trong MOV đều đã được cấp quyền cho dự án. Đây là kiểm tra trang nguồn, không phải nhận diện hay gắn nhãn thành phần video. Trạng thái quyền của sáu MOV không đổi.

## 3. Split theo giảng viên và sức mạnh bằng chứng

Ledger qualification hiện có [9 bài / 9 khóa](./rq1-yale-260928-1952-nine-course-qa-sample.csv), tổng **9.023 giờ**, thuộc **8 giảng viên** vì PHYS 200 và PHYS 201 cùng Ramamurti Shankar. [Batch manifest](./rq1-yale-260929-0843-qualification-batch-manifest.csv) ghi **6 MOV đã có** thuộc **5 giảng viên**, tổng **6.633 giờ / 3.776 GiB**. Ba bài ENGL 291/300/310 đang rights-hold, chưa tải; hai bài ECON nói trên còn visual-source hold. Đây là số lượng file, không phải số unit đủ điều kiện chính thức.

| Kịch bản | Video / giảng viên khả dụng tối đa | Split instructor-disjoint minh họa train / validation / final_test | Đánh giá |
|---|---:|---|---|
| Chỉ xét 4 MOV còn lại nếu hai ECON hold | 4 / 3 | 1 giảng viên mỗi split; PHYS 200+201 phải cùng split | Không có lặp lại giảng viên ở tập đánh giá; quyền/GT 4 MOV vẫn chưa pass. |
| Cả 6 MOV đã tải đều qua mọi gate | 6 / 5 | 3 / 1 / 1 giảng viên (4 / 1 / 1 video nếu PHYS ở train) | Tách được về mặt cấu trúc, nhưng validation và test mỗi tập chỉ 1 giảng viên/1 bài. |
| Cả 9 bài mẫu đều qua mọi gate | 9 / 8 | 4 / 2 / 2 giảng viên (5 / 2 / 2 video nếu PHYS ở train) | Nằm dưới cap 12 giờ; vẫn chỉ 2 giảng viên và 2 bài ở mỗi tập đánh giá, không đủ để thay thế chắc chắn `n=300` YTSeg đã ghi trong kế hoạch. |
| Đủ quyền, GT, media, attrition tại thời điểm này | **0 xác nhận** | Không thể khóa split official | Chỉ qualification. |

Các bài cùng giảng viên phải cùng split, gồm PHYS 200/201; dùng `course_id` riêng cho hai khóa đó là chưa đủ. [Dataset contract](../../multimodal-lecture-summarizer/experiments/evaluation/dataset_contracts.py) kiểm course overlap trên ba split và `speaker_id` overlap giữa validation/final_test, nhưng chưa ép `speaker_id` train-vs-validation/test cho mọi dataset. Cần thêm kiểm ba chiều hoặc bảng split audit độc lập trước freeze. Chọn nhiều bài từ cùng khóa không tăng số giảng viên độc lập; paired bootstrap theo video đơn thuần sẽ đánh giá quá lạc quan nếu các bài cùng giảng viên tương quan.

[Master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) còn ghi official RQ1 dùng YTSeg official split + frozen multimodal subset, bốn delta với paired bootstrap CI và Holm; [unified plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/plan.md) nhắm `n=300` YTSeg. Không có ngưỡng tối thiểu giảng viên Yale đã đăng ký trước. Vì vậy **không tuyên bố split Yale hiện đủ mạnh cho official RQ1 và không thay YTSeg bằng Yale một cách âm thầm**. Yale có thể là external/diagnostic cohort sau qualification; nếu muốn lấy làm official chính, phải sửa protocol trước khi chạy, định nghĩa unit thống kê, power/CI theo cụm giảng viên và split đã khóa.

## Việc còn mở

1. Truy nguồn/tình trạng quyền biểu đồ và dữ liệu ở ECON 251/252 trên toàn MOV, theo đúng phạm vi xử lý nội bộ; ghi chứng cứ cho từng thành phần hoặc loại trừ thành phần chưa rõ bằng pipeline kiểm được.
2. [Đối chiếu cấu trúc GT/MOV](./rq1-yale-260929-publisher-gt-mov-structural-audit.md) và snapshot nguồn đã xong 6/6. Khi freeze, dùng đúng snapshot này hoặc so lại hash GT để phát hiện nguồn đổi. Không phân loại chủ đề, onset hoặc tạo mốc mới; báo riêng giới hạn chất lượng ngữ nghĩa.
3. Rà quyền/GT của bốn MOV còn lại và ba bài ENGL hold; bổ sung pool nhiều giảng viên nếu muốn Yale làm đánh giá theo giảng viên. Trước D2, sửa/kiểm invariant instructor-disjoint trên cả train/validation/final_test, khóa manifest và power plan; giữ nguyên YTSeg official cho tới khi protocol được phê chuẩn sửa.
