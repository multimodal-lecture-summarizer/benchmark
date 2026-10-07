# RQ1: khảo sát YTSeg trước khi chọn nguồn official

**Ngày:** 2026-09-29 (Asia/Bangkok)  
**Loại:** brainstorm / quyết định ưu tiên khảo sát  
**Quyết định của người dùng:** khảo sát YTSeg trước; VidChapters-7M dự phòng.  
**Trạng thái:** 0 D2, 0 official RQ1; chưa sửa protocol, tải media, chọn mô hình hoặc chạy 04a/04b.

## Tóm tắt

Chuyển ưu tiên khảo sát từ SSLectures sang YTSeg. Đích của lượt tiếp theo là một quyết định `go_candidate` hoặc `blocked_*` có chứng cứ, không phải một manifest D2. Khảo sát snapshot annotation chính thức, cách tạo nhãn, lecture subset ngoài Yale, khóa/giảng viên, quyền và đường nhận media. Chỉ mở rộng sang media khi cổng nguồn và quyền có cơ sở. Nếu YTSeg không còn đủ nhóm độc lập hoặc không có đường media phù hợp, dùng VidChapters-7M qua đúng cùng cổng.

## Vấn đề thực sự

Nguồn official RQ1 cần chapter timestamps và titles phát hành độc lập, gắn đúng bản video, có quyền sử dụng và đủ nhóm độc lập cho đánh giá đa phương thức. SSLectures có 9/9 mẫu khóa trước trong `gt_provenance_hold`; YTSeg có đường nguồn nhãn rõ hơn nhưng media, quyền và split vẫn chưa đạt D2. Chuyển tên dataset không tự giải quyết cổng khoa học.

### Kiểm giả định trước khi chọn nguồn

| Giả định | Nếu sai | Phép kiểm trước |
|---|---|---|
| Bản YTSeg phát hành giữ quan hệ mốc–tiêu đề và phiên bản truy được | Chấm sai GT hoặc nhầm nhãn creator nguyên trạng với nhãn đã xử lý | Pin revision/checksum; đọc schema; đối chiếu mốc, titles, Intro/Outro và vùng chưa gắn nhãn với nguồn ở mẫu khóa trước |
| Có đủ lecture ngoài Yale và nhóm khóa/giảng viên xác minh được | Không thể đưa ra kết luận course-disjoint | Đếm nhóm thật sau lọc và trùng lịch sử pilot; không suy `course_id` từ `channel_id` |
| Có media đúng phiên bản, quyền/đường truy cập phù hợp | Không thể chạy nhánh visual/OCR official | Ledger từng video: quyền annotation/media, ngoại lệ resource, đường nhận media, byte/hash/full decode và kiểm khớp nhiều vị trí |
| Tập còn lại đủ cho mục tiêu thống kê | Kết quả official yếu hoặc không hợp lệ | Tính denominator/attrition, nhóm độc lập và độ chính xác/CI dự kiến trước khi chọn mô hình |

## Ba cách hiểu bài toán

1. **Thiếu GT có nguồn:** ưu tiên YTSeg vì paper và release mô tả nhãn creator-derived. Giới hạn: phải ghi chính xác tiền xử lý, không gọi là nhãn creator nguyên trạng.
2. **Thiếu media có thể dùng:** provenance tốt vẫn không mở được RQ1 đa phương thức. Kiểm quyền và đường nhận đúng video sớm; nếu tắc, giữ text/audio riêng hoặc dừng official multimodal.
3. **Thiếu độc lập và sức mạnh thống kê:** official split YTSeg không chứng minh course/speaker-disjoint. Cần derived group split được công bố qua protocol amendment, hoặc hạ phạm vi kết luận.

## Phương án và đánh đổi

| Hướng | Lợi thế | Rủi ro/cổng dừng | Quyết định |
|---|---|---|---|
| YTSeg trước | Khớp nguồn đã đăng ký trong master plan; `creator_chapters` có trong contract; annotation có thể truy nguồn | Official split có chồng kênh; CC BY probe cũ chỉ train/14 kênh; media và quyền chưa qua | **Chọn để khảo sát** |
| Tiếp tục SSLectures | Đã khóa mẫu 9 bài/5 khóa và có đường trang OCW | 9/9 chưa xác minh nguồn mốc; thêm truy vết có nguy cơ không mở được gate | Giữ `hold`, không tiếp tục đầu tư chính |
| VidChapters-7M trước | Annotation dự phòng đã được kiểm cấu trúc một phần theo ghi chú người dùng | Đa miền; phải lọc lecture, xác minh media/quyền và split mới | Dự phòng nếu YTSeg thất bại |
| AVLectures | Có GT boundary trong artifact đã đọc | Chưa có title và cần đúng bản media ghép/cắt | Chỉ dùng nhánh boundary-only riêng nếu đổi phạm vi |

## Bằng chứng và giới hạn

- [Master plan RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) hiện ghi YTSeg official split cùng frozen multimodal subset; mọi đổi split/cohort/GT cần amendment trước model selection.
- [Contract GT](../../multimodal-lecture-summarizer/experiments/evaluation/dataset_contracts.py) chấp nhận `creator_chapters` nhưng đòi source/revision/origin/time convention, mốc hợp lệ và `course_id`/`speaker_id` không trùng giữa các split. Contract không chứng minh quyền hay fidelity của nhãn với video nguồn.
- [Handoff hiện hành](./rq1-readiness-260929-1013-official-gt-d2-handoff-report.md) ghi official YTSeg split có chồng kênh và bốn ID trùng train–validation; probe CC BY 276 video chỉ thuộc train/14 kênh, chưa có media D2. Fetch real đang fail closed.
- [Quyết định SSLectures](./rq1-sslectures-260929-1414-route-decision-report.md) được thay về **ưu tiên khảo sát** theo lựa chọn mới của người dùng; bằng chứng hold của SSLectures vẫn giữ nguyên.
- Ghi chú người dùng về paper và các artifact YTSeg/VidChapters/AVLectures là đầu vào nghiên cứu. Gói `rq1-d2-audit-20260929.md` và ZIP nêu trong ghi chú chưa được cung cấp tại workspace trong lượt này; các số kiểm byte và annotation trong đó chưa được tái chạy ở đây.

## Bước khảo sát kế tiếp và cổng dừng

1. Pin release YTSeg và checksum; lập bảng schema GT, quy tắc mốc–title, Intro/Outro, missing regions. Giữ annotation gốc, không tự thêm/sửa GT.
2. Khóa danh sách khảo sát lecture ngoài Yale từ chính release, gắn nguồn `course_id`/`speaker_id`, đối chiếu MITFLD 35 và mọi ID từng dùng pilot/tuning. Khai báo chọn mẫu và reserve trước xem kết quả mô hình.
3. Từ metadata, báo số video/khóa/giảng viên theo từng split khả dĩ. Nếu không có cách xác minh khóa hoặc không đủ nhóm độc lập, dừng claim course-disjoint; không tải media hàng loạt.
4. Kiểm một hàng media với quyền, byte/SHA-256, full decode và khớp GT ở nhiều vị trí; sau khi đường xử lý qua gate mới mở rộng đến **toàn bộ cohort đã khóa**. Một video qua gate chỉ chứng minh đường xử lý khả thi.
5. Báo `go_candidate`, `blocked_gt`, `blocked_rights`, `blocked_access` hoặc `blocked_data` kèm denominator/attrition. Nếu `go_candidate`, soạn amendment cho mọi lệch với master plan, rồi mới xem xét D2 và model selection.

**Pivot:** chuyển VidChapters-7M khi YTSeg không đủ lecture có GT khớp nguồn, media/quyền phù hợp hoặc nhóm độc lập sau attrition. Giữ AVLectures ngoài benchmark mốc + title; không tái mở SSLectures chỉ vì YTSeg vướng cổng mới.

## Tiêu chí hoàn thành bước khảo sát

- Có revision/hash annotation và bảng mapping timestamp/title, bao gồm ngoại lệ.
- Có danh sách ID khóa trước, nguồn course/speaker, báo trùng lặp với pilot, thống kê nhóm và lý do loại.
- Có ledger quyền/access/media và một receipt media khớp GT, hoặc lý do dừng rõ ràng; không suy một mẫu thành D2.
- Có quyết định go/block và phạm vi kết luận thực tế, giữ final_test chưa dùng chọn mô hình.

## Thông điệp cho nhóm

“Ta khảo sát YTSeg trước vì nhãn creator-derived có đường phát hành rõ hơn. Kết quả khảo sát phải vượt cổng nguồn, quyền, media và split; tới lúc đó RQ1 official vẫn chưa chạy. Nếu YTSeg không đủ, dùng VidChapters-7M qua cùng quy trình.”

## Câu hỏi chưa giải quyết

1. Snapshot YTSeg chính thức có đủ lecture ngoài Yale với course/speaker xác minh và đường media phù hợp không?
2. Sau attrition, còn bao nhiêu nhóm độc lập cho train/validation/final_test và CI/power?
3. Protocol amendment sẽ chốt nhãn creator-derived đã xử lý, derived split và giới hạn claim nào?
