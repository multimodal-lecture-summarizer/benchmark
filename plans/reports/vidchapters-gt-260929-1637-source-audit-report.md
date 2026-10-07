# VidChapters-7M: audit GT và nguồn trước media

**Phạm vi:** bản `chapters.pkl` tác giả đã tải đủ (2.039.261.340 byte; SHA-256 `d476b9aa628d96d015d288a9554fed2e37206670bbcd55b7bf072bf2019b166e`), mã tác giả tại commit `fa3900c6508d53ea9d490a07f079703b163c78ea`, và **10 ID giao YTSeg–VidChapters**. Chưa suy rộng kết quả hàng sang toàn bộ 817K video. Không tải media, không chạy mô hình/official RQ1.

## Kết luận kiểm được

1. [Paper NeurIPS §3.1](https://proceedings.nips.cc/paper_files/paper/2023/file/9b5c3e00d6ed30aad7adac9e7a664de1-Paper-Datasets_and_Benchmarks.pdf), [trang tác giả](https://antoyang.github.io/vidchapters.html), và [README mã tác giả](https://github.com/antoyang/VidChapters/tree/fa3900c6508d53ea9d490a07f079703b163c78ea) độc lập cho biết chapter lấy từ các dòng mốc và tiêu đề do người đăng ghi trong mô tả YouTube; đây là nhãn thu thập tự động, có thể lệch nội dung. Paper kiểm ngẫu nhiên 100 video: 83% chapter gắn với ít nhất một modality, 14% chỉ mô tả cấu trúc, 3% không liên quan. Tỷ lệ này không xác thực bất kỳ ID riêng lẻ nào.
2. Dùng `pickletools` đọc opcode, không `pickle.load`: record đầu và 3.000 record đầu có sáu trường `chapters`, `duration`, `title`, `description`, `channel_id`, `view_count`. Mười ID mục tiêu mỗi ID xuất hiện đúng một lần ở opcode `BINUNICODE` dài 11 byte. Đọc đúng phạm vi record qua opcode, không thực thi pickle. Trong cả 10, `chapters` là danh sách các cặp **`label,time` ngay trong cùng object**; mọi label khác rỗng, mốc tăng nghiêm ngặt, từ 0 tới ≤ `duration`. Memo key của record phía cuối file được đối chiếu tại byte định nghĩa của chúng (ví dụ `duration` ở 568.761.353, `chapters` ở 568.763.432; `label/time` đối chiếu tại record nguồn tương ứng), không suy đoán ghép hai list rời.
3. [Mã `chapters_to_dvc.py` của tác giả](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/preproc/chapters_to_dvc.py) đọc `x['time']`, `x['label']`, tạo end bằng mốc tiếp theo hoặc `duration`. Mã lọc interval và title rỗng; **không nên âm thầm nhận `chapters_dvc_*` làm target tương đương `chapters.pkl`**, vì lựa chọn preprocessing/target cần protocol riêng. Với cohort hiện xét, đề xuất adapter tối thiểu đọc cặp gốc và chỉ tạo end theo quy tắc tác giả sau khi chốt target; giữ SHA nguồn, source offset, kiểm mốc/label trên mỗi ID.

| Video ID | Nguồn theo title | `duration` s | Chapter | Mốc cuối s | GT cấu trúc |
|---|---|---:|---:|---:|---|
| `-dOX_4lI6HY` | MIT 16.687, bài 13 | 3122.333 | 22 | 3006 | đạt |
| `3sB64Au76h0` | MIT 16.687, bài 12 | 3931.895 | 33 | 3302 | đạt |
| `PHtPau1c5sU` | MIT 16.687, bài 3 | 2094.936 | 16 | 1905 | đạt |
| `Th2N_rDfkDw` | MIT 16.687, bài 7 | 2514.903 | 24 | 2128 | đạt |
| `alLh1Jdqwvg` | MIT 16.687, bài 10 | 2172.838 | 19 | 2066 | đạt |
| `kiCNa95DnnE` | MIT 16.687, bài 21 | 1292.349 | 26 | 1208 | đạt |
| `ksyY5wa5_50` | MIT 16.687, bài 19 | 1702.274 | 21 | 1456 | đạt |
| `shHvE6yV4IM` | MIT 16.687, bài 6 | 2033.391 | 13 | 1980 | đạt |
| `tCKk22kaZi4` | MIT 14.01, bài 2 | 2483.417 | 12 | 2071 | đạt |
| `xsO2Ip6eiaY` | MIT 16.687, bài 16 | 1474.475 | 16 | 1346 | đạt |

**Đếm đúng:** 9 ID MIT 16.687 (gồm hai ID YTSeg validation/test cũ), 1 ID MIT 14.01. Cả 10 đều gắn `channel_id` MIT OpenCourseWare (`UCEBb1b_L6zDS3xTUrIALZOw`). `channel_id` chung không chứng minh cùng course hay giảng viên; annotation không có `course_id` hoặc `lecturer_ids`.

## Cổng và giới hạn áp dụng

| Cổng | Mười ID giao YTSeg | Phần VidChapters còn lại |
|---|---|---|
| GT cấu trúc cặp nhãn–mốc | **pass cấu trúc**; chưa đối chiếu nội dung từng chapter với media trong vai trò VidChapters | chưa kiểm từng hàng |
| Quyền sử dụng nghiên cứu | `hold_rights_research`: cần quy tắc áp dụng cho annotation và media từng resource; công bố dataset không tự cấp phép cho mọi video | chưa kiểm |
| Quyền phát hành lại | `hold_redistribution`: đánh giá riêng; không gộp với quyền nghiên cứu | chưa kiểm |
| Nhận dạng/split | 9 + 1 theo course từ nguồn đối chiếu trước; cần ledger đã dùng train/tune/test và nhóm theo course **hoặc** lecturer | chưa khóa cohort |
| Media/timeline | `hold_media`: có media YTSeg cũ cho 8 TRAIN nhưng chưa đối chiếu đủ nhãn VidChapters với những file đó; 2 ID YTSeg val/test chưa có media audit | chưa kiểm |

**Đếm cổng đầy đủ trên 10 hàng đã kiểm: N = 0 video, G = 0 nhóm độc lập `pass`.** Đây là phạm vi *10 hàng được kiểm*, không phải kết luận không có video pass trong toàn bộ release. Không loại ID chỉ do giao dataset; một ID không được đếm thành hai mẫu độc lập, và lịch sử train/tune/test phải quyết định vai trò hợp lệ. Không biến fingerprint âm thanh/hình ảnh thành cổng mới.

## Xếp hạng cách đọc GT

| Hạng | Cách đọc | Độ tin cậy | Chi phí/bảo trì | Rủi ro |
|---|---|---|---|---|
| 1 | `chapters.pkl` cặp `label,time` gốc, adapter có kiểm per-row | cao cho cấu trúc 10 hàng; hợp task chapter | thấp; một adapter | nội dung chapter vẫn cần đối chiếu media; pickle lớn cần parser an toàn |
| 2 | `chapters_dvc_*` của tác giả | mã xử lý công khai | trung bình; lọc và tokenize | target thay đổi so với raw; cần amendment rõ |
| 3 | Ghép list mốc và title độc lập | không có nhu cầu ở VidChapters | thấp | dễ sinh nhãn sai; không chọn |

**Khuyến nghị:** đi tiếp với hạng 1, khóa lựa chọn target trong protocol trước media; tuyển vài course/lecturer ngoài tập giao bằng metadata, xác minh quyền nghiên cứu và quyền phát hành lại độc lập, rồi mới tải media theo danh sách khóa. Công bố học thuật + repository MIT license của **mã** không chứng minh quyền trên annotation, video hay quyền phát hành lại. Dữ liệu user chapter có thể được dùng nghiên cứu theo điều kiện cụ thể; hiện chưa đủ chứng cứ để gọi `pass_rights_research` cho resource nào.

## Phụ lục: khám phá kênh MIT OCW ngoài cohort đã kiểm

Quét byte opcode cho `channel_id=UCEBb1b_L6zDS3xTUrIALZOw`: **87 record**, gồm **10 ID giao YTSeg** và **77 ID ngoài giao**. [CSV đủ 87 hàng](./vidchapters-gt-260929-1637-mit-ocw-channel-discovery.csv), SHA-256 `2b113d3fb7933c3339a0d3ea486bb8cb0d54a6cfb2be34afc78ab07d85da7f26`. Đây là **discovery**, không phải danh sách khóa hay số video pass. Tên bài gợi ý nhiều course (MIT 15.S12, toán, vật lý, điện ảnh, kinh tế), nhưng chưa xác nhận từng trang publisher, `course_id`, tất cả giảng viên hoặc quyền. `channel_id` chung không được dùng thay nhóm độc lập.

30 hàng đầu ngoài 10 ID giao theo thứ tự byte trong annotation:

| `video_id` | Title trong annotation | Duration s | Chapters |
|---|---|---:|---:|
| `Of68ZXH35o0` | Polyelectrolyte Multilayers | 654 | 4 |
| `870y6GUKbwc` | Entropy | 813 | 17 |
| `EH6vE97qIP4` | 1. Introduction for 15.S12 Blockchain and Money, Fall 2018 | 3723.397 | 23 |
| `XDBr39cwmbg` | Day 6: Table-Read / Office Hours | 8058.667 | 5 |
| `ilM34q8F6rY` | 8. The Work of Movies; Capra & Hawks | 3376.642 | 5 |
| `oocw6x_kCQs` | 14. The Western (continued) | 3577.39 | 5 |
| `oo1ZZlvT2LQ` | The Exponential Function | 2333.788 | 5 |
| `BgozyEIGsuc` | 6. German Film, Murnau | 2913.683 | 5 |
| `qkkI9Z9tKvo` | Day 13: Screening (Final Cuts) | 4035.056 | 8 |
| `AjK2zF9yN0k` | Day 3: Storyteller’s Toolkit Pt. I: Verbal Storytelling/Writing for the Spoken Word; Part 1 | 7906.844 | 7 |
| `17uL1VoaWTQ` | Day 1: Identity and Genre; Part 2 | 2204.185 | 3 |
| `ZMe7jSsPmW4` | Day 7: Table-read / Post-production; Part 1: Table-read | 2569.412 | 2 |
| `T_I-CUOc_bk` | Big Picture: Derivatives | 1804.28 | 5 |
| `3MOahpLxj6A` | 5. Discrete Random Variables I | 3034.078 | 5 |
| `flAwb1TmOkQ` | 21. Truffaut, the Nouvelle Vague, The 400 Blows | 3384.316 | 7 |
| `VHyCh1mDneE` | Day 4: Storyteller’s Toolkit Pt. II: Visual Storytelling; Part 2: Storyboarding | 5306.94 | 3 |
| `iR6FUYCNi5A` | Day 10: Project Time; Part 1: Animation | 2107.544 | 4 |
| `EuNXVy5-KgA` | 20. Flying at Night | 1941.811 | 14 |
| `js34ZxECiCA` | 8. Metals and Cheeses - Uncoventional Pairings | 2354.198 | 21 |
| `q38KAGAKORk` | An Interview with Christopher Terman on Teaching Computation Structures | 2036.259 | 12 |
| `BrvMZf2jaso` | 10. Dynamic Financial Constraints | 4221.28 | 6 |
| `ONO1anWuNOk` | 11. Evaluation of a Large Scale Microfinance Experiment | 4571.599 | 6 |
| `Docl3KOqnHI` | Day 7: Table Read / Post-Production; Part 2: Post-Production | 6245.224 | 5 |
| `U_C7xW_gCfI` | 7. Standing Waves Part II | 3196.56 | 5 |
| `wF8vLZ9ceb0` | 9. Accelerated Charges Radiating Electromagnetic Waves | 3590.417 | 7 |
| `WsEPhUu8kKU` | 17. Jean Renoir and Poetic Realism | 2820.222 | 5 |
| `rCG6r6gotZQ` | Day 2: STEM Nuggets; Part 1 | 2165.269 | 3 |
| `MR_Dwrf9yII` | 2. Micro-Founded Macro Models | 5040.445 | 13 |
| `AW3a2ECNFlE` | 5. Measurement in Development | 4923.103 | 11 |
| `X60J__-GMx8` | 6. Standing Waves Part I | 2079.645 | 5 |

Cổng hiện tại của **77 ứng viên ngoài giao**: `hold_identity`, `hold_rights_research`, `hold_redistribution`, `hold_media`; GT mới có metadata cặp nhãn–mốc ở record được đọc để lấy số chapter, chưa audit toàn bộ label/mốc hay đối chiếu media từng ID. Quét dựa trên bốn giá trị kênh ghi trực tiếp trong pickle và các tham chiếu memo đã thấy; không thực thi pickle. Nếu triển khai parser sản xuất, cần kiểm toàn bộ file và bằng chứng publisher độc lập trước khi gọi tập này là đầy đủ.

## Năm ứng viên ngoài giao: kiểm đủ cặp nhãn–mốc

[Receipt theo ID](./vidchapters-gt-260929-1637-shortlist-paired-label-audit-receipt.json). Với **từng chapter** trong từng record, parser opcode giới hạn đã xác nhận đúng một `label` string và một `time` số; label không rỗng, mốc đầu 0, tăng nghiêm ngặt, không âm và nhỏ hơn `duration`. Mỗi ID xuất hiện đúng một lần dưới opcode ID 11 byte. Không chạy `pickle.load`.

| ID | Gợi ý title, chưa xác minh course/giảng viên | Chapter | Duration s | Mốc cuối s | GT cấu trúc |
|---|---|---:|---:|---:|---|
| `EH6vE97qIP4` | MIT 15.S12 Blockchain and Money | 23 | 3723.397 | 3702 | pass |
| `3MOahpLxj6A` | Discrete Random Variables I | 5 | 3034.078 | 2580 | pass |
| `U_C7xW_gCfI` | Standing Waves Part II | 5 | 3196.56 | 1144 | pass |
| `AW3a2ECNFlE` | Measurement in Development | 11 | 4923.103 | 4522 | pass |
| `LFOsw1Vccac` | MIT 21L.011 Film Experience | 6 | 3079.427 | 2755 | pass |

Cả năm vẫn **`hold_identity`, `hold_rights_research`, `hold_redistribution`, `hold_media`**. Title chỉ là gợi ý course, chưa phải nhận dạng publisher/lecturer được chứng thực. Trong shortlist năm video này, N=0/G=0 qua *toàn bộ* cổng; không phải kết luận trên 77 ứng viên hoặc toàn release.

## Câu hỏi chưa giải quyết

1. Điều khoản nào cho phép xử lý annotation và toàn file video từng resource trong nghiên cứu này, và điều khoản nào cho phép phát hành lại từng phần?
2. Chọn target chính là nhãn chapter gốc hay nhãn DVC đã xử lý; nếu dùng end từ mốc tiếp theo, xử lý chapter cuối/duration và ngoại lệ ra sao?
3. Sau lọc lịch sử sử dụng, course/lecturer và đối chiếu media, có bao nhiêu video và nhóm độc lập vượt toàn bộ cổng?
