# Khảo sát YTSeg: annotation đã ghim, split và một đường media MIT OCW

**Kiểm tra:** 2026-09-29 (Asia/Bangkok)  
**Phạm vi:** nguồn GT, metadata/split, giao ID với MITFLD 35 và một bài giảng ngoài Yale. Không chọn mô hình, tải video đầy đủ, xem nội dung, sửa GT, khóa D2 hay chạy official RQ1.  
**Kết luận:** YTSeg tiếp tục là **ứng viên annotation**. Official multimodal RQ1 vẫn **blocked trước D2** vì thiếu cohort lecture nhiều nhóm có quyền/media và split độc lập đã xác minh.

## Tóm tắt

Lần này đọc trực tiếp **sáu Parquet text của revision** `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970` từ [release YTSeg](https://huggingface.co/datasets/retkowski/ytseg/tree/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970/text). [Receipt JSON](./ytseg-260929-pinned-text-metadata-audit-receipt.json) giữ tên, kích thước và LFS SHA-256 của từng file, tổng số hàng, giao ID/kênh và kiểm GT train. LFS SHA lấy từ metadata release; chưa tải toàn bộ file để tự tính lại hash byte.

Đã xác minh một bài giảng ngoài Yale cụ thể: `-dOX_4lI6HY` là một hàng **train** trong Parquet đã ghim. [Trang MIT OCW Lecture 13](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-13-interpreting-weather-data/) chứa chính YouTube ID đó và liên kết [MP4 trên Archive](https://archive.org/download/MIT16.687IAP19/MIT16_687IAP19_lec13_300k.mp4). HEAD MP4 trả 200, 123.297.321 byte; `ffprobe` đọc H.264 640×360, AAC, thời lượng 3.122,324 giây so với `duration=3122.0` trong YTSeg. Đây là **khả dụng kỹ thuật của một đường media** và khớp thời lượng sơ bộ, chưa phải full decode, content alignment, quyền toàn thành phần hay D2.

## Phương pháp và nguồn

1. Đọc [paper YTSeg EACL 2024](https://aclanthology.org/2024.eacl-long.25.pdf) và [dataset card hiện hành](https://huggingface.co/datasets/retkowski/ytseg). Paper mô tả chapter do creator cung cấp rồi tiền xử lý: nội suy thời gian câu caption, gán câu băng qua boundary theo phần thời gian lớn hơn, thêm Intro/Outro cho vùng chưa phủ và loại bản ghi không hợp lệ. Vì thế nhãn phát hành là **creator-derived đã xử lý**, không phải bản chapter YouTube nguyên trạng.
2. API Hugging Face trả revision trên; `HfFileSystem` đọc các cột `video_id`, `channel_id`, `duration` trên train/validation/test. Chỉ train được đọc `chapter_titles` và `chapter_timestamps`; **không đọc GT validation/test**. Parquet column projection tránh lấy transcript/audio/video. Receipt giữ LFS SHA của sáu file.
3. Đối chiếu `video_id` chính xác với [MITFLD 35 đã khóa](./mitfld-rq1-35-260928-1120-selected.csv) và 10 ID pilot cũ trong [receipt chọn cohort](./mitfld-rq1-35-260928-1120-selection-receipt.json). Chưa kiểm near-duplicate nội dung hoặc mọi lịch sử tuning khác.
4. Đọc HTML trang MIT OCW, HEAD liên kết MP4 được trang cấp và chạy `ffprobe` từ xa trên container; không lưu video. Đọc [điều khoản MIT OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) và [điều khoản YouTube](https://www.youtube.com/t/terms/) để tách quyền nội dung và đường truy cập.
5. Tìm `rq1-d2-audit-20260929.md` và `rq1-d2-audit-kit-20260929.zip` trong workspace, attachments, Downloads, Desktop, Documents và thư mục tạm: **không thấy**. Chỉ có đoạn văn người dùng đã dán; không gọi các receipt trong ZIP là đã kiểm lại.

Mẫu lệnh đọc metadata đã ghim:

```python
from huggingface_hub import HfFileSystem
import pyarrow.parquet as pq

fs = HfFileSystem()
path = "datasets/retkowski/ytseg@4ee1c1fccc5a9e118ff0918f3df1e61aadca8970/text/test-00000-of-00001.parquet"
with fs.open(path, "rb") as source:
    ids = pq.read_table(source, columns=["video_id", "channel_id"])
```

## Kết quả GT và schema

| Kiểm trực tiếp trên train | Số hàng |
|---|---:|
| Tổng | 16.404 |
| `len(titles) = len(timestamps) + 1` | 15.813 |
| `len(titles) = len(timestamps) + 2` | 556 |
| `len(titles) = len(timestamps)` | 35 |
| Bị cờ thời gian âm/vượt `duration` hoặc mốc không tăng nghiêm ngặt trong phép kiểm này | 0 |

Không thể `zip(chapter_timestamps, chapter_titles)` theo vị trí rồi coi là GT. Ví dụ train `-dOX_4lI6HY`: 22 tiêu đề, 21 timestamp; ba tiêu đề đầu là `Introduction`, `Definitions`, `Don't Despair, Use Softwair`, hai mốc nội bộ đầu là 39 và 136 giây; mốc cuối 3.006 giây. Ba mẫu có chênh +2 đều kết thúc bằng `Outro` không có timestamp ghép ở trường đọc; đây **không phải** kiểm toàn bộ 556 hàng cho `Outro`. Ba mẫu chênh 0 bắt đầu timestamp rất gần 0. Cần chốt quy ước GT theo release/paper, ghi ngoại lệ và không tự bù Intro/Outro hay dịch mốc.

## Split và giao dữ liệu

| Split | Hàng | ID duy nhất | Kênh |
|---|---:|---:|---:|
| Train | 16.404 | 16.387 | 386 |
| Validation | 1.447 | 1.446 | 281 |
| Test | 1.448 | 1.448 | 280 |

- **Train–validation:** bốn ID video chung (`VKmOXCEq-6A`, `nP-nMZpLM1A`, `xZ3k7Fd6_eU`, `z6qATR0VLnk`); 278 kênh chung.
- **Train–test:** không trùng ID video; **276 kênh chung**.
- **Validation–test:** không trùng ID video; **238 kênh chung**.
- Cả 35 ID MITFLD đã chọn và 10 ID pilot được liệt kê trong selection receipt có **0 giao ID chính xác** với toàn bộ YTSeg revision này. Điều đó chưa chứng minh không trùng nội dung hoặc không từng được dùng ở nguồn khác.
- Kênh của bài MIT mẫu (`UCEBb1b_L6zDS3xTUrIALZOw`) có **9 train, 1 validation, 1 test**, 11 ID duy nhất trong release đã ghim. Đây chỉ là pool metadata của một kênh; chưa xác minh 11 bài đều thuộc OCW, bao nhiêu khóa/giảng viên, hay quyền media từng bài. Một kênh này không đủ chứng minh split độc lập.
- Các cột YTSeg vừa đọc không cho `course_id` hay danh tính giảng viên. `speaker_category`/`num_speakers` trên card chỉ là đặc trưng, không phải `speaker_id` định danh. Không thể xác nhận course/speaker-disjoint từ `channel_id` hoặc video ID.

[Contract trong repo](../../multimodal-lecture-summarizer/experiments/evaluation/dataset_contracts.py) chấp nhận `creator_chapters` nhưng yêu cầu provenance, mốc hợp lệ và tách `course_id`/`speaker_id` giữa split. Giữ nguyên official split chỉ có thể mô tả giới hạn video ID train–test; nó không hỗ trợ claim độc lập theo khóa/giảng viên. Derived split phải có amendment trước model selection theo [master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md).

## Media, quyền và khả năng đánh giá đa phương thức

| Cổng | Bằng chứng ở `-dOX_4lI6HY` | Trạng thái |
|---|---|---|
| GT release | Hàng train trong Parquet ghim; `duration=3122.0`, 22 title/21 mốc | Ứng viên nguồn GT; chưa QC onset ngữ nghĩa |
| Source/course | Trang MIT OCW cùng ID YouTube, Lecture 13 của khóa 16.687 IAP 2019; trang liệt kê Dr. Philip Greenspun và Dr. Tina Srivastava | Mapping một bài có bằng chứng nguồn; chưa có cohort nhiều khóa |
| Media | MP4 do trang MIT liên kết; HEAD 200/123.297.321 byte; `ffprobe` 3.122,324 giây | Metadata khả dụng; chưa full hash/decode/PTS/alignment |
| Quyền | Trang MIT cung cấp download; điều khoản OCW có giới hạn và ngoại lệ cho tài liệu bên thứ ba. Dataset card nói tác giả không sở hữu bản quyền video | Chưa `rights_pass` toàn thành phần; Archive là host ngoài, cần kiểm điều kiện resource cụ thể |
| Split | Hàng này thuộc train; official toàn bộ trùng kênh giữa split | Chưa có course/speaker-disjoint cohort |

Điểm tích cực mới: một đường publisher-link tới MP4 tồn tại nên không buộc phải dựa vào script `yt-dlp` của YTSeg cho **bài này**. Không suy ra 19.299 video có đường tương tự. Nếu lấy video từ YouTube thay vì đường publisher/Archive, [điều khoản YouTube](https://www.youtube.com/t/terms/) là một cổng truy cập riêng. `ffprobe`/HEAD không xác nhận file đúng bản dựng ở mọi đoạn; sai số thời lượng 0,324 giây chỉ là tín hiệu sơ bộ.

## Quyết định khảo sát và việc tiếp theo

**Tiếp tục YTSeg ở mức qualification; chưa freeze D2.** Kết quả mới đóng cổng snapshot/ID tốt hơn báo cáo metadata Viewer ngày trước, nhưng còn thiếu điều kiện chủ chốt của official multimodal RQ1.

1. Khóa quy tắc đọc GT có chênh tiêu đề/mốc `+1`, `+2`, `0` và xử lý vùng chưa gắn nhãn. Giữ nguyên bản phát hành, ghi mẫu ngoại lệ; không biến tiêu đề `Outro` thành mốc mới.
2. Lập danh sách lecture ngoài Yale từ **release đã ghim**, rồi đối chiếu nguồn publisher cho từng ID để xác minh khóa/giảng viên. Khóa selection/reserve và kiểm toàn bộ lịch sử pilot/tuning trước khi xem điểm mô hình. Metadata YTSeg hiện không có video title/course ID đủ để tự động kết luận lecture cohort.
3. Kiểm nhiều publisher-linked video thuộc **nhiều khóa và giảng viên**; ghi quyền resource/thành phần, file hash, full decode/PTS và khớp chapter ở nhiều vị trí. Một bài MIT trên đây chỉ chứng minh một đường khả thi.
4. Sau attrition, đếm nhóm độc lập và tính khả năng train/validation/final_test, ngân sách và CI/power. Nếu không đủ, kết luận `blocked_data`/`blocked_rights` thay vì thay bài theo kết quả mô hình. Nếu đủ, soạn amendment cho subset/split/claim trước D2.
5. Chuyển sang VidChapters-7M chỉ khi YTSeg không đủ cohort qua các cổng trên; áp dụng cùng tiêu chuẩn. Giữ SSLectures `gt_provenance_hold` và AVLectures boundary-only ngoài luồng GT mốc + title.

## Câu hỏi chưa giải quyết

1. Có bao nhiêu lecture YTSeg ngoài Yale với `course_id` và giảng viên xác minh được từ publisher, sau loại trùng lịch sử pilot?
2. Bao nhiêu bài có media do publisher cung cấp trực tiếp, quyền và ngoại lệ rõ, full-file hash/decode và GT khớp timeline?
3. Sau attrition, có đủ nhóm độc lập cho RQ1 đa phương thức và cần amendment nào cho split/loại GT đã xử lý?
