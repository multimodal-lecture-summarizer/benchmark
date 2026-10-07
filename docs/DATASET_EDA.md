# Dataset EDA: scope and evidence

## Quy trình EDA cho cohort mới

Chỉ tạo notebook EDA khi đã chọn dataset **có nhãn sẵn đúng tác vụ**. Ngoài TIB cho RQ2, chỉ dùng dữ liệu miền video bài giảng đã xác minh; không đưa video tổng quát vào benchmark phụ. Theo quyết định mới, EDA TIB phải kiểm kê mọi bản ghi của cả `train`, `valid`, `test` ở revision đã ghim, không lọc `genre`; thể loại là một chiều phân tích, không phải điều kiện loại. Notebook phải đọc dữ liệu thật của **mọi đơn vị trong cohort định dùng**, đối chiếu ID nguồn với ID đọc được, và nêu rõ phần chỉ kiểm tra metadata, phần đã giải mã media, phần kiểm tra mẫu. Phân tích số lượng theo split/nguồn/nhóm, độ dài và chất lượng media, độ đầy đủ và phân bố nhãn, dữ liệu thiếu/lỗi, trùng hoặc gần trùng, leakage và các strata ảnh hưởng metric. Với media quá lớn, ghi quy tắc lấy mẫu và giới hạn suy luận; không gọi đó là EDA toàn bộ media.

Kết thúc notebook bằng bảng quyết định theo dataset/cohort: **giữ**, **sửa/lọc theo quy tắc chốt trước**, **giới hạn mục tiêu**, hoặc **loại/đổi dataset**; có ID, mẫu số, lý do và ảnh hưởng đến split/GT. Sau đó mới đóng băng cohort và tạo notebook đánh giá các ứng viên trên cùng thang đo. Không dùng notebook smoke để thay cho EDA. Final test giữ nguyên ranh giới holdout; những kiểm tra dựa trên nhãn/đầu ra test được hoãn theo protocol.

**Trạng thái 2026-10-03:** [Notebook EDA toàn bộ dữ liệu cục bộ trước khi chia tập](../experiments/notebooks/diagnostics/full-corpus-pre-split-eda.ipynb) đã chạy 10/10 code cell, có bảng và biểu đồ. Kết quả máy đọc được nằm trong `experiments/outputs/full_corpus_eda_261003/`. Nó phân tích toàn bộ annotation/metadata hiện có, nhưng không giải mã toàn bộ waveform/video và không thay thế điều kiện chấm benchmark. Phần lịch sử TED-LIUM/TVSum bên dưới không còn là mô tả đầy đủ tình trạng dữ liệu.

**Cập nhật 2026-10-07:** [Notebook TIB mới](../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) kiểm kê **toàn bộ 9.103 bản ghi dự kiến ở `train`/`valid`/`test`**, không lọc genre và có thể chạy độc lập trên Colab. Nó chưa chạy vì máy hiện không truy cập được revision Hugging Face đã ghim. [Notebook TIB cũ](../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) giữ output chi tiết của 20 DOI lịch sử. Khi notebook mới chạy, việc đọc nội dung/reference của `test` làm mất trạng thái holdout chưa xem của split này cho các kết luận sau. Notebook VISTA đã được bổ sung luồng duyệt **toàn bộ 1.859 ID validation**, tải và kiểm tra từng MP4 trên Colab, ghi checkpoint và xóa media tạm sau mỗi video. Phần này cũng chưa chạy vì cần quyền truy cập VISTA trên Colab; output cũ chỉ chứng minh 40 video được `ffprobe`. Cả hai chưa đạt gate EDA đầy đủ; abstract của creator chưa được xác nhận là ground truth phù hợp và kiểm tra toàn bộ media không đồng nghĩa giải mã mọi frame.

**Đổi phạm vi TIB cùng ngày:** Người dùng yêu cầu bỏ bộ lọc `Lecture` và kiểm kê **cả ba split**. Đợt EDA tiếp theo phải bao phủ mọi bản ghi theo cặp `(split, source_index)`, kể cả DOI thiếu/trùng hoặc transcript lỗi; số bản ghi có thể đưa vào đánh giá chưa biết trước khi chạy. Kết quả 20 và 70 bài ở các notebook/receipt cũ chỉ là subset lịch sử, không được suy rộng thành kết quả trên toàn dataset.

## EDA toàn bộ snapshot cục bộ trước khi chia tập nghiên cứu

| Bộ dữ liệu | Phạm vi đã đọc | Phát hiện quyết định |
|---|---|---|
| TED-LIUM 3 | 270.323 dòng Arrow từ train/validation/test gốc; trường ID, transcript, speaker, source và thời điểm | 268.263/507/1.155 dòng có transcript ASR dùng được theo thứ tự ba split. 84 nhãn validation và 314 nhãn test là `ignore_time_segment_in_scoring`; không được đưa vào WER. 53 GB waveform nhúng chưa giải mã toàn bộ. |
| IIIT-CVID | Toàn bộ 5.475 ảnh frame + XML; 137.745 nhãn crop và header ảnh crop | 82.263/15.379/40.103 dòng OCR ở train/val/test. Không thiếu cặp frame/XML hoặc crop/nhãn. Có 22 hộp chữ sai hình học và 124 XML khai báo sai kích thước ảnh. |
| EduViQA | 20 video, 20 transcript, 883 Q&A và metadata chunk | Q&A phủ 20 video; 583 mốc chuyển đoạn do thuật toán tạo, không phải scene GT độc lập. |
| SlideVQA | 14.484 Q&A ở 2.619 deck qua ba split gốc | Deck không chồng giữa split; ảnh slide không có trong snapshot cục bộ. |
| VidChapters | 817.076 ID annotation trong JSON và 8 video cục bộ | 2 GB `chapters.pkl` chưa giải tuần tự an toàn; chưa thể khẳng định đã phân tích nội dung chapter của toàn bộ ID. |
| YTSeg | 16.404 dòng Parquet, 10 video cục bộ | Nhãn creator chapter phù hợp chaptering; không tương đương nhãn scene cut. |
| Yale / MIT001 | Metadata của 51 / 35 video cục bộ, MIT001 có 277 đoạn | Nguồn còn ở mức qualification/diagnostic; quyền và chất lượng nhãn phải đối chiếu theo video. |
| TVSum | Kiểm kê thư mục cục bộ | Rỗng; không có media/annotation cục bộ để chạy EDA thực nghiệm. |

Quét toàn bộ frame IIIT-CVID tìm thấy **0 nhóm ảnh trùng byte qua split** và **469 cặp dHash gần giống qua split**, ảnh hưởng 263 frame. Không cặp nào trong số này đồng thời đạt ngưỡng chồng từ XML cao đã khai báo (Jaccard ≥ 0,8 với ≥5 từ hợp). dHash là danh sách cần xem lại, không phải lý do tự động loại 263 frame. Bản readiness cũ chỉ loại ba frame validation trong cohort nhỏ; không được suy diễn điều đó sang toàn bộ dữ liệu.

**Quyết định trước chia tập:** TED-LIUM có quy mô đủ để thiết kế benchmark ASR lớn hơn cohort 20; lọc nhãn không chấm và gom theo source/speaker. IIIT-CVID có nhãn OCR phù hợp, cần phân xử 22 box và 124 XML size cùng các cặp gần giống trước khi khóa tập. Các video cục bộ khác hiện chưa cung cấp ground truth độc lập đúng tác vụ cho scene cut, keyframe selection và visual caption. EDA này **chưa chọn hoặc tạo split nghiên cứu mới**.

**Giới hạn khoa học:** Theo yêu cầu xem toàn bộ dữ liệu trước khi chia, thống kê EDA đã đọc reference text/XML của split nguồn tên `test`. Split nguồn này không còn được mô tả là chưa xem nhãn khi thiết kế cohort mới. Không có inference mô hình hay điểm benchmark nào được dùng trong EDA. Các thống kê media video dựa trên container `ffprobe`, chưa giải mã mọi frame. Snapshot TIB của RQ2 có EDA và kết quả riêng, không nằm trong kiểm kê thư mục cục bộ này.

---

**Phần lịch sử dưới đây:** TED-LIUM và TVSum, không thay thế EDA snapshot hiện hành.

## EDA cần hoàn tất trước khi dùng bộ dữ liệu chính

| Phạm vi | Bộ dữ liệu/cohort theo kế hoạch | Bằng chứng EDA trong notebook đã chạy |
|---------|---------------------------------|----------------------------------------|
| RQ1 | Không chạy lại theo quyết định hiện hành | Notebook đầu vào/qualification cũ là bằng chứng lịch sử, không phải gate EDA cho các tác vụ còn lại. |
| RQ2 | VISTA; TIB hoặc fallback đã đăng ký | [EDA TIB toàn bộ ba split](../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) dự kiến 9.103 bản ghi bất kể genre và chưa chạy; [bản valid cũ](../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) có output chi tiết 20 DOI lịch sử. [EDA VISTA](../experiments/notebooks/diagnostics/vista-validation-media-eda-colab.ipynb) có output media 40/1.859 video validation và ô mở rộng toàn validation chưa chạy. Chưa xác nhận GT cho cohort cuối. |
| RQ3 | EduVidQA và tập bằng chứng tự tạo nếu dùng | Notebook snapshot cục bộ đã kiểm kê **EduViQA** 20 video/883 QA; đây là dataset khác **EduVidQA**. Chưa xác nhận nguồn nhãn, evidence và cohort EduVidQA đánh giá chính thức. |
| RQ4 | Các cohort đầu vào dùng trong phép so sánh hiệu năng | Kế thừa EDA tương ứng từ RQ1–RQ3 và phải xác nhận các hệ thống được so sánh trên cùng item. |

Mỗi dòng chỉ được đổi thành **đạt** khi đã chạy notebook trên dữ liệu thật và lưu `.ipynb` có bảng số lượng, phân bố/biểu đồ, nhận xét ngắn, ngoại lệ và quyết định giữ/giới hạn/loại ngay trong các cell output/markdown. Ghi đường dẫn notebook, run receipt, nguồn/phiên bản, manifest/cohort, split và mẫu số cho từng bảng (`đã chọn / quan sát được / thiếu / loại`). Nếu chỉ khảo sát mẫu, ghi rõ cách lấy mẫu; không suy rộng thành toàn bộ cohort. Biểu đồ rỗng, dữ liệu giả, dry run hoặc chỉ có mã notebook không được tính là EDA hoàn tất.

Với final test còn khóa của các dataset khác, chỉ phân tích metadata được phép trước khi chấm; không mở đặc trưng, đáp án chuẩn hoặc kết quả phụ thuộc nhãn để điều chỉnh quyết định. Riêng TIB theo chỉ đạo 2026-10-07 sẽ đọc cả nội dung/reference của creator `test` trong EDA toàn dataset, nên split đó **không còn là unseen holdout** sau lần chạy. Tiêu chí chi tiết theo từng RQ nằm trong [dataset manifest](../plans/260901-unified-scientific-benchmark/framework/01-dataset-manifest.md#executed-eda-gate-before-research-use).

---

**EDA lịch sử bên dưới: TED-LIUM và TVSum; không phải cohort RQ chính. TVSum không phải ứng viên benchmark hiện hành vì không bảo đảm toàn bộ video thuộc miền bài giảng.**

## 4.1 Mô tả tập dữ liệu

Quá trình thực nghiệm được tiến hành độc lập trên hai tập dữ liệu khác nhau, phục vụ cho hai bài toán cốt lõi của hệ thống: nhận dạng giọng nói và tóm tắt video.

*   **TEDLIUM**: Đây là một kho dữ liệu âm thanh chuyên dụng được trích xuất từ các bài diễn thuyết thực tế bằng tiếng Anh. Môi trường âm thanh trong tập dữ liệu này rất sát với bài toán thực tế mà đồ án hướng tới: diễn giả nói chuyện trong một hội trường lớn, có tiếng ồn nền, có sự đa dạng về ngữ điệu và tốc độ nói. Việc sử dụng TEDLIUM giúp đo đạc chính xác khả năng bóc tách khoảng lặng và độ chuẩn xác của mô hình giải mã văn bản.
*   **TVSUM**: Tập dữ liệu này chứa năm mươi video ngắn được thu thập từ YouTube, bao trùm mười chủ đề khác nhau như tin tức, phim tài liệu, bài giảng và hướng dẫn thực hành. Điểm giá trị nhất của TVSUM là mỗi video đều đi kèm với nhãn đánh giá mức độ quan trọng ở cấp độ khung hình do con người gán thủ công. Dữ liệu này đóng vai trò làm tiêu chuẩn vàng để hệ thống đối chiếu và đo lường khả năng trích xuất các khung hình mang tính trọng tâm.

---

## 4.2 Phân tích Dữ liệu TED-LIUM (Audio & ASR)

Tập dữ liệu TED-LIUM bao gồm các phân đoạn âm thanh từ các bài thuyết trình TED Talks thực tế, chứa các đặc điểm âm học phong phú (tiếng ồn khán phòng, tốc độ nói thay đổi, giọng nói nam/nữ đa dạng). 

### 4.2.1 Quy mô dữ liệu (Data Quantities)
* **Tổng số phân đoạn ghi nhận trong metadata**: 150 phân đoạn
* **Tổng số file âm thanh (.wav)**: 150 file (được lưu tại thư mục `audio/`)

### 4.2.2 Phân phối Thời lượng Phân đoạn (Duration Distribution)
Thời lượng của phân đoạn phản ánh cách các câu thuyết trình được ngắt nghỉ theo hơi thở hoặc nhịp điệu của người nói.
* **Thời lượng trung bình (Mean)**: $9.65$ giây
* **Thời lượng trung vị (Median)**: $9.84$ giây
* **Độ lệch chuẩn (Std Dev)**: $4.32$ giây
* **Thời lượng ngắn nhất (Min)**: $1.03$ giây
* **Thời lượng dài nhất (Max)**: $23.57$ giây

![Phân phối thời lượng phân đoạn TED-LIUM](../experiments/images/tedlium_durations.png)

> [!NOTE]
> Hơn 50% các mẫu phân đoạn nằm trong khoảng ngắn từ **7.25 giây đến 12.44 giây** (phạm vi 25% - 75%). Điều này cho thấy VAD (Voice Activity Detection) sẽ phải xử lý các điểm dừng/ngắt giọng với tần suất rất cao.

### 4.2.3 Phân tích Tốc độ Nói (Speaking Rate - WPS)
Tốc độ nói được đo bằng số từ trên giây (**Words Per Second - WPS**) đối với 128 phân đoạn hợp lệ (loại bỏ các nhãn segment trống hoặc segment bị bỏ qua khi tính điểm):
* **Tốc độ nói trung bình**: $3.08$ WPS (~185 từ/phút)
* **Độ lệch chuẩn**: $0.74$ WPS
* **Tốc độ nói nhỏ nhất (Min)**: $0.89$ WPS (Nói rất chậm/ngắt quãng)
* **Tốc độ nói lớn nhất (Max)**: $4.64$ WPS (Nói rất nhanh/dồn dập)

![Phân phối tốc độ nói (WPS) TED-LIUM](../experiments/images/tedlium_wps.png)

> [!IMPORTANT]
> Tốc độ nói trung bình ~3.08 WPS là một thử thách đối với các mô hình STT (Speech-to-Text) truyền thống. Người nói quá nhanh (>4 WPS) dễ gây ra lỗi nuốt từ (deletion error), trong khi người nói quá chậm (<1.5 WPS) dễ dẫn đến lỗi lặp/thêm từ (insertion error). Do đó hệ thống cần WhisperX với khả năng căn chỉnh cấp độ từ (word-level alignment) để tối ưu hóa.

---

## 4.3 Phân tích Dữ liệu TVSum (Video Summarization)

TVSum chứa các video YouTube thuộc nhiều chủ đề khác nhau. Mỗi khung hình (frame) được đánh giá điểm quan trọng từ 1 đến 5 bởi 20 người chấm (annotators) độc lập.

### 4.3.1 Quy mô dữ liệu (Data Quantities)
* **Tổng số video**: 50 videos
* **Số danh mục (Category)**: 10 danh mục (mỗi danh mục có chính xác 5 videos):
  * **BK** (Book Review): 5 videos
  * **BT** (Beauty): 5 videos
  * **DS** (Dog Show): 5 videos
  * **FM** (Food & Drink): 5 videos
  * **GA** (Gaming): 5 videos
  * **MS** (Movie Show): 5 videos
  * **PK** (Parkour): 5 videos
  * **PR** (Personal Product Review): 5 videos
  * **VT** (Vehicle Trip): 5 videos
  * **VU** (Video Gaming): 5 videos
* **Tổng số khung hình (frames) được phân tích**: 352,353 frames

### 4.3.2 Phân phối Điểm số Quan trọng (Importance Scores)
* **Điểm quan trọng trung bình**: $2.7661 \pm 0.4431$ (trên thang điểm 5.0)
* **Độ lệch đồng thuận trung bình (Annotator Consensus Std Dev)**: $0.8190$

![Phân phối điểm số và độ lệch đồng thuận TVSum](../experiments/images/tvsum_scores.png)

> [!TIP]
> Độ lệch đồng thuận $0.8190$ cho thấy có sự khác biệt tương đối lớn trong cảm nhận của con người về độ quan trọng của các khung hình, phản ánh tính chủ quan trong bài toán tóm tắt video.

### 4.3.3 Ngưỡng Lọc Khung hình Khóa & Tỷ lệ Nén (Compression Thresholds)
Để chọn ra các khung hình tiêu biểu, chúng ta cần đặt ngưỡng điểm trung bình nhằm giữ lại các khung hình thực sự có giá trị:
* **Ngưỡng $\ge 3.0$**: Chọn **31.90%** số lượng khung hình của video.
* **Ngưỡng $\ge 4.0$ (Độ quan trọng cao)**: Chỉ giữ lại **3.42%** số lượng khung hình.
* **Ngưỡng $\ge 4.5$ (Độ quan trọng cực cao)**: Chỉ giữ lại **0.17%** số lượng khung hình.

![Tỷ lệ chọn khung hình khóa theo ngưỡng điểm TVSum](../experiments/images/tvsum_thresholds.png)

### 4.3.4 Ý nghĩa đối với Thiết kế Bộ Tóm tắt Hình ảnh (Visual Summarizer)
* Điểm số trung bình chủ yếu tập trung quanh mức trung vị $2.5 - 3.0$. Việc áp dụng một ngưỡng cứng (ví dụ: $\ge 4.0$) sẽ khiến summary video quá ngắn và mất thông tin.
* Giải pháp tối ưu là thiết lập **tỷ lệ nén động (dynamic compression ratio)** hoặc **ngưỡng tương đối (top K%)** (thường là chọn top 10% - 20% khung hình có điểm cao nhất của mỗi video) thay vì dùng ngưỡng tuyệt đối cố định cho mọi video.
