# MIT001: quyền video và 9 mục media audit `review`

Ngày rà soát: 2026-09-28. Phạm vi: 35 MP4 trong chẩn đoán RQ1 MIT001, phụ đề SRT cùng bộ và GT chương AVLectures. Đây là hồ sơ bằng chứng cho quyết định công bố, không phải ý kiến pháp lý.

## Kết luận công bố

**Phạm vi đã chốt:** chỉ công bố phương pháp và số liệu tổng hợp trên **đủ 35 video**; giữ 9 mục `review` trong mẫu và giải thích riêng. Không phát hành MP4, âm thanh, SRT, khung hình, GT, dự đoán theo video hoặc model weights trong đợt này. Gắn nhãn “local diagnostic, 35 video MIT001”, trích nguồn và nêu giới hạn. **Chưa chuyển chẩn đoán này thành benchmark chính thức:** nguồn GT vẫn ghi `diagnostic_only`, archive `truncated_gzip`, `rights_review: pending`; chưa xác minh giấy phép riêng cho GT/SRT. Quyết định về phạm vi công bố không tự thay đổi các trạng thái kiểm toán này.

Không đưa MP4, âm thanh, SRT, khung hình, GT `segments_ts.txt` hoặc bản phái sinh lên kho/bài công bố chỉ dựa vào giấy phép cấp item. [MIT OCW hiện công bố CC BY-NC-SA 4.0](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), còn [item Internet Archive MIT18.01JF07 ghi CC BY-NC-SA 3.0](https://archive.org/details/MIT18.01JF07). Cần giữ nguyên khác biệt phiên bản, ghi công MIT OCW và Giáo sư David Jerison, liên kết giấy phép, ghi rõ thay đổi, tuân thủ phi thương mại/chia sẻ tương tự theo phạm vi tác phẩm áp dụng. [MIT nêu ngoại lệ cho tài liệu bên thứ ba hoặc “all rights reserved”](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content); giấy phép cấp khóa học không chứng minh mọi thành phần của từng video đều được tái phân phối.

## Phương pháp và giới hạn bằng chứng

- Danh sách 35 mã bài khớp [gallery chính thức của MIT OCW](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/video_galleries/video-lectures/), gồm bài 01–07, 09–16, 18–25, 27–33, 35–39. Gallery xác định video của David Jerison được quay mùa Thu 2007, dù trang khóa học mang nhãn Fall 2006. Mỗi hàng dưới đây dẫn đến trang bài giảng OCW tương ứng. Ba trang 01, 02, 39 đã được đọc trực tiếp; các trang còn lại được xác nhận hiện diện từ liên kết gallery. Chưa kiểm tra hình ảnh/âm thanh theo từng khung để loại trừ nội dung có quyền riêng.
- [Item Internet Archive](https://archive.org/details/MIT18.01JF07) ghi tác giả/phát hành MIT OCW và CC BY-NC-SA 3.0 ở **cấp item**. Manifest nguồn có 35 MP4 gốc nhưng không có trường giấy phép riêng cho từng file. Không suy diễn thành 35 xác nhận quyền độc lập.
- `media_audit.json` ghi 35/35 MP4 có audio/video và khớp MD5 cùng kích thước với manifest nguồn: 26 `pass`, 9 `review`. Đây là kiểm tra tính toàn vẹn và thời lượng, không phải kiểm tra quyền.
- [README AVLectures](https://github.com/Darshansingh11/AVLectures) mô tả video, SRT và `segmentation/segments_ts.txt` là các thành phần khác nhau. [LICENSE của repo ghi CC0](https://github.com/Darshansingh11/AVLectures/blob/main/LICENSE), nhưng không chứng minh tác giả có quyền đưa media MIT hay phụ đề/GT do bên khác sở hữu vào CC0. Chưa xác thực giấy phép của GT MIT001 từ bản phân phối đầy đủ; `gt_url` trong adapter chỉ là chuỗi “AVLectures MIT001 release”.

## Sổ đối chiếu từng video

Quyền trong tất cả 35 hàng: **nguồn OCW/item đã nhận diện; quyền tái phân phối từng MP4/SRT chưa được kết luận**. Cột audit chỉ nói về đối chiếu MP4 với GT và manifest. Các mã bài dùng đúng tên file `ocw-18.01-f07-lecNN_300k.mp4`.

| Bài / MP4 | Trang OCW | Media audit | Quyền từng video/SRT |
|---|---|---|---|
| 01 | [Rate of Change](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-1-derivatives/) | pass | cần xác nhận ngoại lệ |
| 02 | [Limits](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-2-limits/) | review | cần xác nhận ngoại lệ |
| 03 | [Derivatives](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-3-derivatives/) | review | cần xác nhận ngoại lệ |
| 04 | [Chain Rule](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-4-chain-rule/) | review | cần xác nhận ngoại lệ |
| 05 | [Implicit Differentiation](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-5-implicit-differentiation/) | review | cần xác nhận ngoại lệ |
| 06 | [Exponential and Log](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-6-exponential-and-log/) | pass | cần xác nhận ngoại lệ |
| 07 | [Exam 1 Review](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-7-exam-1-review/) | pass | cần xác nhận ngoại lệ |
| 09 | [Linear and Quadratic Approximations](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-9-linear-and-quadratic-approximations/) | pass | cần xác nhận ngoại lệ |
| 10 | [Curve Sketching](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-10-curve-sketching/) | pass | cần xác nhận ngoại lệ |
| 11 | [Max-min](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-11-max-min/) | pass | cần xác nhận ngoại lệ |
| 12 | [Related Rates](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-12-related-rates/) | pass | cần xác nhận ngoại lệ |
| 13 | [Newton's Method](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-13-newtons-method/) | pass | cần xác nhận ngoại lệ |
| 14 | [Mean Value Theorem](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-14-mean-value-theorem/) | pass | cần xác nhận ngoại lệ |
| 15 | [Antiderivatives](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-15-antiderivatives/) | pass | cần xác nhận ngoại lệ |
| 16 | [Differential Equations](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-16-differential-equations/) | review | cần xác nhận ngoại lệ |
| 18 | [Definite Integrals](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-18-definite-integrals/) | pass | cần xác nhận ngoại lệ |
| 19 | [First Fundamental Theorem](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-19-first-fundamental-theorem/) | pass | cần xác nhận ngoại lệ |
| 20 | [Second Fundamental Theorem](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-20-second-fundamental-theorem/) | pass | cần xác nhận ngoại lệ |
| 21 | [Applications to Logarithms](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-21-applications-to-logarithms/) | pass | cần xác nhận ngoại lệ |
| 22 | [Volumes](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-22-volumes/) | pass | cần xác nhận ngoại lệ |
| 23 | [Work, Probability](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-23-work/) | pass | cần xác nhận ngoại lệ |
| 24 | [Numerical Integration](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-24-numerical-integration/) | pass | cần xác nhận ngoại lệ |
| 25 | [Exam 3 Review](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-25-exam-review/) | pass | cần xác nhận ngoại lệ |
| 27 | [Trig Integrals](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-27-trig-integrals/) | review | cần xác nhận ngoại lệ |
| 28 | [Inverse Substitution](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-28-inverse-substitution/) | pass | cần xác nhận ngoại lệ |
| 29 | [Partial Fractions](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-29-partial-fractions/) | pass | cần xác nhận ngoại lệ |
| 30 | [Integration by Parts](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-30-integration-by-parts/) | pass | cần xác nhận ngoại lệ |
| 31 | [Parametric Equations](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-31-parametric-equations/) | review | cần xác nhận ngoại lệ |
| 32 | [Polar Coordinates](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-32-polar-coordinates/) | pass | cần xác nhận ngoại lệ |
| 33 | [Exam 4 Review](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-33-exam-4-review/) | pass | cần xác nhận ngoại lệ |
| 35 | [Indeterminate Forms](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-35-indeterminate-forms/) | pass | cần xác nhận ngoại lệ |
| 36 | [Improper Integrals](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-36-improper-integrals/) | review | cần xác nhận ngoại lệ |
| 37 | [Infinite Series](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-37-infinite-series/) | pass | cần xác nhận ngoại lệ |
| 38 | [Taylor's Series](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-38-taylors-series/) | pass | cần xác nhận ngoại lệ |
| 39 | [Final Review](https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/resources/lecture-39-final-review/) | review | cần xác nhận ngoại lệ |

## Chín mục `review`

Chín GT kết thúc sau thời lượng container MP4 từ 0,508 đến 0,881 giây. Cả chín đều có mốc chương nội bộ hợp lệ, thứ tự liên tục, không có khoảng hở, MD5/kích thước khớp manifest và audio/video có mặt.

| Bài | Thời lượng MP4 (s) | GT kết thúc (s) | GT vượt (s) | Mốc chương nội bộ cuối (s) | Số đoạn |
|---|---:|---:|---:|---:|---:|
| 02 | 3166,203 | 3167 | 0,797 | 2689 | 11 |
| 03 | 2994,492 | 2995 | 0,508 | 2835 | 9 |
| 04 | 2762,292 | 2763 | 0,708 | 2504 | 8 |
| 05 | 2940,134 | 2941 | 0,866 | 2835 | 8 |
| 16 | 2724,281 | 2725 | 0,719 | 2615 | 6 |
| 27 | 2804,204 | 2805 | 0,796 | 1764 | 7 |
| 31 | 2724,119 | 2725 | 0,881 | 2468 | 7 |
| 36 | 2966,442 | 2967 | 0,558 | 2704 | 10 |
| 39 | 2353,180 | 2354 | 0,820 | 2294 | 9 |

GT kết thúc đều là số giây nguyên; làm tròn là một cách giải thích hợp lý nhưng **chưa được nguồn xác nhận**. Giữ nguyên GT, cờ `review` và cả 35 video trong mẫu chính. Adapter tạo `chapter_boundaries_sec` từ điểm bắt đầu của đoạn 2 trở đi; bộ chấm `collar_f1_3s` dùng những mốc nội bộ này. Vì vậy độ lệch ở mốc kết thúc không trực tiếp đi vào F1 chia chương hiện tại. Báo cáo 26 video `pass` chỉ là phân tích độ nhạy, **không thay mẫu chính**. Đối chiếu payload ablation của run `20260927T121111Z`:

| Biến thể | Macro F1@3s, 35 video | Macro F1@3s, 26 `pass` | Chênh lệch 26 − 35 |
|---|---:|---:|---:|
| duration_only | 0,019751 | 0,021093 | +0,001342 |
| transcript | 0,029383 | 0,030476 | +0,001094 |
| transcript+ocr | 0,050168 | 0,048910 | −0,001258 |
| transcript+scene | 0,048577 | 0,048893 | +0,000316 |

Đây là phân tích độ nhạy từ **chẩn đoán địa phương**, không thay cho chạy benchmark chính thức hoặc xác nhận quyền.

## Việc cần làm cho bản công bố đã chốt

1. Chỉ xuất bản văn bản phương pháp, bảng/biểu đồ số liệu **tổng hợp**. Không đính kèm dữ liệu theo video hoặc các tài sản nguồn. Rà soát bản thảo để bảo đảm hình/bảng không chứa khung hình, phụ đề hay nội dung GT có thể tái tạo.
2. Ghi rõ tập 35 video thuộc một khóa MIT 18.01, đây là chẩn đoán địa phương chứ chưa phải benchmark chính thức/đa khóa. Trích MIT OCW, David Jerison và AVLectures; nêu `truncated_gzip`, `rights_review: pending` và giới hạn nguồn GT, không trình bày các cờ này như đã được giải quyết.
3. Giữ 9 mục `review` trong trung bình chính, công bố lý do và bảng độ nhạy 26 video `pass`. Không sửa GT theo giả thuyết làm tròn. Nếu sau này chấm độ phủ toàn đoạn, chốt trước quy tắc mốc cuối rồi tính lại.
4. Tiếp tục tạo hồ sơ quyền riêng cho từng MP4/SRT và xác minh quyền GT, URL bản phân phối AVLectures, checksum archive đầy đủ. Đây là điều kiện cho việc chia sẻ tài sản hoặc nâng trạng thái kiểm toán, **không phải lý do để âm thầm giảm mẫu còn 26**. Nếu mục đích sử dụng đổi sang clip/khung hình/transcript/GT/model weights hay thương mại, rà quyền lại trước khi phát hành phần đó.

## Tài liệu nội bộ đã đối chiếu

- `experiments/datasets/avlectures_mit001/source_receipt.json`: nguồn GT, checksum, `truncated_gzip`, `rights_review`.
- `experiments/datasets/avlectures_mit001/media_audit.json`: 35 bản ghi MP4, hash và trạng thái.
- `experiments/datasets/avlectures_mit001/run_local_diagnostic.py`: ánh xạ quyền và mốc GT vào unit.
- `experiments/outputs/diagnostic/rq1_mit001_local_runs/20260927T121111Z/diagnostic/full/payloads/chapter.ablation_metrics.json`: F1 theo video/biến thể.

## Câu hỏi chưa giải quyết

- Có chứng cứ cấp từng file về ngoại lệ nội dung và quyền phân phối lại SRT/GT không? Câu hỏi này sẽ quyết định khả năng chia sẻ dữ liệu sau này.
- Tác giả AVLectures có xác nhận quy ước làm tròn mốc GT cuối không?
