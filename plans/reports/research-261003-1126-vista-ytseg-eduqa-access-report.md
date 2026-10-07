# Khả năng lấy VISTA, YTSeg và nhận diện EduViQA/EduVidQA

Ngày kiểm tra: 2026-10-03. Phạm vi: nguồn phát hành hiện tại và snapshot trong workspace; không tải media mới, không chấm chất lượng nhãn.

## Kết luận

| Câu hỏi | Kết luận thực tế |
|---|---|
| VISTA có lấy được media không? | **Có.** Sau lần Chrome tự động bị chặn tại CDN, người dùng tải thủ công một MP4 validation. SHA-256 khớp đúng trang phát hành và giải mã toàn bộ thành công. Điều này chứng minh một tệp/subset có thể lấy qua Chrome hiện tại; chưa chứng minh tải tự động hoặc toàn bộ 1,93 TB. |
| YTSeg có đủ video đúng bản không? | Dataset phát hành annotation/audio cho 19.299 video và script lấy video từ YouTube, không phát hành snapshot MP4 cố định. Workspace hiện có 10 MP4, cả 10 ID khớp annotation `text/train` ở revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`, nhưng chỉ thuộc 2 kênh. ID trùng không chứng minh byte, bản cắt hay thời điểm video khớp bản lúc gắn nhãn. Chưa đo được số video còn tải được trong cohort lớn. |
| 20 video EduViQA cục bộ là phần nào của EduVidQA? | **Không phải subset của EduVidQA.** Thư mục cục bộ khớp `UIAIC/EduViQA` (còn gọi EduVQA-Alpha): 20 video tiếng Anh/Ba Tư, 883 Q&A đếm trực tiếp từ `q_and_a.json`, cùng tên tệp chunking của nguồn này. EduVidQA công bố tại `sourjyadip/eduvidqa-emnlp25` là bộ khác: 296 video khoa học máy tính, 5.252 Q&A, gồm dữ liệu synthetic và test câu hỏi thực. |

## Cơ sở và giới hạn

- [VISTA dataset card](https://huggingface.co/datasets/dongqi-me/VISTA/blob/main/README.md) ghi cấu trúc `videos/{train_part1,train_part2,val,test}` cùng JSON metadata. [Trang files](https://huggingface.co/datasets/dongqi-me/VISTA/tree/main) liệt kê `videos/` nhưng yêu cầu access form. Local `experiments/registry/research_decisions.yaml` vẫn ghi `vista_full.access_status: unavailable` vì 1,93 TB/18.606 video vượt ngân sách cục bộ; đây là đánh giá tải **toàn bộ**, không phủ định khả năng lấy một subset.
- [YTSeg dataset card](https://huggingface.co/datasets/retkowski/ytseg) ghi 16.404 train, 1.447 validation, 1.448 test; audio nhúng có sẵn, video phải lấy bằng script. Cache Parquet local ghi revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`. Phép so ID local đọc toàn bộ 4 shard train và khớp 10/10 tên MP4, 2 `channel_id`.
- [UIAIC/EduViQA](https://huggingface.co/datasets/UIAIC/EduViQA) ghi 20 video hai ngôn ngữ, `q_and_a.json`, `video_transcripts/`, `video_chunkings/`, `Videos/`, trùng cấu trúc thư mục local. [EduVidQA EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1760/) ghi 296 video và 5.252 Q&A; [repo chính thức](https://github.com/sourjyadip/eduvidqa-emnlp25) có dữ liệu QA trong `data/`, còn video/transcript cần lấy riêng.
- Kiểm tra HEAD VISTA từ shell không thành công vì proxy sandbox tới `127.0.0.1:9`; đây không phải phản hồi 401 từ VISTA. Chưa thử tải media YTSeg hàng loạt hay tải dữ liệu EduVidQA.

## Kiểm tra tiếp cùng ngày

- Trang VISTA mở trong trình duyệt hiện **chưa đăng nhập** và hiện thông báo `Gated dataset — You can list files but not access them`. Không có HF token trong môi trường Python. Do đó quyết định phê duyệt tài khoản ghi trong master chưa thể chuyển thành phép thử tải ở phiên hiện tại.
- Cả 10 MP4 YTSeg cục bộ đều khớp `video_id` trong 4 shard `text/train` đã ghim. So `ffprobe` với cột `duration`: chênh lệch từng video nằm trong **−0,5 đến +0,4 giây**; có 9–32 chapter/video. Đây là tín hiệu media tương ứng với annotation theo ID và thời lượng, nhưng chưa chứng minh mọi frame/mốc chương đúng bản gốc.
- [Script tải video tại revision đã ghim](https://huggingface.co/datasets/retkowski/ytseg/blob/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970/download_videos.py) nhập `from load_data import get_data`, trong khi [file tree của revision](https://huggingface.co/datasets/retkowski/ytseg/tree/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970) không có `load_data.py`. Không thể xem lệnh trong card là script độc lập chạy ngay; có thể lấy ID từ Parquet đã ghim rồi dùng `yt-dlp`, sau khi có môi trường mạng phù hợp.
- [Repo EduVidQA chính thức](https://github.com/sourjyadip/eduvidqa-emnlp25/tree/main/data) cung cấp 3 CSV: `real_world_test.csv`, `synthetic_test.csv`, `synthetic_train.csv`. File real-world có cột `url,id,question,answer,timestamp`; README hướng dẫn lấy video và transcript từ YouTube riêng. Có thể lấy annotation công khai trước mà không cần tải media, nhưng chưa có 296 video cục bộ.

## Thử truy cập media thực tế

- Lấy mẫu cố định **12 video train từ 12 `channel_id` khác nhau**: sắp kênh theo SHA-256, chọn ID có SHA-256 nhỏ nhất trong mỗi kênh. Dùng `yt-dlp 2026.07.04` chỉ lấy metadata, không tải media. Kết quả: **10 public, 1 unlisted, 1 private**. Cả 11 video truy cập metadata được có `duration` YouTube bằng đúng `duration` annotation theo giây. Đây là phép thử đường truy cập nhỏ, không phải ước lượng tỷ lệ toàn bộ YTSeg hay lecture subset.
- Tải thử MP4 của video public `dzm9dIRE8Is` bằng định dạng 18 (360p, audio+video) trả **HTTP 403** ở bước lấy byte. Thử lại định dạng 134 (360p video only) cùng video cũng **403**. Video public thứ hai `BP6bLvfl0V0`, định dạng 18, cũng **403**. Metadata và danh sách format xem được không chứng minh rằng media tải được ở mạng hiện tại. Không tạo được MP4 mới từ các lượt thử này.
- Trang YouTube của `dzm9dIRE8Is` mở và phát được trong trình duyệt, hiển thị đúng 2:15. Tuy vậy thử lưu từ phần tử `<video>` bằng công cụ trình duyệt hết thời gian chờ; khả năng phát trực tuyến **khác** khả năng lưu bản media để benchmark.
- VISTA: trình duyệt trong ứng dụng **signed out** và Python không có Hugging Face token. Theo yêu cầu người dùng, thử bằng **Chrome** đang đăng nhập: mở được thư mục `videos/val` và thấy `10101-icml-2021.mp4` kích thước 25,4 MB. Nhấp liên kết tải chuyển sang CDN và báo `ERR_BLOCKED_BY_CLIENT`. Không có file ở Downloads sau thử. Điều này chứng minh tài khoản Chrome xem được listing gated nhưng **chưa chứng minh đường tải byte MP4**; không thử vượt chặn của Chrome.

## Tải lại bằng Chrome và kiểm tra file người dùng nhận

- Người dùng tải thủ công `C:\Users\hung\Downloads\10101-icml-2021.mp4` từ VISTA validation. Kích thước thực **25.443.624 byte**. SHA-256 thực `6115f963bd5dccdce41cf87000426b23648816a0adaeb9de67ae24100dd853e1`, **khớp SHA-256 công bố trên trang tệp**. `ffprobe` đọc được thời lượng **309,96 giây**, video **H.264 1280×720, 25 fps**, audio **AAC**. `ffmpeg -xerror` giải mã toàn bộ hai stream với exit code 0, không in lỗi. Kết luận hẹp: **một MP4 VISTA đã tải thành công và dùng được**. Việc tải bằng công cụ Chrome tự động hoặc CLI vẫn chưa chứng minh.
- YTSeg: thử lại `dzm9dIRE8Is` bằng yt-dlp với `player_client=web`; extractor trả `Only images are available for download`, không có MP4 phù hợp. Cộng với các lượt 403 trước đó, môi trường CLI hiện chưa lấy được media YTSeg mới. Không có file YTSeg mới trong thư mục probe.

## Hướng thực hiện

1. Với VISTA, thử **một MP4 ở validation** bằng tài khoản Hugging Face đã được duyệt trong môi trường có mạng; đo dung lượng, thời gian và decode. Nếu khả thi, chốt subset theo ngân sách. Không tải 1,93 TB vào workspace.
2. Với YTSeg, chọn cohort ứng viên từ annotation đã ghim, rồi thử lấy video theo ID và so thời lượng/mốc chương với bản phát hành. Mười MP4 local chỉ là phép thử đường media, không là mẫu đánh giá đủ rộng.
3. Với RQ3 theo master, tải đúng `sourjyadip/eduvidqa-emnlp25/data` nếu muốn dùng EduVidQA 5.252 Q&A. Ghi `UIAIC/EduViQA` là bộ phụ riêng; không gộp số lượng của hai nguồn.

## Câu hỏi chưa giải quyết

- Có thể lặp lại phép tải VISTA cho một cohort giới hạn qua quy trình tự động và ngân sách lưu trữ rõ ràng không? Một file tải thủ công đã đạt.
- Khi dùng mạng/phiên YouTube phù hợp, byte MP4 của YTSeg có tải được không? Bao nhiêu video trong cohort định dùng còn truy cập được và khớp annotation?
