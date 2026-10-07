# RQ1 Yale: đối chiếu cấu trúc GT nguồn với sáu MOV

Ngày kiểm: 2026-09-29. Chỉ dùng chapter starts và số tiêu đề **Yale đã công bố**. Không tạo, sửa, chọn hoặc gắn nhãn mốc chương; không đánh giá nội dung/ngữ nghĩa của mốc. [Receipt máy đọc được](./rq1-yale-260929-publisher-gt-mov-structural-receipt.json) lưu kết quả từng file.

## Nguồn và phép kiểm

Đối chiếu sáu trang gốc: [ECON 159 L2](https://oyc.yale.edu/economics/econ-159/lecture-2), [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1), [ECON 252 L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6), [ENGL 220 L23](https://oyc.yale.edu/english/engl-220/lecture-23), [PHYS 200 L19](https://oyc.yale.edu/physics/phys-200/lecture-19), [PHYS 201 L10](https://oyc.yale.edu/physics/phys-201/lecture-10). Ngày này cả sáu trang hiển thị số tiêu đề và dãy giây đúng như [ledger nguồn](./rq1-yale-260928-1952-nine-course-qa-sample.csv). [Snapshot GT nguồn](./rq1-yale-260929-1111-source-gt-snapshot-receipt.json) lưu chính xác 34 cặp tiêu đề/mốc do Yale đăng cùng thời điểm truy xuất UTC, ETag, Last-Modified, SHA-256 HTML và SHA-256 bảng GT chuẩn hóa. Không lưu toàn HTML/transcript. Lần truy xuất thứ hai cho cùng HTML hash và ETag ở 6/6 trang.

Đối với đúng sáu MOV trong [batch receipt trước](./rq1-yale-260929-0843-qualification-batch-receipt.json), đọc byte và SHA-256 mới; dùng `ffprobe` đọc duration container, video stream, `start_time` và `time_base`. Kiểm URL media/filename khớp receipt; số mốc bằng số tiêu đề ở [metadata ledger](./rq1-yale-260928-1916-nine-course-metadata-ledger.csv); mốc đầu bằng 0, các mốc tăng nghiêm ngặt, mốc cuối nhỏ hơn thời điểm kết thúc video stream và container. Không so âm thanh, hình hoặc transcript với nội dung chương.

| Kết quả cấu trúc | Số MOV |
|---|---:|
| File đúng byte và SHA-256 receipt trước | 6/6 |
| URL/filename khớp, số mốc bằng số tiêu đề | 6/6 |
| Mốc đầu 0, tăng nghiêm ngặt, mốc cuối trong video stream/container | 6/6 |

Số mốc lần lượt: ECON 159 **5**, ECON 251 **7**, ECON 252 **6**, ENGL 220 **5**, PHYS 200 **7**, PHYS 201 **4**. Khoảng kết thúc video stream theo file đã băm: **2643,98–4456,26 giây**. Đây là **structural pass**, không phải xác nhận mốc khớp onset ngữ nghĩa trong ±3 giây, không xác nhận quyền từng thành phần và không cấp D2. Phần full decode/PTS đã có ở batch trước; phép kiểm này chỉ đọc metadata stream, không tái kiểm mọi frame/PTS.

## Còn thiếu trước official

Đã cố định **bản GT quan sát ngày 2026-09-29** bằng receipt nguồn, nhưng không thể bảo đảm trang Yale sẽ không đổi về sau; cần so hash hoặc dùng chính snapshot này khi freeze. Chưa có chứng cứ quyền toàn thành phần trên từng MOV; chưa có cohort/split đủ mạnh theo giảng viên. Chất lượng onset ngữ nghĩa không được chấm khi không có nhãn độc lập và dự án không tự tạo nhãn. Giữ nguyên GT Yale công bố, báo giới hạn này trong mọi phép đánh giá có thể được phép sau này. Sáu MOV vẫn là qualification, chưa là D2 official.
