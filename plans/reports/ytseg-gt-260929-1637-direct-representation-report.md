# YTSeg GT: kiểm trực tiếp 10 hàng đã khóa

**Kết luận:** Cổng `hold_gt` do thiếu mã tiền xử lý upstream **không còn cần cho 10 video TRAIN đã khóa**, nếu protocol chấp nhận đọc biểu diễn GT đã phát hành. Đây là đề xuất cập nhật quyết định, chưa sửa manifest/protocol khóa. Các cổng quyền resource vẫn độc lập và chưa qua; số video vượt **toàn bộ** cổng không đổi chỉ nhờ kết quả GT.

[Receipt JSON theo từng ID](./ytseg-gt-260929-1637-direct-representation-receipt.json) ghi shard, hàng, SHA-256 và mọi phép kiểm Boolean, không lưu transcript.

## Nguồn và phép kiểm

- Đọc trực tiếp bốn file `text/train-0000{0..3}-of-00004.parquet` thuộc [revision YTSeg `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`](https://huggingface.co/datasets/retkowski/ytseg/tree/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970/text). File đặt trong `multimodal-lecture-summarizer/experiments/datasets/ytseg_qualification/text/` (ignored). SHA-256 lần lượt: `feb4ae49080e43128315ba4c5338eca339a17b7fc7b8e66628d9cf539310f691`, `004434130e68aa9f48f6cc75961161f25eea1dd0c42e7c2ebc0a7887efbc347b`, `1ef803d268644ef6e19e201510893a1234c2f55f3f0d1a8883a52da85c837eaf`, `7c8456986faf1782f4fdb855370fdb790f53bccbfeff3ecad5ef4f166ad3c7a4`. Cả bốn khớp LFS SHA-256 trong [receipt nguồn trước đó](./ytseg-260929-pinned-text-metadata-audit-receipt.json).
- Chọn đúng 10 `video_id` TRAIN từ [cohort lock](./ytseg-260929-1543-pre-media-cohort-lock.csv), quét cả bốn shard; mỗi ID đúng một hàng. `raw_chapters` là mảng struct có `start_time`, `end_time`, `title`; `target_ts`, `target_text_ref`, `target_text_ts_ref` là chuỗi thực có trong **từng hàng**. Đây là bằng chứng hàng Parquet, mạnh hơn khai báo schema trên [dataset card](https://huggingface.co/datasets/retkowski/ytseg/blob/main/README.md).
- Với từng hàng: tất cả tiêu đề không rỗng; `0 <= start < end <= duration`; chapter đầu tại 0, mỗi `end_time` bằng `start_time` kế tiếp, chapter cuối bằng `duration` *trong metadata*. Parse toàn bộ marker `[CSTART] hh:mm:ss - title [CEND]` của `target_ts`: số marker, giây bắt đầu và tiêu đề khớp `raw_chapters`; dựng lại từ `raw_chapters` cho kết quả **bằng chính xác toàn chuỗi `target_ts`**, kể cả xuống dòng. `target_text_ref` chứa đủ marker tiêu đề và `target_text_ts_ref` chứa đủ marker thời gian–tiêu đề tương ứng. `chapter_titles` bằng raw titles; `chapter_timestamps` bằng raw starts bỏ mốc đầu 0. Không zip hai danh sách rời.

| `video_id` | Shard, row (0-based) | Số chapter | `raw_chapters` đầy đủ/liên tục | `target_ts` khớp chính xác | `target_text_*` đủ marker |
|---|---:|---:|---|---|---|
| `-dOX_4lI6HY` | 0, 1 | 22 | Có | Có | Có |
| `MoEaRpLNo9A` | 1, 3644 | 10 | Có | Có | Có |
| `-7xg8pGcP6w` | 2, 1594 | 12 | Có | Có | Có |
| `tCKk22kaZi4` | 0, 1607 | 12 | Có | Có | Có |
| `3sB64Au76h0` | 1, 2105 | 33 | Có | Có | Có |
| `Th2N_rDfkDw` | 0, 2968 | 24 | Có | Có | Có |
| `alLh1Jdqwvg` | 2, 2667 | 19 | Có | Có | Có |
| `xsO2Ip6eiaY` | 2, 2762 | 16 | Có | Có | Có |
| `ksyY5wa5_50` | 1, 3600 | 21 | Có | Có | Có |
| `kiCNa95DnnE` | 0, 2257 | 26 | Có | Có | Có |

Tổng **195 chapter / 10 hàng**. Từng `raw_chapters.end_time` cuối bằng metadata `duration`; điều này không tự chứng minh trùng thời lượng MP4. [Audit media](./ytseg-260929-1543-locked-cohort-final-qualification-report.md) đã kiểm timeline bằng file và transcript ở nhiều vị trí. Riêng `text_wt`/`text_wl` của CS50P từng thấy nội dung khác bài; **không** dùng chúng thay `text_ref`.

## Quyết định target cần ghi rõ trong amendment

| Xếp hạng | Target / adapter | Ưu điểm | Rủi ro và điều kiện |
|---|---|---|---|
| **1** | Dùng nguyên `target_ts` của revision ghim cho đầu ra mốc–tiêu đề | Đã ghép sẵn; khớp raw ở 10/10 hàng; ít logic chuyển đổi, tương thích biểu diễn đã xử lý | Chỉ cho mốc bắt đầu, không có `end_time`; phải nêu rõ metric/endpoint nào dùng target này. Không suy diễn quy tắc cho toàn bộ release. |
| **2** | Adapter đọc trực tiếp `raw_chapters` (`start_time`, `end_time`, `title`) | Có interval tường minh, không cần mã upstream để ghép nhãn | **Đổi target** từ nhãn đã xử lý sang raw: bắt buộc amendment, phiên bản adapter, kiểm metric và so sánh; không dùng âm thầm cho D2 hay so kết quả như cùng một target. |
| **3** | Tiếp tục chờ mã upstream để tái tạo `chapter_titles` + `chapter_timestamps` | Giữ nguyên giả định cũ | Không cần thiết cho 10 ID khi target trực tiếp đã được xác minh; làm chậm qualification. Chỉ giữ `hold` với hàng/biểu diễn còn mơ hồ. |

**Đề xuất:** cập nhật `gt_gate=pass_direct_published_target` cho 10 hàng, nêu rõ target mặc định là `target_ts` nguyên bản; nếu endpoint cần interval, ghi amendment riêng chọn `raw_chapters` làm target và kiểm lại trước D2. Giữ nguyên bản [lock](./ytseg-260929-1543-pre-media-cohort-lock.csv), [protocol](./ytseg-260929-1543-pre-media-cohort-protocol.md) và [manifest quyết định cũ](./ytseg-260929-1543-resource-gate-manifest.csv) như snapshot lịch sử; xuất bản quyết định cập nhật có ngày/receipt mới. Kết quả này không cấp quyền dùng media và không chọn mô hình hay chạy official RQ1.

## Giới hạn và câu hỏi chưa giải quyết

1. Những hàng YTSeg ngoài 10 ID, nhất là hai dạng đếm khác, chưa được kiểm đầy đủ theo adapter này; không mở rộng kết luận toàn release.
2. Metric/đầu ra RQ1 chính thức cần mốc bắt đầu hay interval có `end_time`? Quyết định đó xác định target mặc định và amendment tương ứng.
3. Quyền nghiên cứu nội bộ của từng video và quyền phát hành lại thành phần vẫn cần hai cổng riêng; kết quả GT không giải quyết chúng.
