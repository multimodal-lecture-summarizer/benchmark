# VISTA validation: kiểm tra 40 video tải trên Colab

Ngày: 2026-10-03. Nguồn người dùng tải về: `selection.csv`, `download_receipts.csv`, `media_profile.csv`, `asr_sample.csv`. Revision do notebook ghi: `39c60afff185fbefe80b685898cf073da0fd92ab`. Phạm vi: metadata train/validation và media validation; chưa mở test.

## Kết quả đối chiếu CSV

- Có 40 ID, 40 tên MP4 và 40 đường dẫn Hub khác nhau. Bốn bảng nối được theo ID; không có lỗi tải hoặc lỗi `ffprobe` được ghi.
- 40/40 MP4 tải thành công. `actual_bytes` bằng `expected_bytes` ở cả 40; tổng 3.210.108.933 byte (2,99 GiB). Tổng thời gian tải được receipt ghi khoảng 2,0 phút; không xem là phép đo tốc độ mạng đại diện.
- `media_profile.csv` ghi 40/40 `ok`: đọc được thời lượng và cả luồng video/audio. Trạng thái này **không** bao gồm giải mã hết từng frame hoặc đánh giá nội dung bài nói.
- 40 video đến từ 19 cặp venue–năm, 7 họ venue, các năm 2020–2024. Phân bổ họ: ACL 8, Findings 8, NeurIPS 8, EACL 4, EMNLP 4, ICML 4, NAACL 4. Đây là lựa chọn cân bằng venue cho EDA, không là mẫu ngẫu nhiên hay bằng chứng đại diện cho toàn corpus.

## Media thực tế

| Chỉ số | Kết quả |
|---|---:|
| Thời lượng trung vị | 6,28 phút |
| Khoảng thời lượng | 3 giây – 13,23 phút |
| Dưới 2 phút | 1 video |
| 2–5 phút | 10 video |
| 5–10 phút | 15 video |
| 10–15 phút | 14 video |
| Kích thước trung vị | 61,0 MB |
| Video H.264/AAC | 39/40 |
| Video 1280×720 | 21/40 |

**Ngoại lệ quan trọng:** `val_0395` (`2022.naacl-main.174.mp4`, NAACL 2022) chỉ dài **3,0 giây**, 198.892 byte. Đây là tệp đúng kích thước bản phát hành và có luồng video/audio, nhưng không thể xem là bài trình bày đầy đủ để chấm tóm tắt. Đưa vào danh sách kiểm tra hoặc loại khỏi cohort đánh giá nội dung theo quy tắc thời lượng tối thiểu được chốt trước khi chấm. Nếu dùng ngưỡng 2 phút, còn **39 ứng viên** trong 40 tệp đã tải.

Một tệp khác, `val_0194` (`2022.naacl-main.156.mp4`), dùng **MSMPEG4v2/MP3** thay vì H.264/AAC, thời lượng 4,55 phút. Pipeline xử lý nên kiểm tra decode/transcode cho tệp này trước khi dùng cùng các MP4 khác.

`silence_events_first_minute` là **số lần** FFmpeg phát hiện đoạn yên tĩnh trong phút đầu, không phải tỷ lệ im lặng hay chất lượng tiếng nói. Giá trị của cohort là 0–9, trung vị 2; không đủ để kết luận âm thanh sạch.

## ASR mẫu

Whisper hoàn thành 5/5 đoạn đầu 60 giây. Nội dung đầu transcript có dạng lời giới thiệu bài trình bày, nhưng chưa đối chiếu thủ công với audio hay abstract nên không có số liệu độ chính xác ASR hoặc độ đúng của tham chiếu. Cả 5 tệp ASR đều thuộc **ACL/EACL**; mẫu này chưa kiểm tra tiếng nói của ICML, NeurIPS, EMNLP, Findings hoặc NAACL.

## Kết luận và bước tiếp

VISTA **khả thi cho cohort validation có media thật** trên Colab: 40/40 tệp tải được và có cả hình, tiếng. Sau khi tách tệp 3 giây, cohort hiện có 39 ứng viên bài trình bày. Các kết quả chưa chứng minh khả năng lấy toàn bộ VISTA, tính đại diện thống kê, chất lượng abstract, hoặc chất lượng mô hình tóm tắt.

Lần kiểm tra tiếp theo có thể dùng **chính các media đã lưu trên Drive**: xem tệp 3 giây; chạy ASR mẫu phân tầng theo 7 họ venue; ghép `val.json` để xem title/abstract của 39 ứng viên và so sơ bộ nội dung. Không cần tải lại 40 MP4.

## Câu hỏi chưa giải quyết

- Tệp 3 giây là video gốc ngắn bất thường hay lỗi nguồn phát hành?
- Tệp MSMPEG4v2/MP3 có giải mã ổn định trong pipeline dự định dùng không?
- Abstract có phản ánh nội dung video đủ tốt để làm tham chiếu tóm tắt không?
