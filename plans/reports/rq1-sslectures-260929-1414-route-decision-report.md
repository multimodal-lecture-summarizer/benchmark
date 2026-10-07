# RQ1: chọn SSLectures làm nhánh nguồn tiếp theo

**Kiểm gói và truy chín bài 14:32:** [Báo cáo bằng chứng và ledger](./rq1-sslectures-260929-1432-package-provenance-nine-row-report.md) đã xác định file annotation và nối 9/9 bản ghi với YouTube ID trên trang OCW. **Chưa xác định người/cách tạo chapter; 9/9 tiếp tục `gt_provenance_hold`, 0 GT official, 0 D2.** Con số 1.378 là số dòng CSV, không phải số GT đủ điều kiện.

**Quyết định:** 2026-09-29 14:14, Asia/Bangkok. Theo yêu cầu người dùng, dừng khảo sát và qualification Yale; dùng SSLectures làm **nhánh ứng viên duy nhất đang khảo sát** cho RQ1. Không đổi quy tắc official GT: mốc/tiêu đề chapter phải có nguồn phát hành độc lập đủ điều kiện; dự án không tự gắn, sửa hoặc suy mốc. MITFLD 35 giữ pilot. Đây là quyết định ưu tiên nguồn, **chưa phải** protocol amendment, D2 freeze hay kết quả official.

## Bằng chứng hiện có và cổng dừng

| Cổng | Kết quả kiểm | Trạng thái |
|---|---|---|
| Mẫu khóa trước | [Receipt](./rq1-sslectures-260929-1401-prelocked-source-screen-receipt.json): 9 bài/5 khóa lấy từ CSV 1.378 bài/69 khóa; không chọn theo kết quả mô hình. | Đã khóa mẫu khảo sát. |
| Media nguồn | [Đối chiếu từng trang](./rq1-sslectures-260929-1401-mit-ocw-source-screen-receipt.json): 9/9 bài có trang MIT OCW và liên kết tải video. | Chỉ xác nhận đường media trên trang; chưa tải, hash, giải mã. |
| GT chapter nguồn | [Báo cáo sàng lọc](./research-260929-1401-sslectures-mit-ocw-gt-source-screen-report.md): 0/9 trang MIT hiển thị bảng mốc/tiêu đề chapter nội bộ tương ứng. CSV và `auto_generated=False` không chứng minh publisher/creator GT hay QC. | **9/9 `gt_provenance_hold`.** Chưa kết luận không tồn tại nguồn creator khác. |
| Khả năng truy xuất từ CSV | Header file đã tải không có cột URL nguồn GT, URL/video ID, giảng viên, license hoặc revision. Các trường liên quan chỉ là `titles`, `true_chapters_start`, `true_chapters_end` và các trường fragment/transcript. | Cần đối chiếu nguồn ngoài CSV theo từng bài; không thể coi file CSV là receipt provenance. |
| Quyền, chất lượng, split | [MIT OCW Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) là cơ sở điều khoản chung; chưa kiểm ngoại lệ từng resource, khớp timebase, visual hay số giảng viên/khóa sau attrition. [Audit CSV](./rq1-preexisting-gt-260928-1843-source-rights-d2-qualification-report.md) đã thấy 7 hàng lỗi cấu trúc, 4 chapter cuối âm, 974/1.378 hàng lệch timebase trên 30 giây giữa hai trường thời gian. | HOLD; **0 D2, 0 official RQ1**. |

## Việc thực hiện tiếp

1. Truy nguồn mốc và tiêu đề của **đúng chín bài đã khóa**, ưu tiên trang publisher/creator và phiên bản lưu trữ của chính trang đó. Ghi URL, revision/snapshot, cặp mốc–tiêu đề, timebase và quan hệ với file video MIT OCW. Không thay bài bị HOLD bằng bài khác sau khi biết kết quả.
2. Nếu có GT nguồn đủ điều kiện, kiểm điều khoản và ngoại lệ của đúng resource, rồi mới tải mẫu tối thiểu để hash, full decode/PTS, so duration và đo visual kỹ thuật theo lịch cố định. Không dùng ASR/OCR/model để tạo GT hay chọn bài.
3. Chỉ sau attrition thật mới đếm số bài, giảng viên và khóa độc lập; tính khả năng train/validation/final_test, CI/power và cap D2. Nếu đủ, soạn sửa [master protocol](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) trước model selection vì hiện RQ1 ghi YTSeg. Nếu không đủ, báo RQ1 multimodal `not_eligible`; không nới chuẩn GT để cứu nguồn.

**Yale:** ngừng khảo sát, không tải thêm và không đưa vào cohort RQ1. Bằng chứng cũ chỉ lưu để truy vết quyết định, không tạo nhiệm vụ tiếp.

## Câu hỏi chưa giải quyết

1. Nguồn publisher/creator nào đã phát hành đúng các cặp mốc–tiêu đề trong CSV cho chín bài, với phiên bản và timebase xác minh được?
2. Sau các cổng GT, quyền, media và split, cohort SSLectures còn bao nhiêu giảng viên/khóa độc lập và có đủ sức mạnh thống kê theo protocol không?
