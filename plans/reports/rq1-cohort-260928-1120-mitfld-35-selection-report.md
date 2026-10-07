# RQ1 MITFLD: cohort ứng viên 35 bài

**Ngày:** 2026-09-28. **Trạng thái:** `candidate_only_not_d2`. Danh sách này chốt ID để kiểm tra quyền, căn chỉnh media và GT trên đúng tập được chọn. Đây chưa phải D2 hoặc kết quả RQ1 official.

## Quy tắc chọn

- Nguồn: [course map 538 hàng](./mitfld-260928-1031-normalized-course-map.csv), SHA-256 `b9fced1fb98d24c21fc0bc0480bcf2f18acfc8dc125e57276203b93e7d9c2a62`, revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec`.
- Giữ `lecture_video_candidate_course`; loại tiêu đề có `Problem Session` và 10 ID đã dùng trong pilot. Còn 459 ứng viên thuộc 21 khóa.
- Seed `rq1-mitfld-qualification-20260928`; sắp khóa và ID bằng SHA-256 theo [script chọn](../../multimodal-lecture-summarizer/experiments/scripts/select_mitfld_rq1_cohort.py). Gán khóa vào train/validation/final_test trước khi xét bài: 11/5/5 khóa. Chọn một bài cho mỗi khóa, thêm bài thứ hai ở 8/3/3 khóa có nhiều ứng viên nhất trong từng split. Tổng 19/8/8 bài. Không dùng điểm mô hình hay nhãn đã xem để chọn.
- [Danh sách 35 bài](./mitfld-rq1-35-260928-1120-selected.csv) và [hàng đợi thay thế 424 bài](./mitfld-rq1-35-260928-1120-reserve-order.csv) cùng giữ `review_flag`. Nếu bài không đạt, dùng ID chưa kiểm tiếp theo trong **cùng khóa và split**, ghi lý do loại và giữ ID gốc trong attrition; không thay theo điểm mô hình. [Receipt](./mitfld-rq1-35-260928-1120-selection-receipt.json) khóa seed, revision, quy tắc và SHA-256 của hai CSV.

## Danh sách đã chọn

| Split đề xuất | Khóa | Video ID |
|---|---|---|
| train | 11.382 | `neBeTYziSLo` |
| train | 15.S08 | `JuKKBf-uSDI` |
| train | 15.S12 | `_Ycy0Dy-B1c`, `w7HDA8gUbpQ` |
| train | 18.100A | `gXPX29KfEc4`, `M2d4HsBsu8Y` |
| train | 18.404J | `KAySmSEGc9U`, `7J1HD9rqEB4` |
| train | 22.01 | `9uqKU5ZDwfM`, `7LyvAVjQUR8` |
| train | 6.006 | `2NMtS1ecb3o`, `EmSmaW-ud6A` |
| train | 7.016 | `CALYA11terw`, `Chv8dlBVXpw` |
| train | 8.20 | `_S1CREXGfvE`, `gtQ046Tu2S4` |
| train | 8.962 | `JNWXzIFcf3g`, `gnWKpHUj11w` |
| train | 9.13 | `vFZY--lgmHs` |
| validation | 18.217 | `Rlvwagd2BmY`, `vcsxCFSLyP8` |
| validation | 24.900 | `qb1U3_Q-7o8` |
| validation | 5.310 | `JIw9mnVeFig` |
| validation | 6.801 | `XSUjp-cDyeY`, `J4gbaRyWpoM` |
| validation | 9.40 | `Hf1Ma9YkOMY`, `r1VX3WXrYUw` |
| final_test | 11.165 | `AhK3YeJP8Ts` |
| final_test | 14.04 | `o8sje-b-BCk`, `ySqVVEBTy2o` |
| final_test | 3.091 | `tKyaGnPni3U`, `DvGNpuan4rw` |
| final_test | 7.05 | `Ed0Wg-5YYCk` |
| final_test | MAS.S62 | `muwNEvhy6Po`, `74_BKWR3n0k` |

## Kiểm tra và giới hạn

- Kiểm thử chọn/lọc/không trùng khóa/preflight artifact: `python -m pytest tests/test_select_mitfld_rq1_cohort.py -q` → 3 passed. Kiểm đếm: 35 đã chọn + 424 dự phòng = 459; không trùng ID hay khóa giữa split; 10 pilot ID đều bị loại. Receipt v2 ghi SHA-256 selected `ed658ca8fe4fce47b780ef72195d2e0bdc58a60a141e622b1d9f73128fd1b49d`, reserve `e8ad28d7dc048873f1bb2dc07cdc9c5f64cd14cf5499c6046b3ee191b1aa6442`. Bản v1 lúc 11:12 bị thay thế vì thiếu `review_flag` trong CSV.
- `Rlvwagd2BmY` và `vcsxCFSLyP8` mang cờ `shortlink_redirects_to_2023_course`: kiểm bằng trang khóa chuẩn, không tin shortlink cũ. Các tiêu đề `Course Review` (6.006), `Chernobyl Trip Report` (22.01), `Prof. Klute’s Research` (8.20) cần kiểm loại nội dung có phù hợp chaptering bài giảng. Kiểm thêm trùng nội dung gần đúng giữa các khóa và ngoại lệ quyền trong nội dung từng video.
- Chưa kiểm quyền/ngoại lệ của 35 file, tương ứng OCW MP4 với `frags` sau giải mã, nguồn gốc/giấy phép GT, hoặc tỷ lệ bài sống sót. Chưa chạy mô hình trên cohort này. Split hiện là **đề xuất**, không phải split độc lập đã chứng nhận. Mọi thay đổi nguồn primary YTSeg đã đăng ký trước cần amendment có ngày trong master plan trước khi đóng băng D2.

## Bước tiếp theo

Kiểm 35 ID theo cùng ledger: quyền từng MP4 và ngoại lệ nội dung; cặp HF/OCW ở các mốc `frags` sau giải mã; nguồn gốc, quyền và chất lượng GT. Chỉ dùng reserve cùng khóa khi có thất bại được ghi; tổng hợp attrition và số khóa/bài sống sót trước quyết định D2.

## Câu hỏi chưa giải quyết

1. Bao nhiêu trong 35 bài vượt đủ ba gate quyền, căn chỉnh và GT, kể cả ngoại lệ nội dung?
2. Có cần tạo GT độc lập được cấp phép nếu tác giả MITFLD chưa xác nhận provenance/quyền GT không?
3. Sau attrition, split theo khóa còn đủ nhóm và phù hợp mục tiêu RQ1 không?
