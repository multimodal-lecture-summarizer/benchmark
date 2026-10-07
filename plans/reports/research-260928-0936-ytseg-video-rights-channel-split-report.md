# Nghiên cứu: quyền video YTSeg và split độc lập theo kênh/khóa học

Ngày kiểm tra: 2026-09-28 (Asia/Bangkok). Phạm vi: trạng thái nguồn hiện hành và toàn bộ metadata 19.299 hàng của YTSeg; không tải, phát hay tái phân phối video. Đây là đánh giá bằng chứng phục vụ thiết kế benchmark, không phải ý kiến pháp lý.

## Kết luận

**Chưa đủ bằng chứng để duyệt sử dụng video của toàn bộ YTSeg cho benchmark đa phương thức.** [Thẻ dữ liệu YTSeg](https://huggingface.co/datasets/retkowski/ytseg) gắn CC BY-NC-SA 4.0 cho bộ dữ liệu nhưng ghi rõ tác giả **không sở hữu bản quyền video**. Các video được truy xuất từ YouTube; giấy phép bộ dữ liệu không tự cấp quyền với từng video, và [điều khoản YouTube](https://www.youtube.com/t/terms) có hạn chế riêng đối với tải xuống, sử dụng và truy cập tự động. Chưa kiểm tra giấy phép hiện hành, trạng thái truy cập và ngoại lệ nội dung cho từng video. Vì vậy chưa thể coi tập video là đã thông qua kiểm toán quyền để tải/xử lý/công bố hàng loạt.

**Split train/validation/test chính thức không độc lập theo kênh.** Kiểm tra đủ 19.299 hàng cho thấy 276 kênh xuất hiện đồng thời trong train và test; 1.444/1.448 hàng test thuộc các kênh cũng có trong train. Schema không có `course_id`, nên chưa thể xác minh độc lập theo khóa học. Có thể lập *split tùy chỉnh theo kênh* từ metadata, nhưng không thể gọi split chính thức là đánh giá khái quát hóa sang kênh/khóa học mới. Một split theo khóa học cần ánh xạ khóa học và kiểm tra thủ công hoặc metadata bổ sung.

## Phạm vi và phương pháp

- Đối chiếu [dataset card chính](https://huggingface.co/datasets/retkowski/ytseg), [bộ con CC BY](https://huggingface.co/datasets/retkowski/ytseg-cc-by), [hướng dẫn giấy phép YouTube](https://support.google.com/youtube/answer/2797468?hl=en) và [điều khoản dịch vụ YouTube](https://www.youtube.com/t/terms) vào ngày kiểm tra.
- API Hugging Face trả revision bộ chính `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970` (cập nhật 2026-07-20), bộ CC BY `282b0a039e82ed78f85adc1f99a94f87e1d47a97` (cập nhật 2026-06-11). Đọc metadata repo và script tải ở revision bộ chính. Không thấy tệp `.mp4`, `.mkv`, `.webm` hoặc `load_data.py` trong danh sách tệp của revision đó; [script `download_videos.py`](https://huggingface.co/datasets/retkowski/ytseg/resolve/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970/download_videos.py) nhập `load_data`, nên lệnh chạy độc lập trong card còn thiếu một phụ thuộc ở revision đã kiểm tra. Chưa chạy script.
- Đọc **toàn bộ** sáu tệp text Parquet được [Dataset Viewer liệt kê](https://datasets-server.huggingface.co/parquet?dataset=retkowski/ytseg), chỉ các cột `channel_id` và `video_id`. Đây là snapshot của dịch vụ Parquet tại ngày kiểm tra; endpoint chuyển đổi này không được ghim theo Git revision ở trên. Không đọc transcript, âm thanh hay video. Cách đọc khác với probe 80 hàng trong `experiments/scripts/rq1_candidate_ledger.py`.
- Đọc Parquet text của [bộ CC BY](https://datasets-server.huggingface.co/parquet?dataset=retkowski/ytseg-cc-by) theo cùng cách để kiểm tra số nhóm kênh.

## Quyền sử dụng: ba lớp phải tách riêng

| Lớp | Bằng chứng hiện có | Kết luận hiện tại |
|---|---|---|
| Gói dữ liệu YTSeg | Card ghi CC BY-NC-SA 4.0; cấu hình text/audio và các split được công bố | Điều kiện của gói dữ liệu cần tuân thủ; không suy ra quyền đối với MP4 YouTube. Quyền và giới hạn đối với âm thanh được phân phối cũng cần rà soát theo mục đích sử dụng cụ thể. |
| Video gốc | Card ghi tác giả không sở hữu bản quyền video. Video không nằm trong danh sách tệp của repo đã kiểm tra; script dùng `yt_dlp` để lấy từ YouTube | Chưa có giấy phép theo từng video, bằng chứng được phép tải/xử lý, hoặc danh sách video còn truy cập được. Không xác nhận “video YTSeg đã được cấp phép”. |
| Nền tảng YouTube | [Giấy phép chuẩn là mặc định; CC BY là tùy chọn do người đăng chọn](https://support.google.com/youtube/answer/2797468?hl=en). [Điều khoản dịch vụ](https://www.youtube.com/t/terms) hạn chế tải và truy cập tự động ngoài các trường hợp được cho phép | Cần kiểm tra cả quyền tác phẩm lẫn cách truy cập. Một nhãn CC BY tại thời điểm thu thập không tự chứng minh thao tác tải hiện tại phù hợp điều khoản nền tảng. |

Tác giả YTSeg đã công bố [bộ con `ytseg-cc-by`](https://huggingface.co/datasets/retkowski/ytseg-cc-by): theo card, họ dùng YouTube Data API `videos.list(part=status)` để kiểm tra **video trong train**, tìm được 276 video (1,7%) từ 14 kênh có nhãn CC BY tại thời điểm kiểm tra; bộ con chỉ có train và được phát hành với nhãn CC BY 4.0. Kiểm tra Parquet hiện tại xác nhận 276 `video_id` khác nhau, 14 `channel_id`; phân bố số video/kênh là 121, 47, 30, 26, 20, 8, 6, 6, 4, 3, 2, 1, 1, 1. Đây là ứng viên nhỏ hơn để *tiếp tục kiểm toán từng video*, không phải bằng chứng giấy phép hiện hành cho mọi video hay một test độc lập được cung cấp sẵn. Giấy phép CC BY của video, giấy phép gói dữ liệu và điều khoản truy cập YouTube phải được ghi riêng.

## Kiểm toán split hiện hành

| Split | Số hàng | `video_id` duy nhất | `channel_id` duy nhất | Hàng lặp `video_id` trong split |
|---|---:|---:|---:|---:|
| Train | 16.404 | 16.387 | 386 | 17 |
| Validation | 1.447 | 1.446 | 281 | 1 |
| Test | 1.448 | 1.448 | 280 | 0 |
| **Tổng** | **19.299** | — | **393 kênh toàn bộ** | — |

Không có `channel_id` hoặc `video_id` trống trong các hàng đã đọc. Các giao giữa split:

| Cặp split | Kênh chung | Hàng split thứ nhất thuộc kênh chung | Hàng split thứ hai thuộc kênh chung | `video_id` chung |
|---|---:|---:|---:|---:|
| Train–test | 276 | 16.073/16.404 train | 1.444/1.448 test | 0 |
| Validation–test | 238 | 1.403/1.447 validation | 1.406/1.448 test | 0 |
| Train–validation | 278 | 16.075/16.404 train | 1.444/1.447 validation | 4 |

Có 238 kênh xuất hiện ở cả ba split. **Không trùng `video_id` giữa train và test** theo metadata, nhưng việc một kênh xuất hiện ở cả hai vẫn làm mất tính độc lập theo nguồn. Bốn `video_id` giao giữa train và validation cần được loại trùng hoặc nhóm cùng một phía trước khi dùng validation để chọn mô hình.

Nếu giữ nguyên **toàn bộ test chính thức** rồi bỏ khỏi train/validation mọi hàng thuộc kênh của test, chỉ còn 331 hàng train (110 kênh) và 44 hàng validation (43 kênh); hai phần còn lại vẫn chung 40 kênh. Nếu tiếp tục giữ toàn bộ 331 hàng train, chỉ **3 hàng validation** thuộc kênh không có trong cả train lẫn test. Đây là phép lọc minh họa mức hao hụt, không phải split đề xuất. Một split theo kênh khả dụng cần tái chia nhóm và công bố tỷ lệ, phân phối nội dung, số nhóm độc lập, video lặp cùng seed/manifest.

Không có trường `course_id` trong schema đã đọc. `channel_id` có thể đại diện nhà phát hành, nhưng một kênh có thể đăng nhiều khóa học và một khóa học có thể hiện diện ở nhiều kênh. Vì vậy phép tách theo kênh chỉ là **proxy**, chưa chứng minh course-disjoint. Metadata đã kiểm tra cũng không có nhãn máy đọc được đủ để chọn chắc chắn tập “lecture/science” cho benchmark chương.

## Hệ quả cho RQ1 và bước tiếp theo

1. Với văn bản/âm thanh theo split chính thức, chỉ báo cáo đúng loại đánh giá **video-disjoint train–test theo `video_id`**, đồng thời nêu rõ kênh chồng lấn; xử lý bốn ID train–validation trùng trước mọi model selection. Không quảng bá kết quả là channel/course-independent.
2. Trước khi mở rộng benchmark **visual hoặc kết hợp đầy đủ** trên YTSeg, tạo ledger theo từng video: URL/ID, người đăng, nhãn giấy phép và thời điểm kiểm tra, ngoại lệ nội dung, điều kiện truy cập/tải, trạng thái phát, provenance và bản ghi quyết định. Bắt đầu từ tập ứng viên nhỏ; không suy diễn từ nhãn dataset sang quyền MP4.
3. Nếu mục tiêu là khái quát hóa nguồn, lập split mới theo `channel_id` đã khóa seed và `video_id`, rồi gắn `course_id` bằng bằng chứng nguồn cho từng nhóm. Kiểm tra phân bố chủ đề và số kênh hiệu dụng; bộ CC BY chỉ có 14 kênh và không có test chính thức nên khả năng suy luận thống kê sẽ hạn chế.
4. Chỉ đóng băng D2/GT chính thức sau khi tập media đủ quyền, truy cập được, cùng đơn vị đánh giá, có GT chương độc lập và split được khai báo trước. Chẩn đoán MIT001 một khóa học và 35 video hiện có không thay thế kiểm toán/split YTSeg.

## Câu hỏi chưa giải quyết

- Video nào trong ứng viên YTSeg còn truy cập được hôm nay, mang giấy phép nào ở cấp video, và có quyền tải/xử lý/lưu/công bố kết quả theo cách benchmark dự định hay không?
- Có metadata đáng tin cậy để gán `course_id`, xác minh cùng khóa học qua nhiều kênh và lọc lecture/science hay không?
- Sau kiểm toán quyền và lọc media, còn bao nhiêu video/kênh/khóa học có GT phù hợp để lập train, validation, test độc lập và đủ sức đánh giá RQ1?
