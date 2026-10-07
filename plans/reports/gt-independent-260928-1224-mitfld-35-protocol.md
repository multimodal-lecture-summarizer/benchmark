# Quy trình tạo GT chapter độc lập cho cohort RQ1 MITFLD 35 bài

**Quyết định:** người dùng bỏ qua xác minh bằng email lúc 12:24, 2026-09-28. `frags` MITFLD chỉ dùng để kiểm cấu trúc/căn media; **không** làm đáp án hoặc gợi ý cho người gán nhãn. Tài liệu này là quy trình, **chưa có nhãn GT mới**. Nguồn: [cohort v2](./mitfld-rq1-35-260928-1120-selected.csv), [báo cáo GT provenance](./gt-provenance-260928-1214-mitfld-35-report.md), [điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/).

**Trạng thái sau quyết định 2026-09-28:** tài liệu này là phương án lịch sử **chưa kích hoạt**. Người dùng giữ [quy tắc GT có sẵn](../260921-1943-scientific-benchmark-pipeline/plan.md) cho official RQ1 và chỉ dùng [MITFLD 35 bài làm pilot](./rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md). Không tuyển người gán, tạo hoặc đưa nhãn trong template này vào official D2. [Master plan RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) giữ nguyên YTSeg cùng subset multimodal đóng băng; thiếu GT có sẵn phù hợp thì báo `not_eligible`. Phần dưới chỉ lưu quy trình đã soạn, không phải danh sách việc cần thực thi hiện tại.

## 1. Điều kiện bắt đầu theo từng bài

Mỗi ID phải có: trang OCW và đúng MP4 được dẫn; quyền dùng cho quy trình xem/gán nhãn được ghi; ngoại lệ hình/tiếng được đánh giá và xử lý; duration/time origin của MP4 cố định; đối chiếu hình/tiếng ở mốc đầu–giữa–cuối với nguồn nhãn cũ chỉ để kiểm căn chỉnh, không cho annotator xem nhãn cũ. Lưu SHA-256 của media dùng để gán khi có bản cục bộ hợp lệ; trước lúc đó, URL/item identifier và metadata không thay thế hash file. `JuKKBf-uSDI` giữ trạng thái hold vì slide có ngoại lệ CC đã tìm thấy trong MP4.

Nếu ID không đạt quyền hoặc căn chỉnh, ghi lý do và xét reserve kế tiếp **cùng khóa/split** theo [thứ tự khóa trước](./mitfld-rq1-35-260928-1120-reserve-order.csv). Không thay theo điểm mô hình. Không tạo nhãn cho bài đang hold.

## 2. Định nghĩa nhãn

- Chapter là đoạn liên tục dạy một ý/nhóm ý có thể đặt tiêu đề ngắn, cụ thể cho người xem. Đặt boundary khi chủ đề giảng dạy chuyển có ý nghĩa; kiểm cả nội dung nói và hình. Chuyển slide, thay camera, dừng nói, ví dụ ngắn hoặc hiệu ứng dựng phim **một mình** không tạo chapter.
- Ghi boundary theo giây từ đầu A/V đã giải mã của MP4 OCW, độ chính xác tới 0,1 s. Mốc 0 và duration cuối là sentinel của interval, **không** tính vào tập internal boundaries. Intro/outro, bài ôn tập, bài trình bày sinh viên và clip ngắn được gắn `segment_kind`; quyết định có nằm trong endpoint RQ1 hay không phải khóa trước khi xem dự đoán mô hình.
- Mỗi chapter có `start_s`, `end_s`, `title`, `segment_kind`, `reason`, `evidence_modality`, `confidence`. Tiêu đề/diễn giải do annotator tự viết, không chép nguyên văn transcript, slide hoặc `frags`.

## 3. Gán nhãn và QC

1. Pilot rubric trên ba bài ngoài cohort/reserve, ưu tiên ba ID feasibility cũ đã qua gate quyền. Hai người gán thử độc lập; chốt ví dụ biên, ngưỡng tối thiểu cho chapter ngắn, cách xử lý intro/outro/review và tolerance ghép boundary **trước** khi bắt đầu 35 ID. Phiên bản rubric, ngày và người phê duyệt được khóa.
2. Mỗi bài có **hai annotator độc lập**, đủ hiểu khóa học hoặc được chuyên gia môn hỗ trợ. Họ xem/nghe bản OCW cố định; mù với `frags`, output mô hình và vai trò train/validation/final_test. Không trao đổi nhãn trước khi nộp. Nhãn cá nhân lưu nguyên bản, không sửa đè.
3. Ghép boundary một đối một theo tolerance đã khóa từ pilot; báo cáo agreement F1 ở ±15/30/60 s, median absolute offset, số chapter/bài và bất đồng theo khóa. Người thứ ba adjudicate mọi boundary không ghép hoặc khác loại ý; lưu quyết định, lý do và hai nhãn gốc. Rà ngẫu nhiên 10% bài đã đồng thuận và toàn bộ bài review/clip ngắn/sinh viên.
4. Nếu agreement dưới ngưỡng đã khóa, cho hai annotator gán lại **sau** huấn luyện bổ sung nhưng giữ version cũ; không tự chọn nhãn thuận lợi cho mô hình. Báo cáo failure/attrition theo ID và khóa.

## 4. Quyền bộ GT mới và niêm phong test

Trước khi gán, người tham gia ký chấp thuận cho lưu nhãn, dùng trong nghiên cứu phi thương mại, công bố aggregate và cấp phép nhãn mới theo điều khoản được thống nhất. Đề xuất CC BY-NC-SA 4.0 cho **nhãn do nhóm tự tạo**, kèm attribution OCW/người gán; xác nhận điều này với chủ sở hữu nhãn trước khi release. Chỉ phát hành timestamp/tiêu đề tự viết nếu quyền nguồn cho phép; không kèm MP4, frame, audio, transcript, ảnh/slide bên thứ ba. Giấy phép nhãn mới không tự cấp quyền cho media gốc.

Lưu manifest `{video_id, course_id, split, ocw_url, media_sha256, decoded_duration, rubric_version, annotator_1_hash, annotator_2_hash, adjudicated_hash, rights_status}`. Người chạy mô hình không truy cập nhãn final_test tới khi chọn mô hình/threshold xong trên train/validation và protocol D2 được duyệt. Chạy final_test một lần; giữ bản nhãn cá nhân và audit log để truy vết.

## 5. Biểu mẫu và trạng thái

[CSV template trống](./mitfld-rq1-35-260928-1224-independent-gt-template.csv) chỉ nêu schema, không chứa GT. Một hàng là một chapter của một annotator. `annotation_status` có `draft`, `submitted`, `adjudicated`; khóa file `submitted` bằng hash, không sửa tại chỗ. Các trường nhận dạng annotator dùng mã nội bộ thay cho tên cá nhân trong bản công bố.

Ước tính theo [báo cáo provenance](./gt-provenance-260928-1214-mitfld-35-report.md): 37,04 giờ video, hai lượt độc lập và adjudication cần khoảng **128–177 giờ người**, chưa tính tuyển/đào tạo người hoặc kiểm quyền. Đây là dự toán, không phải GT đã tạo.

## Câu hỏi chưa giải quyết

1. Ai là hai annotator và adjudicator đủ chuyên môn cho 21 khóa, ai giữ quyền cấp phép nhãn mới?
2. Sau kiểm quyền/căn chỉnh, bao nhiêu ID thật sự được mở để gán nhãn và có cần reserve cùng khóa?
3. Pilot sẽ khóa tolerance/ngưỡng agreement cụ thể nào trước khi gán 35 bài?
