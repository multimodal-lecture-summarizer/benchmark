# Đánh giá ASR trên TED-LIUM Release 3

## Phạm vi và chuẩn bị dữ liệu

Thí nghiệm so sánh sáu hệ thống nhận dạng tiếng nói tiếng Anh thuộc các họ kiến trúc khác nhau: Whisper encoder–decoder, Wav2Vec2 CTC, FastConformer CTC, FastConformer RNNT, Paraformer và Qwen3-ASR. Các hệ thống dùng checkpoint có sẵn với revision được pin trong `experiments/registry/asr_architecture_candidates.yaml`. Thí nghiệm **không huấn luyện hoặc tinh chỉnh bằng tập train cục bộ**; tập train không tham gia tính metric hay chọn hệ thống.

Nguồn dữ liệu là snapshot Arrow cục bộ của TED-LIUM Release 3, gồm 270.323 hàng trên 107 shard. Sau khi kiểm tra metadata và marker cần bỏ qua, cohort đánh giá có 507 đoạn validation và 1.155 đoạn native test chấm được. Cả 1.662 đoạn này đã được giải mã thành audio chuẩn, kiểm tra hash và liên kết với transcript tham chiếu. Manifest đóng băng unit ID và checksum; 507 unit ID validation không giao với 1.155 unit ID native test. Bộ Colab mang theo audio và frozen inputs cần thiết, không chuyển toàn bộ Arrow shard.

Notebook `experiments/notebooks/asr_architecture_colab_t4.ipynb` xác minh SHA-256 của bundle, tạo các môi trường Python theo lockfile, tải đúng revision của sáu checkpoint, kiểm tra dependency và GPU Tesla T4, rồi chạy một suy luận thật cho mỗi hệ thống. Chỉ sau khi cả sáu probe thành công mới mở validation. Kết quả validation được dùng để chọn đúng một hệ thống theo WER; native test chạy sau với receipt lựa chọn đã khóa và không tạo lựa chọn mới.

## Kết quả run hoàn tất

Run `architecture_25ce9f1f300b` hoàn tất 3.042/3.042 cặp hệ thống–đoạn trên validation và 6.930/6.930 cặp trên native test. Failure ledger của hai split đều không có lỗi. WER và CER là tỷ lệ lỗi micro trên transcript đã chuẩn hóa bằng `english-asr-nfkc-apostrophe-us-v1`; mỗi đoạn có edit count riêng rồi cộng tử số và mẫu số. Native test được báo là **diagnostic**.

| Hệ thống | WER validation | WER native test |
|---|---:|---:|
| A0 Whisper Base | 6,64% | 6,43% |
| A1 Wav2Vec2 CTC | 8,34% | 8,24% |
| A2 FastConformer CTC | 5,87% | 5,31% |
| A3 FastConformer RNNT | 5,09% | 4,97% |
| A4 Paraformer English | 7,97% | 6,66% |
| **A5 Qwen3-ASR 0.6B** | **3,91%** | **3,53%** |

A5 đứng hạng 1 trên validation và là hệ thống duy nhất có `selected: true`. A5 có CER validation 2,27% và CER native test 1,85%; WER tương ứng là 696/17.783 và 971/27.500 từ tham chiếu. Trên cùng Tesla T4, RTF của A5 khoảng 0,185 ở validation và 0,190 ở native test; vì vậy kết luận ở đây là **độ chính xác cao nhất trong sáu cấu hình đã thử**, không phải nhanh nhất. WER giữa các hệ thống không cô lập riêng tác động của kiến trúc vì checkpoint, dữ liệu huấn luyện trước đó, quy mô và toolchain khác nhau.

Một đoạn native test dài 0,706 giây cho A1 trả transcript rỗng trước đây bị adapter coi là lỗi. Bundle đã sửa chấp nhận đầu ra rỗng hợp lệ và scorer tính hai lỗi xóa đối với tham chiếu “thank you”. Run mới ghi đoạn này là hoàn tất; không bỏ đoạn hoặc sửa metric bằng tay.

## Cách phát biểu kết luận và giới hạn

> Trên cohort TED-LIUM Release 3 đã đóng băng, sáu hệ thống ASR có checkpoint cố định được đánh giá trên 507 đoạn validation và 1.155 đoạn native test. Không dùng tập train cục bộ để huấn luyện hay chọn hệ thống. Sau khi toàn bộ 3.042 lượt validation hoàn tất, Qwen3-ASR 0.6B được chọn duy nhất theo WER thấp nhất (3,91%). Trên 6.930 lượt native test hoàn tất, hệ thống này đạt WER 3,53% và CER 1,85%, thấp nhất trong sáu cấu hình. Kết quả native test là phân tích diagnostic vì tham chiếu/kết quả test đã từng được xem trong quá trình nghiên cứu; không diễn giải như xác nhận trên holdout độc lập.

Giới hạn về lịch sử tiếp xúc native test là lý do trực tiếp cho nhãn diagnostic. Artifact chung còn ghi `scientific_selection_eligible=false` do các cổng qualification khác chưa đóng, gồm provenance của tham chiếu và audit waveform giữa train với evaluation. Vì run này không dùng tập train cục bộ, audit train–evaluation chưa hoàn tất **không có nghĩa là thí nghiệm đã huấn luyện trên đoạn trùng**. Nó cũng không thay thế việc kiểm tra dữ liệu huấn luyện gốc của từng checkpoint phát hành bên ngoài.

## Bằng chứng có thể kiểm tra

- Notebook đã lưu output: `experiments/notebooks/asr_architecture_colab_t4.ipynb`, bundle SHA-256 `25ce9f1f300bd1944f081aac9c1543ee6fe3d2a027105c7f03f637505051027b`.
- Bundle đầu vào `asr_architecture_colab_t4_inputs_empty_transcript_261005_clean.zip` đã bỏ khỏi máy; còn receipt `experiments/outputs/asr_architecture_colab_t4_inputs_empty_transcript_261005_clean.zip.sha256` và bản trên Drive.
- ZIP kết quả hoàn tất từng được kiểm tra với SHA-256 `8f6e359f947097cb85b67b59024b2e58a7872a86fbcacb8a0a6180310270b1cf`, root `runs/architecture_25ce9f1f300b/`. Ngày 2026-10-07, tệp `external-results/runs-20261005T055449Z-1-001.zip` không còn ở máy; kết quả chi tiết còn đường dẫn Drive được lưu trong notebook. ZIP `full-20261004T041611Z-1-001.zip` là phiên validation cũ chưa hoàn tất, chỉ giữ [bản kiểm kê rút gọn](../../reports/asr-architecture-partial-validation-2026-10-04.json), không thay thế ZIP kết quả này.
- `validation/diagnostic/full/selection_receipt.json` có trạng thái `complete`; `native_test/diagnostic/full/parent_index.json` có trạng thái `complete` và trỏ về receipt validation.
- CRC toàn ZIP hợp lệ; SHA-256 của năm payload ASR chính ở mỗi split khớp receipt. Đã kiểm tra đủ cặp duy nhất, trạng thái completed, tổng word errors khớp aggregate và không giao unit ID giữa hai split.
