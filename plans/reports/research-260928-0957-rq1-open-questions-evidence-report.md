# Nghiên cứu tiếp: quyền video, split khóa học và nguồn thay thế cho RQ1

Ngày kiểm tra: 2026-09-28 (Asia/Bangkok). Đây là kiểm tra nguồn công khai và metadata, không phải phê duyệt pháp lý. Không tải MP4. Đọc [kiểm toán YTSeg toàn bộ 19.299 hàng](../../multimodal-lecture-summarizer/plans/reports/research-260928-0936-ytseg-video-rights-channel-split-report.md) và [kế hoạch tiếp nối](../260928-0949-rq1-completion-after-ytseg-audit/plan.md) làm mốc; các phép thử mới dưới đây chỉ đánh giá khả năng đi tiếp.

## Kết luận nhanh

| Câu hỏi | Bằng chứng mới | Trả lời hiện tại |
|---|---|---|
| Video YTSeg nào đủ quyền và còn truy cập? | Bộ con CC BY có 276 ID/14 kênh; 14 ID chọn cố định, một ID/kênh, đều trả về metadata qua YouTube oEmbed ngày 2026-09-28. Không có giấy phép/khả năng phát/ngoại lệ trong oEmbed. | **Chưa xác nhận được video nào đủ toàn bộ điều kiện**. Có 14 phản hồi metadata, không có 14 xác nhận quyền. Cần `videos.list(part=status,snippet,contentDetails)` qua YouTube Data API với khóa hợp lệ, rồi kiểm tra quyền và phương thức truy cập theo từng video. |
| Có đủ khóa học và GT để split độc lập? | Cả 276 hàng có `chapter_timestamps`; 14 kênh phân bố rất lệch; schema không có `course_id`; subset chỉ có train. | **Chưa chứng minh được** split theo khóa học. Có thể thử tách theo kênh, nhưng không tự gọi đó là course-disjoint hay test chính thức. Mốc chương là nhãn creator/editorial của YTSeg, không phải chuyên gia độc lập. |
| Nếu YTSeg không đạt, nguồn nào? | MITFLD có 538 bộ MP4 + GT phân đoạn + transcript trên Hugging Face; một MP4 mẫu trả lời `HEAD 200`. AVLectures công bố 15 khóa CwS nhưng API archive hiện `401`. Open Yale có điều khoản tái sử dụng phi thương mại, chưa xác minh GT chương. | **MITFLD là ứng viên kỹ thuật nên kiểm toán tiếp**, chưa đủ quyền và course map. AVLectures bị chặn truy cập; Open Yale thiếu GT đã xác minh cho endpoint này. Chưa có nguồn thay thế nào được xác nhận đủ mọi cổng. |

## 1. YTSeg: kiểm tra được gì hôm nay

[Thẻ `ytseg-cc-by`](https://huggingface.co/datasets/retkowski/ytseg-cc-by) cho biết tác giả kiểm tra nhãn YouTube CC BY của video **train** tại thời điểm tạo subset, được 276 video thuộc 14 kênh. Snapshot text Parquet [do Dataset Viewer liệt kê](https://datasets-server.huggingface.co/parquet?dataset=retkowski/ytseg-cc-by) hiện có đúng 276 `video_id` duy nhất. Phân bố số video theo kênh: **121, 47, 30, 26, 20, 8, 6, 6, 4, 3, 2, 1, 1, 1**. Năm kênh lớn chiếm **244/276 (88,4%)**; 9 kênh còn lại chỉ 32 video. Đây là giới hạn thực tế cho split theo kênh, chưa tính lọc quyền/media/lecture.

Chọn **ID nhỏ nhất theo thứ tự từ điển của mỗi kênh** trước khi gọi oEmbed. Cả 14/14 yêu cầu [YouTube oEmbed](https://www.youtube.com/oembed) trả HTTP 200, có title/author vào ngày kiểm tra. Các ID mẫu: `-KLa_lDkji0`, `2gU4F6ePhcM`, `-_31PoDRu28`, `0GRLhpMao3I`, `14iLLtnGsnE`, `64tsAc2ncJQ`, `Hed8nytXCOw`, `5Dlk1UgQSfQ`, `5L3Ao5KuCC4`, `DJYPdy0ITbo`, `g-JgA1hvJzA`, `Tu7G4btt4WU`, `wOI8RuhW7q0`, `7aURiz5J32A`. Đây là **metadata reachability**, không xác nhận video phát/giải mã được, giấy phép hiện tại, quyền tải hay quyền với nội dung bên thứ ba. Chưa kiểm tra 262 video còn lại.

[Tài liệu YouTube Data API](https://developers.google.com/youtube/v3/docs/videos) quy định `status.license` nhận `creativeCommon` hoặc `youtube`, cùng `status.privacyStatus`, `status.embeddable`; `videos.list` trả các phần được yêu cầu. [Hướng dẫn khởi tạo API](https://developers.google.com/youtube/v3/getting-started) yêu cầu dự án và thông tin xác thực. Phiên này không có kiểm tra `videos.list` được ủy quyền, nên không có bảng giấy phép hiện hành. Kể cả khi trường này là `creativeCommon`, cần đánh giá riêng quyền tác phẩm/ngoại lệ và [điều khoản YouTube](https://www.youtube.com/t/terms) đối với cách lấy, lưu, xử lý hoặc phát hành media.

## 2. GT và split trên subset CC BY

Đọc đầy đủ các cột `channel_id`, `video_id`, `chapter_titles`, `chapter_timestamps`, `duration` của 276 hàng text Parquet, không đọc audio/video:

- 276/276 có danh sách mốc chương không rỗng; mọi danh sách tăng nghiêm ngặt và các mốc nằm trong `duration` metadata.
- 265/276 có ít nhất hai mốc nội bộ; 225/276 có ít nhất ba. Trung vị danh sách mốc là 4, trung vị thời lượng là 820 giây.
- Trong 262 hàng, số title = số mốc + 1; 14 hàng có số title = số mốc + 2. Đây là khác biệt cấu trúc cần đối chiếu định nghĩa nhãn và video, **không tự động kết luận GT lỗi**.
- Không có `course_id` trong schema. Ví dụ title metadata từ mẫu một ID/kênh cho thấy nội dung rất khác nhau: YaleCourses “8. Imagism”, cs631apue “Advanced Programming in the UNIX Environment: Week 07, Segment 5”, Jeremy Howard “Lesson 3 - Deep Learning for Coders (2020)” và cả các video Q&A/giải thích chủ đề. Một kênh không tự bằng một khóa học; cũng chưa có nhãn lecture-only đáng tin cậy cho toàn subset.

Kiểm toán đầy đủ trước đó tìm **276 kênh chung train–test** trong YTSeg chính; 1.444/1.448 hàng test thuộc kênh xuất hiện ở train, và bốn `video_id` trùng train–validation. Subset CC BY chỉ là train, nên phải lập split tùy chỉnh nếu dùng nó. Việc này thay đổi thiết kế đã đăng ký trước và [kế hoạch](../260928-0949-rq1-completion-after-ytseg-audit/plan.md) yêu cầu sửa master plan trước D2/final test. Với 14 nhóm kênh rất lệch và chưa có ánh xạ khóa học/quyền hiện hành, **chưa thể nói còn đủ đơn vị độc lập cho một kết luận RQ1 chính thức**.

## 3. Nguồn đa khóa học thay thế

| Nguồn | Bằng chứng hiện hành | Cổng chưa qua | Đánh giá |
|---|---|---|---|
| [MITFLD](https://huggingface.co/datasets/robotwang/MITFLD) | Hugging Face revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec` liệt kê **538 MP4, 538 `frags/*.json`, 538 transcript** (1.617 tệp gồm README và danh sách ID). Một `frags` mẫu chứa mốc giây, MP4 cùng ID trả `HEAD 200` với `Content-Type: video/mp4`, `Content-Length: 586887760`; chưa tải/giải mã. Mười ID trải đều theo tên file đều trả oEmbed 200, title/author cho thấy nhiều chủ đề và `MIT OpenCourseWare`, nhưng đó chưa phải ánh xạ khóa học đã xác thực. | Repo không có tệp LICENSE hoặc tag license; card chưa khai báo `course_id`/split. Cần đối chiếu từng video với trang MIT OCW, ngoại lệ bên thứ ba, quyền MP4/GT và provenance của mốc. | **Ưu tiên pilot metadata + quyền**, vì đã có media và nhãn phân đoạn công bố, song chưa đủ điều kiện chính thức. Bộ ~177 GB theo card; chỉ lấy mẫu nhỏ sau khi cổng quyền qua. |
| [AVLectures CwS](https://github.com/Darshansingh11/AVLectures) | Tác giả mô tả **15 khóa có segmentation**, cấu trúc `videos/`, `subtitles/`, `segmentation/segments_ts.txt`. | Link archive tác giả [india-data.org](https://india-data.org/dataset-details/52e67bb5-5acd-438d-a13b-f255cee17432) hiện mở trang SPA, nhưng API `get-versions` không đăng nhập trả **401 `DFS Access token is required`**. Giấy phép CC0 của repo và badge CC BY-NC không xác nhận quyền từng MP4/GT. | Có course IDs và GT theo thiết kế, nhưng **blocked_access** với archive hiện hành. MIT001 local chỉ là một khóa. |
| [Open Yale Courses](https://oyc.yale.edu/help) | Yale nói phần lớn bài giảng là CC BY-NC-SA 3.0 và cho phép tải/chỉnh sửa video cho mục đích phi thương mại, với ngoại lệ nội dung bên thứ ba cần kiểm tra từng bài. Nhiều khóa có lecture video. | Chưa tìm thấy/kiểm chứng GT ranh giới chương ở cấp video đáp ứng scorer RQ1. Nếu tự gán nhãn mới, phải thay đổi quy tắc GT đã đăng ký và kiểm tra chất lượng độc lập. | Nguồn media tiềm năng, **chưa phải benchmark chương sẵn sàng**. |
| [Artificial Lecture Video Fragmentation Dataset](https://github.com/bmezaris/lecture_video_fragmentation) | 300 bài giảng tổng hợp và GT mốc nối fragment được phát hành cho nghiên cứu phi thương mại. | Tác giả ghi rõ **không phát hành video**, chỉ transcript và không nên dùng thị giác để truy ra mốc ghép. | Không phù hợp mục tiêu visual/acoustic thực của RQ1. |

Mọi vật liệu MIT OCW dùng tiếp phải theo [điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) và kiểm tra ngoại lệ nội dung của từng bài. Một tệp MP4 tải được từ kho thứ cấp chưa xác nhận bên phát hành có quyền cấp phép lại media.

## Quyết định nghiên cứu và bước có giá trị cao nhất

1. **Không công nhận YTSeg hoặc MITFLD là cohort chính thức hôm nay.** Chỉ có metadata/GT hình thức và mẫu endpoint tiếp cận; chưa có quyền hiện hành, xác thực course map hoặc D2.
2. Nếu có YouTube Data API credential được phép dùng, kiểm tra `status.license`, `privacyStatus`, `embeddable`, `snippet.channelId/title` cho **toàn bộ ID được chọn trước**, lưu ngày/nguồn và xử lý trường hợp ID bị thiếu. Sau đó rà quyền nội dung và cách truy cập; API flag một mình chưa đủ.
3. Ưu tiên một pilot **MITFLD 10–20 ID trải nhiều chủ đề**: tìm trang OCW/cụm khóa học cho từng ID, kiểm tra notice/ngoại lệ và quyền GT, kiểm tra mốc `frags` so với thời lượng, rồi mới cân nhắc tải một mẫu media được phép. Nếu không có ít nhất vài khóa độc lập đã xác minh, dừng tại diagnostic/no-selection.
4. Nếu muốn theo AVLectures CwS, cần quyền truy cập archive tác giả hoặc bản phân phối được phép; không thay bằng các file không rõ provenance. Open Yale cần GT chương độc lập hoặc quyết định thay đổi protocol.

## Câu hỏi chưa giải quyết

- Với các ID định đưa vào cohort, YouTube Data API hiện trả `status.license`/khả dụng gì, và phương thức lấy media nào được cho phép cho nghiên cứu này?
- MITFLD bao gồm chính xác bao nhiêu khóa học độc lập, quyền từng MP4/GT ra sao, và có đủ khóa sau lọc để lập train/validation/test có ý nghĩa thống kê không?
- AVLectures archive có thể cấp quyền truy cập và hồ sơ giấy phép theo thành phần hay không; nếu không, nguồn nào có cả media, GT độc lập và quyền đủ rõ?
