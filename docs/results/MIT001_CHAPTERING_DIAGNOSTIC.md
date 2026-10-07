# Chẩn đoán chia chương MIT001 trên 35 video

Ngày cập nhật: 2026-09-28. Số liệu lấy từ run địa phương `20260928T022609Z` (hai runner 04a/04b hoàn tất, đủ bảy biến thể 04b trên 35 bài). Đây là kết quả **chẩn đoán địa phương**, chưa phải benchmark RQ1 chính thức hay kết quả trên tập kiểm tra độc lập.

## Phạm vi và phương pháp

Tập đánh giá gồm 35 video của một khóa MIT 18.01 do Giáo sư David Jerison giảng dạy. [MIT OpenCourseWare liệt kê các bài giảng](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/video_galleries/video-lectures/) và cho biết video được ghi hình vào mùa Thu 2007; bản media đối chiếu với [item MIT18.01JF07 trên Internet Archive](https://archive.org/details/MIT18.01JF07). Mốc chương tham chiếu lấy từ `segmentation/segments_ts.txt` của [AVLectures](https://github.com/Darshansingh11/AVLectures) (Darshan Singh S., Anchit Gupta, C. V. Jawahar, Makarand Tapaswi, WACV 2023). Tập này có 277 đoạn, tương ứng 242 mốc ranh giới nội bộ trên 35 bài.

Chúng tôi dùng văn bản từ phụ đề SRT làm transcript (**không phải đầu ra ASR**). Cảnh và OCR (tối đa 12 khung hình mỗi bài) được trích từ MP4. Tín hiệu `visual` là mức thay đổi ảnh xám 64 × 36 giữa các khung hình lấy mẫu mỗi 20 giây; `acoustic` là mức thay đổi năng lượng âm thanh RMS giữa các cửa sổ 10 giây. Đây là tín hiệu hình/âm thanh mức thấp, **không phải caption hình hoặc mô hình ngữ điệu đã học**. Mỗi đặc trưng được gắn SHA-256 của MP4, cấu hình và danh tính bộ trích xuất; visual chỉ khả dụng khi giải mã ít nhất 95% khung hình dự kiến. Cả bốn đặc trưng cảnh/OCR/visual/acoustic đều khả dụng ở 35/35 bài trong run này.

Các mốc từ vựng TextTiling được ước lượng theo tốc độ token đều của bài vì không có timestamp từng từ. Biến thể từng nguồn ghép mốc từ vựng với sự kiện gần nhất trong 45 giây; visual/acoustic dùng nhóm 25% mức thay đổi dương cao nhất theo từng bài. Biến thể `all_modalities` dùng cả bốn nguồn cảnh, OCR, visual, acoustic và giữ mốc từ vựng có ít nhất hai nguồn xác nhận trong 45 giây. Các quy tắc này cố định trong mã, không lấy GT để đặt ngưỡng. Mỗi video được tính F1 tại ranh giới chương với dung sai ±3 giây; số trong bảng là trung bình đều của 35 F1 theo video (**macro F1**). Đây là điểm số mô tả của một lần chạy, không phải kiểm định ý nghĩa thống kê.

## Kết quả tổng hợp

| Biến thể | Macro F1, ±3 giây, 35 video | Chênh lệch ghép cặp so với transcript | Thắng / hòa / thua theo video |
|---|---:|---:|---:|
| Cửa sổ 300 giây (`duration_only`) | 0,0198 | −0,0096 | 5 / 2 / 28 |
| Transcript (`transcript`) | 0,0294 | 0 | mốc so sánh |
| Transcript + cảnh (`transcript+scene`) | 0,0486 | +0,0192 | 23 / 0 / 12 |
| Transcript + OCR (`transcript+ocr`) | 0,0502 | +0,0208 | 13 / 2 / 20 |
| Transcript + visual (`transcript+visual`) | 0,0416 | +0,0122 | 20 / 1 / 14 |
| Transcript + acoustic (`transcript+acoustic`) | **0,0637** | **+0,0343** | 29 / 0 / 6 |
| Kết hợp đủ nguồn (`all_modalities`) | 0,0488 | +0,0194 | 26 / 0 / 9 |

`transcript+acoustic` cao nhất ở F1 ±3 giây và thắng transcript trên 29/35 bài; `all_modalities` thấp hơn biến thể acoustic, nên thêm nguồn không tự động cải thiện điểm. OCR có trung bình cao hơn transcript nhưng chỉ thắng 13/35 bài. Điểm tuyệt đối vẫn thấp. Hai mô hình học C5/C6 vẫn `not_run` vì thiếu checkpoint và bằng chứng huấn luyện đủ điều kiện; các hàng trên là heuristic, không đại diện cho C5/C6.

Chỉ số phụ cũng không chọn cùng một biến thể ở mọi thước đo (Pk và WindowDiff càng thấp càng tốt):

| Biến thể | F1 ±5 giây | F1 ±10 giây | Pk | WindowDiff |
|---|---:|---:|---:|---:|
| Transcript | 0,0487 | 0,0711 | 0,5616 | 1,0000 |
| Transcript + cảnh | 0,0657 | 0,1056 | 0,5318 | 0,8158 |
| Transcript + OCR | 0,0597 | 0,0976 | **0,4675** | 0,5204 |
| Transcript + visual | 0,0596 | **0,1157** | 0,5400 | 0,8419 |
| Transcript + acoustic | **0,0826** | 0,1093 | 0,5450 | 0,9630 |
| Kết hợp đủ nguồn | 0,0674 | 0,0986 | 0,5458 | 0,9489 |

## Quyết định đối với 9 mục media audit `review`

Cả 35 MP4 có audio/video và khớp MD5, kích thước với manifest nguồn. Media audit ghi **26 `pass`, 9 `review`**. Chín mục `review` có mốc kết thúc đoạn GT vượt thời lượng container MP4 từ **0,508 đến 0,881 giây**; các mốc ranh giới chương nội bộ đều nằm trong video. Phép chấm F1 ở trên sử dụng các mốc nội bộ, vì vậy giữ **đủ 35 video** trong mẫu chính và giữ nguyên GT. Chúng tôi không coi giả thuyết làm tròn giây ở mốc cuối là sự thật đã được nguồn xác nhận.

Phân tích độ nhạy dưới đây tính lại trung bình chỉ trên 26 video `pass`; đây **không phải** kết quả chính thay thế.

| Biến thể | Macro F1, 35 video | Macro F1, 26 `pass` |
|---|---:|---:|
| Cửa sổ 300 giây | 0,019751 | 0,021093 |
| Transcript | 0,029383 | 0,030476 |
| Transcript + cảnh | 0,048577 | 0,048893 |
| Transcript + OCR | 0,050168 | 0,048910 |
| Transcript + visual | 0,041558 | 0,043501 |
| Transcript + acoustic | 0,063661 | 0,061484 |
| Kết hợp đủ nguồn | 0,048825 | 0,046255 |

## Giới hạn và nguồn

- Cả 35 bài thuộc một khóa học; nhãn của chúng đã xuất hiện trong một pilot trước đó. Không có tập test giữ kín hoặc kiểm tra khả năng chuyển sang khóa khác. Không suy rộng các điểm số này thành hiệu quả chung của hệ thống.
- Nguồn GT đang được ghi nhận là `diagnostic_only`; archive gốc chưa toàn vẹn (`truncated_gzip`) và việc rà quyền theo từng tài sản vẫn `pending`. Kết quả này không được đưa vào lựa chọn mô hình chính thức.
- Payload theo video của run nằm ở `experiments/outputs/diagnostic/rq1_mit001_local_runs/20260928T022609Z` trong máy chạy và có receipt/manifest cùng hash nguồn. Payload này không nằm trong nhánh công bố; người đọc bên ngoài chưa thể tái chạy chỉ từ trang này.
- Bản công bố này chỉ chứa phương pháp và số liệu tổng hợp. Không kèm video, âm thanh, phụ đề, khung hình, GT, dự đoán theo từng video hoặc model weights. Nguồn video: [MIT OpenCourseWare](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/video_galleries/video-lectures/) và [Internet Archive](https://archive.org/details/MIT18.01JF07); nguồn mốc chương: [AVLectures](https://github.com/Darshansingh11/AVLectures).
- Khi đánh giá trên tập độc lập, cần xác nhận quyền và nguồn GT, quy ước mốc kết thúc, thêm khóa học khác và khóa tập kiểm tra trước khi chọn mô hình.
