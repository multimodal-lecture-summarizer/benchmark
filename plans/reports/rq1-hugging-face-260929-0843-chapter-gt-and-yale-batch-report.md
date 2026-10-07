# RQ1: kiểm Hugging Face và đợt tải Yale theo cohort

**Kiểm:** 2026-09-29, Asia/Bangkok. **Quy tắc:** official RQ1 cần chapter GT phát hành sẵn, video bài giảng dài đúng bản, quyền xử lý nội bộ và công bố số liệu, chất lượng GT/media, split độc lập theo khóa/giảng viên, hash và D2. MITFLD 35 chỉ là pilot. Đây là kiểm nguồn và acquisition qualification, **chưa là official D2**.

## Quyết định nguồn

Chưa xác minh được dataset trên Hugging Face đồng thời đạt toàn bộ điều kiện official. Vì vậy tiếp tục Yale publisher GT theo cohort đã chọn trước; không tải cả 226 MOV, không thay GT Yale bằng nhãn tự tạo.

| Hugging Face | Điểm có giá trị | Gate còn thiếu cho official RQ1 |
|---|---|---|
| [MOSAIC](https://huggingface.co/datasets/AmyIvan/mosaic-emnlp2026) | Mới đáng theo dõi: MOSAIC-G có nhãn topic cấp utterance do người gán trên 6 khóa; 179 khóa/14.942 video toàn bộ theo card. | Bản công khai **không chứa video gốc**, nguồn iCourse163 có quyền riêng; chủ yếu tiếng Trung. Cần xác minh video, quyền, ánh xạ mốc sang timebase và tính phù hợp English primary. Nhãn silver MOSAIC-S không thay GT gold. Dataset viewer hiện lỗi parse. |
| [YTSeg CC BY subset](https://huggingface.co/datasets/retkowski/ytseg-cc-by) | 276 hàng, chapter timestamps và audio có sẵn. | Hub không chứa hình video trong subset; chỉ có `channel_id`, chưa chứng minh course/instructor-disjoint split và quyền media đúng video. |
| [Chapter-Llama/VidChapters](https://huggingface.co/datasets/lucas-ventura/chapter-llama) | Có chapter timestamps, ASR, captions, một số MP4 trên Hub. | Toàn repo khai báo 551 GB; card không xác lập tập lecture đa khóa, provenance/quyền của từng MP4 hay split độc lập. Nhãn MIT ở repo không tự cấp quyền cho video nguồn. Viewer báo lỗi schema. |
| [MITFLD](https://huggingface.co/datasets/robotwang/MITFLD) | Media/fragment phục vụ pilot đã kiểm trước. | Giữ nguyên quyết định pilot: fragment không tự thành chapter GT official phát hành độc lập. |

Tìm trên Hugging Face bằng `lecture video chapter timestamps`, `lecture topic segmentation`, `video chaptering lecture`, và đối chiếu card/file tree trực tiếp. Không coi kết quả tìm kiếm không thấy là bằng chứng mọi dataset đều không tồn tại. [Báo cáo ứng viên trước](./rq1-dataset-research-260928-1902-preexisting-chapter-gt-candidates-report.md) vẫn áp dụng cho CLVTS, SSLectures, AVLectures và các nguồn ngoài Hub.

## Acquisition qualification Yale

[Manifest khóa sẵn 9 bài](./rq1-yale-260929-0843-qualification-batch-manifest.csv) kế thừa [mẫu lựa chọn theo hash trước khi xem kết quả](./rq1-yale-260928-1952-nine-course-qa-sample.csv). Đối chiếu URL, Content-Length từ [HEAD ledger 226 bài](./rq1-yale-260928-1937-higher-resolution-mov-head-scan.csv) và [ledger quyền thành phần](./rq1-yale-260928-2025-component-rights-internal-use-ledger.csv). Tổng mẫu 9 bài: **5,073 GiB / 9,023 giờ**. Ba bài ENGL 291/300/310 đang `rights_hold`; script không tải. Sáu bài trong acquisition qualification: **3,776 GiB / 6,633 giờ**; ECON 159 L2 và PHYS 200 L19 là file đã có, bốn file mới tải tổng **2,620 GiB**.

Batch downloader lịch sử (download_yale_rq1_qualification_batch.py; đã xóa khỏi checkout ngày 2026-10-07) đọc manifest trong một lệnh, tái dùng hai file có sẵn sau khi so byte và SHA-256, bỏ qua `rights_hold`, hỗ trợ HTTP Range cho `.part`, kiểm byte/hash và ghi receipt cục bộ vào thư mục dataset được `.gitignore`. Chạy thử `--dry-run` và biên dịch Python đã đạt. Tải nguyên file bị treo; byte-range 8 MiB được HTTP 206 và trả đủ 8.388.608 byte sau 23,15 giây. Vì vậy downloader dùng range có thể tiếp tục và tối đa bốn file đồng thời. **Đợt tải xong: 6/6 file được ghi trong [receipt kiểm được](./rq1-yale-260929-0843-qualification-batch-receipt.json), 4.054.394.835 byte (3,776 GiB), 0 lỗi, 0 `.part`; hai file tái dùng và bốn file mới đều có SHA-256.** Receipt cục bộ có thêm đường file ở `experiments/datasets/yale_rq1_qualification/qualification_download_receipt.json`; `batch-stderr.log` rỗng. Không dùng manifest này để âm thầm chọn final test hoặc công bố số official.

**ENGL 220 L23, file đầu hoàn tất:** 386.792.955 byte; SHA-256 `8413c9e25b94db5cbc43123b468f55fb42f9c5995d5d569654bccb034eee1dd8`. `ffprobe`: H.264 640×360, AAC, cả hai luồng bắt đầu PTS 0, duration khoảng 2643,977 s; sai khác với duration GT ledger 0,009 s. `ffmpeg -xerror` giải mã hình+tiếng tới EOF, exit 0. Kiểm packet PTS: video 79.240, audio 113.867, không bước lùi; bước lớn nhất lần lượt 0,033367 và 0,023220 s. Mười frame lấy đều toàn bài chỉ thấy giảng viên trước bảng trống trong mẫu; visual OCR ở bài này có thể rất thấp, chưa phải policy loại và chưa suy ra toàn timeline. Contact sheet tạm không lưu trong báo cáo.

PaddleOCR English ở 8 thời điểm cách 300 s (300–2400 s) đều chỉ có **1 detection/1 dòng proxy ≥4 ký tự/confidence ≥0,70**, phù hợp watermark Yale nhìn thấy trong frame; chưa có bằng chứng chữ học thuật đọc được. Đây không phải CER hoặc chứng minh toàn video thiếu chữ.

`base.en` offline đã chạy trên bốn cửa sổ 40 s quanh các mốc Yale 117/1034/1538/2202 s. Kết quả ASR và các thời điểm câu ước lượng trước đây chỉ là chẩn đoán, **không dùng để gắn nhãn, sửa GT hoặc quyết định đạt ±3 s**. Phép kiểm tiếp chỉ đối chiếu provenance/cấu trúc mốc Yale với duration và PTS của MOV.

**ECON 252 L6, file thứ hai hoàn tất:** 603.398.593 byte; SHA-256 `bcf1ed9b582c7d25fe3f29398ffe98d90554e7308de3a395cb29c21e7ac42232`. H.264 640×360/AAC, cùng start PTS 0, duration 4097,297 s khớp ledger; full decode `ffmpeg -xerror` exit 0. Packet PTS: video 122.796, audio 176.456, không bước lùi, bước lớn nhất 0,033367/0,023220 s. Hai mươi frame rải toàn bài thấy bảng phấn; cuối bài có đồ thị trình chiếu và bảng dữ liệu, nên `visual_source_review` vẫn bắt buộc. PaddleOCR English trên 13 frame cách 300 s và bốn thời điểm hình biểu đồ/bảng bổ sung có tín hiệu chữ, ví dụ 3600 s: 89 detection, 29 dòng ≥4 ký tự/confidence ≥0,70. Chỉ là proxy phát hiện chữ, không phải CER hay chứng minh nội dung OCR đúng. Dùng shim `np.sctypes` trong tiến trình vì PaddleOCR cài sẵn không nhập được với NumPy 2; không sửa thư viện. Frame/contact sheet tạm đã xóa.

`base.en` offline trên năm cửa sổ 40 s quanh GT 388/1200/2504/3090/3419 s chỉ là kiểm timebase/diễn ngôn sơ bộ. Các onset do ASR ước lượng trước đây **không được dùng làm nhãn hoặc mốc thay thế**. Theo yêu cầu hiện hành, không gắn nhãn mới và không cần người rà độc lập; giữ nguyên GT Yale, chỉ kiểm provenance/cấu trúc trên đúng media và báo giới hạn về chất lượng ngữ nghĩa.

**ECON 251 L1 và PHYS 201 L10, hai file cuối:** SHA-256 lần lượt `a28ecd0df64eafcfb6aadd804e3fa6159239583f805dce812b7843aac4220f2a` (939.375.786 byte) và `ecbec411b1a7602c08df621734460b80058a2952de079dbde22df1f8735f1724` (883.319.266 byte). Cả hai H.264 640×360/AAC, start PTS 0, duration luồng 4456,256/4240,274 s khớp ledger trong 0,02 s, `ffmpeg -xerror` full decode exit 0. ECON 251: 133.554 video + 191.915 audio packet; PHYS 201: 127.081 + 182.614; không PTS lùi, bước lớn nhất 0,033367/0,023220 s ở cả hai.

Mỗi file xem 20 frame trải toàn timeline. ECON 251 có biểu đồ/slide chiếu, gồm đồ thị và trang tài liệu, nên `visual_source_review` không được bỏ. PHYS 201 chủ yếu bảng phấn, công thức/sơ đồ vật lý. PaddleOCR English ở 14 frame cách 300 s của ECON 251 cho proxy ≥3 dòng ở **4/14**; PHYS 201 ở 13 frame cho **3/13**. Ở ECON 251, proxy tập trung ở slide cuối bài (3000/3300/3600/4200 s); ở PHYS 201, chữ phấn ký hiệu toán có thể bị OCR đọc sai. Không có CER hay quyền hình từ các phép đếm này. Frame/contact sheet tạm đã xóa.

`base.en` offline đã kiểm cửa sổ audio quanh sáu mốc Yale của ECON 251 và ba mốc của PHYS 201. Các diễn giải ASR về chuyển ý trước đây **không dùng làm nhãn**; chỉ nguồn Yale và phép kiểm media/PTS khách quan được dùng cho GT.

## Trạng thái sau batch

| Gate | Kết quả |
|---|---|
| Media/acquisition | 6/6 file đủ byte, SHA-256 trong receipt; bốn file mới full decode và PTS sạch; hai file cũ đã có báo cáo QA riêng. |
| GT cấu trúc | 28 mốc nội bộ do Yale công bố trên sáu bài; không có cờ cấu trúc trong metadata ledger. Không tự xác minh hoặc gắn nhãn onset ngữ nghĩa. |
| Visual | Slide/biểu đồ ở ECON 251/252, bảng phấn ở PHYS 200/201, chủ yếu talking-head ở ECON 159 và ENGL 220; OCR coverage khác nhau, chưa có CER. |
| Quyền | 2 bài kinh tế cần xác minh nguồn biểu đồ; 4 bài còn lại chưa kiểm xong toàn bộ thành phần. 3 bài văn học từ manifest vẫn `rights_hold`, không tải. |
| Split/D2 | Sáu bài từ sáu khóa nhưng chỉ **năm giảng viên** vì PHYS 200/201 cùng giảng viên. Còn quá ít và chưa qua quyền/GT để niêm phong split hoặc gọi official; **0 bài official eligible đã xác nhận**. |

## Điều kiện để nâng lên D2

1. Xác minh quyền nội bộ từng thành phần của sáu file, nhất là biểu đồ ECON 251/252; giải quyết hoặc thay thế ba `rights_hold` theo quy tắc chọn trước.
2. Kiểm full decode/PTS, OCR detection nhiều thời điểm và provenance/cấu trúc mốc GT Yale so với duration/timebase của đúng MOV; không tạo GT OCR/chapter mới.
3. Đếm cohort thật sự đạt sau attrition; khóa split theo giảng viên (PHYS 200/201 cùng giảng viên), không chọn bằng kết quả mô hình; amend kế hoạch RQ1 vì Yale thay nguồn preregistered.
4. Ghi hash, URL/revision, license/rights decision, media/GT receipt, tài nguyên D2 ≤12 giờ và ≤50 GiB; chỉ sau đó mới chạy official.

## Câu hỏi chưa giải quyết

1. Nguồn và quyền nội bộ của biểu đồ/slide ECON 251/252 có xác minh được không? Các bài còn lại có thành phần ngắn bị bỏ sót trong mẫu frame không?
2. Sau kiểm GT nguồn/cấu trúc, quyền và visual kỹ thuật không tạo nhãn, còn bao nhiêu bài/giảng viên đủ cho split có ý nghĩa thống kê?
3. MOSAIC-G có nguồn video đủ quyền và English subset đáng kể hay không? Hiện không làm nguồn thay thế.
