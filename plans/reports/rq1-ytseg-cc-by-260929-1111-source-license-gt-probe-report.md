# RQ1 YTSeg CC BY: probe quyền nguồn và GT đã phát hành

Ngày kiểm: 2026-09-29. Phạm vi: **10 hàng đầu** của cấu hình `text`, split `train` trong [YTSeg CC BY](https://huggingface.co/datasets/retkowski/ytseg-cc-by). Chỉ đọc metadata; không tải video, không xem/chấm nội dung, không tạo nhãn. [Receipt 10 video](./rq1-ytseg-cc-by-260929-1111-first-ten-source-license-receipt.json) lưu ID, metadata giấy phép/truy cập và đối chiếu chapter từ nguồn hiện hành.

## Bằng chứng

[Card YTSeg CC BY](https://huggingface.co/datasets/retkowski/ytseg-cc-by) nói bộ con có **276 video / 14 kênh / 99,1 giờ**, tất cả được tác giả lọc từ train qua trạng thái `creativeCommon` của YouTube Data API; chỉ có split train. Revision repo quan sát: `282b0a039e82ed78f85adc1f99a94f87e1d47a97`. Hàng lấy từ Dataset Viewer API chưa ghim vào revision này, nên receipt ghi riêng giới hạn đó.

[Quét toàn bộ metadata 276 hàng](./rq1-ytseg-cc-by-260929-1111-full-metadata-structural-receipt.json): 276 `video_id` duy nhất, 14 kênh, 99,144 giờ. Cả 276 dãy mốc nội bộ đều tăng, dương và nằm trong duration ghi ở HF. **262/276** hàng có số tiêu đề bằng số mốc nội bộ + chương đầu tại 0. **14/276** hàng có thêm tiêu đề cuối `Outro` nhưng không có mốc ghép tương ứng trong `chapter_timestamps`/`target_ts`; không tự tạo mốc cho tiêu đề đó hoặc dùng nó làm GT thời gian. Tổng thời lượng của video ngắn nhất ở mỗi kênh là **5,57 giờ**, chỉ cho thấy cap 12 giờ không tự loại trừ việc lấy một video/kênh; chưa chứng minh quyền, media, sức mạnh split hay phù hợp nội dung.

Probe metadata hiện hành của 10 ID đầu: **10/10 public**, **10/10 hiển thị Creative Commons Attribution**, **10/10 channel ID và thời lượng khớp** metadata HF trong sai số dưới 2 giây. Mẫu này có **4 kênh, 3,042 giờ**; không đại diện toàn bộ 276 video. Không kiểm nội dung/hình/âm thanh hay quyền thành phần bên trong video.

Đối chiếu mốc đã phát hành: **10/10** dãy `chapter_timestamps` nội bộ HF bằng các chapter start sau mốc 0 mà `yt-dlp` trích từ trang YouTube hiện hành. **9/10** dãy tiêu đề bằng nhau. Với `zAQYtolfB4g`, HF ghi tiêu đề chương đầu `Intro` còn `yt-dlp` trả placeholder `<Untitled Chapter 1>`; bốn tiêu đề còn lại và các mốc thời gian khớp. Placeholder có thể do công cụ trích xuất tạo, nên chưa kết luận trang YouTube thực sự hiển thị câu này. Không tự thay tiêu đề nào; bài này không thể coi toàn bộ tiêu đề HF đã được đối chiếu nguyên xi với nguồn hiện hành. Đây là kiểm provenance, không xác nhận onset ngữ nghĩa hoặc tình trạng GT tại thời điểm HF tạo dataset.

## Hệ quả quyền và protocol

[YouTube Help](https://support.google.com/youtube/answer/2797468?hl=en) xác nhận CC Attribution là một lựa chọn giấy phép video và yêu cầu ghi công khi tái sử dụng. Tuy nhiên [YouTube Terms, Permissions and Restrictions](https://www.youtube.com/t/terms) hạn chế việc tải nội dung và truy cập tự động nếu không được Service cho phép hoặc có quyền theo điều khoản nêu ở đó. **CC hiển thị ở cấp video chưa đủ để kết luận pipeline tải bằng `yt-dlp` được phép theo điều khoản nền tảng.** Vì vậy không tải media, không chuyển bất kỳ video nào sang D2, không coi probe là `rights_pass` đầy đủ.

Bộ con 276 video chỉ có train và 14 kênh; không thay trực tiếp mục tiêu `n=300` với official split của [master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md). Nếu dùng làm đánh giá đa phương thức riêng, phải sửa protocol trước chọn mô hình, định nghĩa split theo kênh/khóa và kiểm cap 12 giờ sau khi quyền truy cập media được giải quyết. Không suy từ metadata CC BY rằng tất cả 276 còn công khai hoặc cùng có GT hiện hành khớp.

## Câu hỏi chưa giải quyết

1. Có đường nhận video hợp điều khoản YouTube hoặc bản video do chủ quyền cung cấp trực tiếp cho 10 ID này và các ứng viên khác không?
2. Sau kiểm toàn bộ 276 về trạng thái nguồn hiện hành, quyền thành phần và cap 12 giờ, còn bao nhiêu kênh/video độc lập cho split đã đăng ký trước? Mười bốn hàng có `Outro` không ghép timestamp phải được xử lý theo đúng nguồn/contract, không bổ sung nhãn.
3. Official RQ1 sẽ giữ YTSeg split gốc cho text/audio và dùng CC BY subset như nhánh đa phương thức riêng, hay cần protocol amendment khác?
