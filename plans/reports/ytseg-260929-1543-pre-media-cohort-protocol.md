# YTSeg: khóa cohort khảo sát trước khi tải media

**Khóa:** 2026-09-29 (Asia/Bangkok), trước bất kỳ full-file download nào của cohort này.  
**Nguồn:** `retkowski/ytseg` text revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`.  
**Danh sách:** [CSV 12 hàng](./ytseg-260929-1543-pre-media-cohort-lock.csv), SHA-256 `4DEDB0EFACECF547F1BF2EAC773A0B6CED3CEA9ED1330875CF6E9B493E9F0719`. Không sửa file này sau khi bắt đầu tải; bằng chứng mới nằm ở ledger riêng.  
**Mục đích:** qualification có chủ đích của các đường publisher media, chưa phải mẫu suy luận official và chưa là D2.

## Quy tắc chọn và loại đã khóa

1. Giữ duy nhất ID trong YTSeg **train** của revision trên. Loại Yale; không đọc GT của original validation/test. Hai ID MIT 16.687 thuộc original validation/test được ghi trong CSV là `exclude`, không đưa vào khảo sát media hoặc chọn mô hình.
2. Chọn nguồn có trang khóa/bài do publisher duy trì, ánh xạ cùng YouTube ID, giảng viên xác minh được và điều khoản nguồn đọc được. Khảo sát có giới hạn: 11 ID kênh MIT OCW và một ID CS50P tìm qua sàng lọc 25 kênh train đông nhất. Đây là tìm nguồn có chủ đích, không đại diện toàn YTSeg.
3. Bốn `primary` gồm bài `-dOX_4lI6HY` theo yêu cầu người dùng và một ID ở mỗi ba khóa còn lại. Sáu `reserve` còn lại đều thuộc MIT 16.687, xếp theo thứ tự trong CSV cố định; chỉ dùng để kiểm thêm cùng khóa sau khi primary fail cổng không liên quan điểm mô hình. Không biến reserve cùng khóa thành nhóm độc lập mới.
4. Giữ MIT 14.01 primary ở trạng thái nguồn media `hold`: hiện chỉ xác minh kênh publisher trên YouTube, chưa có MP4 publisher trực tiếp. Không loại nó khỏi denominator vì biết sớm rằng nguồn media khó lấy.
5. Đối chiếu ID chính xác với MITFLD 35 đã chọn và 10 pilot cũ: 0 giao theo [receipt YTSeg](./ytseg-260929-pinned-text-metadata-audit-receipt.json). Kiểm near-duplicate nội dung và lịch sử tuning khác ở giai đoạn media; trùng hoặc không xác minh được thì `hold`/`exclude`, không thay sau khi xem điểm mô hình.

## Quy ước GT trước media

Đã đọc toàn bộ 16.404 hàng train trong Parquet ghim và đối chiếu `raw_chapters` với `chapter_titles`/`chapter_timestamps`: có **năm mẫu biểu diễn** nằm trong ba dạng chênh số tiêu đề–mốc. Cả 10 ID train trong CSV cùng mẫu: tiêu đề đúng bằng tiêu đề `raw_chapters`; mốc bằng các `raw_chapters.start_time` sau mốc đầu 0. Từng ID chỉ có một hàng. Mẫu này cho phép hiểu cấu trúc, **không cho phép tự zip tiêu đề và mốc theo cùng index**.

[Paper §2.2](https://aclanthology.org/2024.eacl-long.25.pdf) mô tả tiền xử lý Intro/Outro, nhưng [revision công khai](https://huggingface.co/datasets/retkowski/ytseg/tree/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970) không chứa mã chuyển đổi GT. Do yêu cầu đối chiếu mã upstream chưa đạt, **GT cả 10 ID giữ `hold_gt`**. Media audit dưới đây là qualification kỹ thuật; không nâng `hold_gt` thành `pass` chỉ vì video tải được hoặc transcript có vẻ khớp. Không tạo/chỉnh mốc, tiêu đề hay vùng Intro/Outro.

## Cổng media và quyền cố định

- Ưu tiên MP4 do trang publisher liên kết. Đường YouTube-only không tự đổi sang `yt-dlp`; quyền annotation, quyền video/resource và điều khoản đường truy cập là các trường riêng.
- Với mỗi primary có nguồn phù hợp: tải **toàn file** vào `multimodal-lecture-summarizer/experiments/datasets/ytseg_qualification/` (ignored), ghi URL, HTTP header/byte count, SHA-256; `ffprobe` codec/duration; `ffmpeg` giải mã video+audio toàn file và kiểm PTS. File tải thiếu byte, hash/decoder lỗi hoặc sai timeline giữ `hold_media`/`exclude` kèm lý do.
- Đối chiếu transcript/timeline ở ba vị trí cố định 10%, 50%, 90% thời lượng và quanh chapter nội bộ đầu, giữa, cuối. So với transcript/subtitle publisher hoặc lời nói thực của cùng file; ghi đoạn và sai khác. Không dùng ASR/mô hình tạo chapter GT hoặc dùng điểm mô hình chọn bài. Duration gần bằng chỉ là điều kiện sơ bộ.
- Kiểm credits/ngoại lệ trên trang và thành phần thực sự xuất hiện trong file theo phạm vi xử lý nội bộ, chỉ công bố kết quả tổng hợp. Thiếu chứng cứ toàn thành phần giữ `hold_rights`, không tự suy từ giấy phép dataset hay giấy phép khóa học chung.
- Giữ mọi primary fail trong denominator. Không thay ID do kết quả mô hình. Không tải reserve vì mục tiêu tăng N nếu primary đã cho biết cùng khóa không làm tăng G; chỉ dùng reserve để điều tra lỗi riêng của một file theo quy tắc trên.

## Nhóm độc lập và split

Tạo đồ thị: mỗi video nối với `course_id` của nó và **tất cả** `lecturer_ids` nguồn công bố; thành phần liên thông là một nhóm, kể cả quan hệ bắc cầu. Không gộp chỉ theo `channel_id`, không tách hai bài chung khóa/giảng viên sang hai split. Nếu giảng viên chưa rõ, giữ `hold_identity` thay vì gán `unknown` rồi coi độc lập.

Sau media/GT/quyền, báo `N` video và `G` thành phần thực sự `pass`; chỉ chia train/validation/final_test bằng nguyên nhóm và loại trùng nội dung. Hiện protocol dự án **chưa chốt ngưỡng N/G hoặc mục tiêu precision/power định lượng**; không được gọi ba nhóm là “đủ” chỉ vì có thể đặt một nhóm vào mỗi split. Nếu không đạt một thiết kế có CI theo nhóm hợp lý, ghi `no_selection`/`blocked_data`, chuyển qualification sang VidChapters-7M. Nếu đạt và GT/rights hoàn tất, phải có amendment cho derived split/subset trước D2; chưa chạy official RQ1.

## Câu hỏi chưa giải quyết

1. Có mã chuyển đổi GT upstream hoặc quyết định protocol chấp nhận phép đọc trực tiếp từ `raw_chapters` phát hành không?
2. MIT 14.01 có media publisher phù hợp không, và ba nhóm còn lại qua full-file/rights/timeline bao nhiêu bài?
3. Sau attrition, cần mục tiêu precision/power nào để xác định G/N đủ cho CI theo nhóm?
