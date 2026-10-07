# YTSeg CS50P media audit: `-7xg8pGcP6w`

**Kết quả:** `pass_technical` cho file media và đối chiếu timeline với phụ đề publisher; **`hold_gt` và `hold_rights`** cho qualification toàn bộ. [Receipt JSON](./ytseg-260929-1543-cs50-media-receipt.json).

## Nguồn và tính toàn vẹn

- [Trang Harvard CS50P Week 2](https://cs50.harvard.edu/python/weeks/2/) liên kết cùng YouTube ID `-7xg8pGcP6w`, [MP4 360p](https://cdn.cs50.net/python/2022/x/lectures/2/lecture2-360p.mp4), và [SRT có mốc thời gian](https://cdn.cs50.net/python/2022/x/lectures/2/lang/en/lecture2.srt). Giảng viên trên trang: David J. Malan.
- Tải trọn file publisher vào `multimodal-lecture-summarizer/experiments/datasets/ytseg_qualification/-7xg8pGcP6w.mp4`: **963.059.289 byte**, bằng kích thước nguồn đã công bố qua HEAD. SHA-256 **`A58685B0AD2424AE6BC995521C7C5CB22B652D42FE964A0448E14C137E2CE719`**.
- `ffprobe`: video H.264 640×360, 24 fps, 116.322 frame; audio AAC stereo 48 kHz, 227.194 packet; thời lượng container **4.846,805333 s**. Giải mã **toàn bộ video và audio** bằng `ffmpeg -xerror` thành công, exit 0, không có diagnostic.
- Quét packet PTS: video 0–4.846,708333 s, audio −0,044–4.846,74 s; **0 PTS thiếu, 0 PTS lùi** cho cả hai stream.

## Đối chiếu timeline và transcript

Hàng TRAIN của revision YTSeg `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`, shard `train-00002-of-00004.parquet`, index 1594: thời lượng 4.847 s, 12 `raw_chapters`; `chapter_titles` bằng đúng 12 tiêu đề raw và 11 `chapter_timestamps` bằng các start sau mốc 0. Đây là nhận dạng cấu trúc release, **không** sửa hay tự ghép nhãn.

Đã so phụ đề SRT của publisher với text theo chapter trong `target_text_ts_ref` ở các mốc khóa trước kiểm media. Tỷ lệ là phần 5-gram từ cửa sổ SRT ±12 giây tìm được trong đoạn YTSeg chapter tương ứng; cửa sổ cắt qua ranh giới chapter làm tỷ lệ giảm.

| Mốc kiểm | Thời gian (s) | Chapter YTSeg | 5-gram khớp |
| --- | ---: | --- | ---: |
| 10% | 484,7 | while | 1,0000 |
| 50% | 2.423,5 | Iteration with Lists | 0,8556 |
| 90% | 4.362,3 | Nested Loops | 1,0000 |
| Ranh giới nội bộ đầu, kiểm +8 s | 24 | Loops | 0,9394 |
| Ranh giới nội bộ giữa, kiểm +8 s | 2.099 | Iteration with Lists | 0,7358 |
| Ranh giới nội bộ cuối, kiểm +8 s | 4.817 | Conclusion | 0,8404 |

Phụ đề mở đầu ở khoảng 24,16 s nói “This is CS50's Introduction to Programming with Python”; tương ứng chapter `Loops` bắt đầu 24 s. Các đoạn sau về vòng lặp, list, nested loops và lời kết đi theo đúng thứ tự. Mức khớp ở nhiều vị trí là chứng cứ timeline mạnh hơn sự gần bằng thời lượng. Receipt giữ trích đoạn ngắn, số cue và khoảng thời gian từng cửa sổ.

Hai trường `text_wt`/`text_wl` của cùng hàng mở bằng nội dung vector calculus không thuộc CS50P. Chưa xác định ý nghĩa các trường này từ code upstream; việc so transcript chỉ dùng `text_ref`/`target_text_ts_ref` và publisher SRT. Không coi hai trường kia là transcript tham chiếu của video này.

## Cổng còn giữ

- `hold_gt`: revision công khai không có mã upstream chuyển đổi ba dạng quan hệ title–timestamp. Sự khớp raw fields ở video này không tự giải quyết yêu cầu GT chung.
- `hold_rights`: [giấy phép khóa CS50P](https://cs50.harvard.edu/python/license/) là CC BY-NC-SA 4.0. Chưa kiểm đủ quyền mọi thành phần hình/âm thanh và ngoại lệ trong toàn file, nên chưa nâng quyền resource lên `pass`.
- Chưa kiểm fingerprint nội dung với pilot ở audit này; parent qualification ledger phải xử lý trước split.

## Câu hỏi chưa giải quyết

1. Upstream có mã chuyển đổi GT chính xác cho revision này không?
2. Có chứng cứ quyền cho mọi thành phần của video theo phạm vi sử dụng nội bộ không?
3. Kiểm trùng nội dung với pilot có phát hiện bài trùng/phiên bản khác không?
