# VidChapters‑7M: khởi động qualification sau cổng YTSeg

**Đính chính 2026-09-29:** Giao `video_id` với YTSeg không tự động là leakage hoặc lý do loại. [Ledger lịch sử sử dụng](./cross-dataset-use-history-260929-1637-ledger.csv) tách kiểm khả dụng/GT/media khỏi huấn luyện, tuning và chọn mô hình; chưa có bằng chứng các ID giao nhau đã được dùng huấn luyện/tuning trong đợt qualification này. Một ID chỉ được tính một mẫu, và việc đưa vào final test phải xét lịch sử sử dụng cùng quy tắc nhóm khóa/giảng viên trước khi khóa split. Mọi chỉ dẫn loại tự động theo giao ID bên dưới được thay bằng quy tắc này.

**Trạng thái:** nguồn dự phòng đang được kiểm; chưa khóa cohort bài giảng, chưa có unit eligible hay split RQ1. [Receipt máy đọc được](./vidchapters-7m-260929-qualification-kickoff-receipt.json).

## Release và phép đọc GT

[Trang tác giả](https://antoyang.github.io/vidchapters.html) công bố `chapters.pkl`, ba danh sách ID train/validation/test và `tagged.pkl`. Đã tải đủ byte năm file vào thư mục dữ liệu ignored, ghi SHA‑256 trong receipt. `chapters.pkl` dài **2.039.261.340 byte**, SHA‑256 `d476b9aa628d96d015d288a9554fed2e37206670bbcd55b7bf072bf2019b166e`. File lớn được xác nhận toàn byte và xem đầu bằng `pickletools`; **chưa unpickle hoặc kiểm toàn bộ annotation**. Không dùng nhãn chưa kiểm này làm GT.

[Mã tạo chapter của tác giả](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/collection/desc2chapters.py) tại commit `fa3900c6508d53ea9d490a07f079703b163c78ea` tách mốc và tiêu đề từ mô tả YouTube, chỉ giữ danh sách có nhiều hơn một chapter và thời gian tăng nghiêm ngặt. [Mã xử lý cho DVC](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/preproc/chapters_to_dvc.py) lấy kết thúc segment từ mốc tiếp hoặc duration, lọc interval không hợp lệ/tiêu đề rỗng. Cổng tới phải đối chiếu mã, trường `label/time/duration` và nguồn description từng ID; chất lượng chapter vẫn cần kiểm trực tiếp. Giấy phép MIT của **mã nguồn** và copyright notice trên trang tác giả chưa giải quyết giấy phép annotation hoặc quyền xử lý từng video YouTube.

## Split phát hành và rò rỉ lịch sử

Đã đọc các file JSON ID thuần: **800.676 train, 8.200 validation, 8.200 test**; mỗi split không có ID lặp, ba cặp split không giao ID. Đây chỉ là split **cấp video**, chưa xác nhận rời nhau theo khóa hoặc mọi giảng viên. `tagged.pkl` là ba danh sách ID (`nsfw` 5.716, `toxic_chapters` 355, `toxic_asr` 1.368); đã xem toàn bộ opcode trước khi nạp file nhỏ này, không có opcode thực thi. Tag không thay thế kiểm quyền hoặc nội dung.

**Mười trong 12 ID danh sách YTSeg khóa nằm trong VidChapters train**, gồm cả hai ID YTSeg gốc validation/test đã loại; 35 MITFLD selected và 10 pilot cũ không giao ID. Ghi lịch sử sử dụng từng ID trước khi gán split RQ1; không loại tự động vì giao ID. Không tính cùng ID hai lần và không dùng split video sẵn có làm split RQ1 nếu cùng khóa/giảng viên xuất hiện hai phía.

## Cổng tiếp theo cho VidChapters

1. Đọc annotation bằng bộ phân tích dữ liệu an toàn, lọc video dạng bài giảng ngoài Yale; đối chiếu lịch sử dùng mẫu để quyết định vai trò split, giữ `video_id`, mốc/tiêu đề phát hành, nguyên nhân lọc. Không tuyển theo điểm mô hình.
2. Gắn trang publisher, `course_id`, **mọi** `lecturer_ids`, giấy phép resource và đường nhận toàn file cho từng ID chọn. Không coi giấy phép mã nguồn hoặc annotation là giấy phép video; không dùng công cụ tải YouTube để lấp cổng đường truy cập.
3. Khóa ID trước media; kiểm full-file bytes/hash/decode và nhiều vị trí transcript/chapter; rà nội dung trùng với YTSeg và pilot, quyền thành phần. Split theo thành phần liên thông cùng khóa **hoặc** bất kỳ giảng viên chung, xét precision/CI ở cấp nhóm.
4. Chỉ khi có cohort đủ toàn bộ cổng mới lập amendment cho nguồn/split/GT, đóng băng D2 rồi cân nhắc official RQ1.

## Câu hỏi chưa giải quyết

1. Có bao nhiêu video bài giảng VidChapters có GT chất lượng, publisher media và quyền từng resource đủ để kiểm toàn file?
2. Sau lọc trùng YTSeg/pilot và gộp theo khóa hoặc giảng viên, còn bao nhiêu nhóm độc lập có thể hỗ trợ CI đã khai báo trước?
