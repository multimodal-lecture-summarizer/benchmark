# Research: dataset đánh giá tóm tắt + thiết kế nhiều mức độ dài

Date: 2026-10-22. Nối tiếp [research-261022-0929-human-free-summary-evaluation-report.md](research-261022-0929-human-free-summary-evaluation-report.md). Claim đã duyệt: "faithfulness/coverage vs timeline", không dùng người. Chưa tải dataset nào; license/availability chưa xác minh trừ khi ghi khác.

## Kết luận ngắn

1. **Không có dataset nào vừa có speech vừa có tracking GT.** Tìm kiếm không ra. Đừng chờ một bộ "đủ cả"; ghép theo tầng.
2. Vì metric **không cần reference**, dataset chỉ cần cung cấp **timeline đầu vào đa dạng + đa độ dài**. Reference của dataset (nếu có) chỉ là đối chiếu phụ. Hệ quả: vấn đề "creator test đã lộ" của TIB không còn chặn.
3. Dùng ngay **TIB trong repo** làm bộ chính (speech-only, đa độ dài tự nhiên). Thêm **một bộ video đa phương thức nhỏ** để kiểm fusion. Dùng **bộ có GT tracking** cho phần hình ảnh. Thêm **needle injection** (không cần dữ liệu).

## 1. Dataset đã có trong master/repo

| Dataset | Dùng được cho tóm tắt không người? | Ghi chú |
|---|---|---|
| **TIB** (9.103 bản ghi; đủ điều kiện nguồn/reference/nội dung 5.270; train/valid/test 4.213/464/523) | **Có, bộ chính.** Transcript lecture, độ dài nguồn trải short/medium/long | Speech-only. Dev40/selection300 đã niêm phong, test chưa mở, chưa sinh gì. Quyền: private-use policy, 6.171 conditional / 2.932 hold |
| TED-LIUM | Hạn chế | Chỉ 42/50 diagnostic; full corpus HOLD. Bỏ |
| MLPDataset (333 video, 9.021 mốc chuyển slide) | Chưa | Thiếu media căn chỉnh, rights: HOLD. Có thể sinh sự kiện chuyển slide nếu sau này qualify |
| LVVO, CVID | Không trực tiếp | Ảnh tĩnh, phục vụ OCR/detection, không có chuỗi thời gian |
| AccessMath, LectureMath | Không | Thiếu video gốc |
| EduVidQA, VISTA | Không cho đề tài này | RQ3 / chưa qualify media |
| Tracking GT trong repo | **Không có** | Bảng BENCHMARK ghi "no qualified persistent-ID GT yet" |

Nên lấy từ TIB: dùng đủ 3 tầng độ dài nguồn đã có (short/medium/long). TIB là miền bài giảng, nên chỉ là **một miền** trong phạm vi video tổng quát.

## 2. Dataset mới cần xác minh (ứng viên)

Không cái nào đã xác minh license/tải được. Thông tin dưới đây từ kết quả tìm kiếm, cần kiểm tra lại ở trang chính thức.

| Tầng | Ứng viên | Có gì | Cảnh báo |
|---|---|---|---|
| Video đa phương thức có speech | **MMSum** (CVPR 2024): 5.100 video, TB 14,5 phút, 17 nhóm/170 tiểu nhóm, có video + transcript + tóm tắt | Đa miền, dài, đủ cho fusion | License/cách tải chưa rõ; chỉ thấy site dự án. Chưa thấy nhãn tracking |
| | **VideoXum**: 14.001 video, 10 tóm tắt/video; nguồn ActivityNet Captions | Tóm tắt văn bản + video | Annotation tách riêng; video phải tự tải từ ActivityNet (YouTube, có thể mất). Apache-2.0 chỉ thấy trên mirror HF |
| | **YouCook2** | Caption mốc thời gian, ~320s/video | Non-commercial (nguồn mâu thuẫn); một phần video YouTube đã mất; chưa xác nhận có ASR đi kèm |
| | MrHiSum / S-MrHiSum (2025) | Importance theo khung + transcript | Chỉ thấy qua trang tổng hợp, cần đọc bài gốc |
| | VT-SSum | 125K cặp transcript-tóm tắt, 9.616 video | Chỉ văn bản; hữu ích nếu cần thêm nguồn speech-only |
| | Ego4D | Narration có mốc thời gian | Cần ký thỏa thuận truy cập; chưa kiểm tra |
| Tracking GT (gold timeline hình ảnh) | **SportsMOT** | Nhiều người, có track ID | Chỉ người. License CC BY 4.0 theo nguồn phụ |
| | **DanceTrack** (100 video) | Người, track ID | Chỉ người. License chưa tìm được |
| | **MOT17** | Người, track ID | Chỉ người. CC BY-NC-SA 3.0 theo nguồn phụ |
| | **TAO** (2.907 video), **BDD100K MOT** | Có **vật** (đa lớp) | License không rõ ở cả hai. Đây là hai ứng viên duy nhất trong danh sách cho "người **và vật**" |

Nhận xét: để đáp ứng "người và vật", chỉ TAO và BDD100K (và Ego4D ở mức narration) thuộc ứng viên; ba bộ MOT còn lại chỉ có người. BDD100K là cảnh lái xe, TAO đa dạng hơn. Cần kiểm tra license trước.

## 3. Phương án ghép (đề xuất)

| Bộ | Vai trò | Kích cỡ gợi ý (pilot trước, chốt sau) | Đầu vào |
|---|---|---|---|
| **A. TIB** | So sánh mô hình tóm tắt, đa độ dài, đa độ dài nguồn | Dùng cohort sẵn có; không sinh thêm cohort | Speech-only |
| **B. MMSum (hoặc VideoXum)** | Fusion ablation: speech → +OCR → +caption → +track/event | ~100 video, chạy pipeline thật | Speech + hình ảnh |
| **C. Tracking GT** (TAO/BDD + một bộ người) | Gold timeline hình ảnh để tách lỗi tracker khỏi lỗi tóm tắt; kiểm chứng sự kiện | ~20–30 video | Hình ảnh (không speech) |
| **D. Needle injection** | Kiểm recall tuyệt đối theo vị trí/độ dài/nguồn | Sinh ngay, không tải | Tổng hợp trên timeline của A/B |

Không bắt buộc B và C dùng chung video. Hệ quả cần ghi rõ: **không có gold timeline đủ cả speech lẫn hình ảnh**, nên việc tách lỗi upstream được làm riêng từng modality, không trên cùng một video.

Thứ tự: A + D chạy được ngay (không cần tải mới). B và C chờ xác minh license/tải.

## 4. Thiết kế nhiều mức độ dài

Đề xuất (cần pilot để hiệu chỉnh trước khi freeze):

- **3 mức ngân sách tóm tắt: S / M / L.** Định nghĩa theo **tỷ lệ nén** so với token đầu vào (ví dụ ~2% / 5% / 10%) kèm sàn và trần tuyệt đối (ví dụ 40 và 400 từ). Lý do: nguồn dài ngắn chênh nhau cỡ 10 lần, ngân sách tuyệt đối đơn lẻ làm lẫn "tóm tắt ngắn" với "nguồn ngắn". Số cụ thể là giả định, chưa đo.
- **Hai trục tách riêng:** (a) độ dài nguồn: short/medium/long (tầng sẵn có của TIB, độ dài video ở B); (b) mức ngân sách S/M/L. Báo cáo bảng chéo, không gộp.
- **Điều kiện hợp lệ trước khi chấm:** tuân thủ ngân sách (tỷ lệ output nằm trong dải ±X%). Mô hình vượt ngân sách bị đánh dấu, không so điểm trực tiếp. Repo đã ghi "equal allocated caps do not imply equal actual token usage", nên đây là kiểm tra bắt buộc.
- **Metric mới theo mức độ dài** (cơ học, không người):
  1. **Đường cong coverage–ngân sách** và diện tích dưới đường cong (AUC chuẩn hóa). Mô hình tốt phải tăng coverage khi ngân sách tăng.
  2. **Hallucination tại từng mức** (cổng, không được tăng khi ngân sách tăng nhiều).
  3. **Tính lồng nhau (nestedness):** sự kiện quan trọng có trong tóm tắt S phải có trong M và L. Đo bằng tỷ lệ sự kiện S còn trong L và tương quan hạng. Đây là kiểm tra "ưu tiên nhất quán" và chỉ làm được vì có fact inventory.
  4. **Tính đơn điệu:** coverage(S) ≤ coverage(M) ≤ coverage(L) theo từng video; tỷ lệ vi phạm là chỉ số lỗi.
- **Cách sinh:** mỗi mô hình sinh độc lập cho từng mức (cùng prompt, đổi ngân sách). Có thể thêm biến thể "nén từ L xuống S" làm đối chứng, chưa cần ở pilot.
- **Nguồn dài hơn cửa sổ ngữ cảnh:** cần chiến lược chia đoạn thống nhất cho mọi mô hình trước khi đo (repo có S1 fixed chunk, nên tái dùng được).

### Thống kê cho nhiều mức
- Metric chính chốt trước: **AUC chuẩn hóa của coverage–ngân sách** tại ba mức, kèm cổng hallucination ở từng mức.
- So sánh cặp theo từng video; bootstrap theo cụm video; Holm qua ba mức cho phân tích phụ.
- Báo cáo riêng theo từng ô trong bảng nguồn × ngân sách để thấy nơi khác biệt xuất hiện.

## 5. Xung đột với quyết định đã đóng băng

Hai điểm trong repo cần amendment, và là việc của bạn duyệt, tôi không tự đổi:
- "Một word cap toàn cục chọn trước từ train references" (TIB) mâu thuẫn với ba mức ngân sách. Cần amendment bỏ hoặc thay bằng bộ ba S/M/L.
- Ràng buộc "chỉ miền bài giảng" và "TIB text-only, VISTA ngoài phạm vi" đã được bạn bỏ, cần ghi vào master plan.

Cohort TIB đã niêm phong (dev40/selection300), nên giữ nguyên danh sách ID và chỉ đổi giao thức sinh/chấm.

## 6. Rủi ro

- Không có dataset đủ cả speech lẫn tracking: kết luận về fusion đầy đủ chỉ dựa trên B (không GT hình ảnh) và C (không speech). Phải nói rõ trong claim.
- License TAO/BDD/DanceTrack/MMSum/YouCook2 chưa rõ. Một số non-commercial; đề tài học thuật nhưng cần xác nhận.
- Video YouTube có thể không còn (ActivityNet, YouCook2).
- Mốc tỷ lệ nén S/M/L chưa chứng minh phù hợp; cần pilot đo phân phối độ dài.
- B chạy pipeline thật trên video dài tốn T4; giữ ~100 video và FPS thấp.

## 7. Bước tiếp theo

1. Duyệt hướng ghép A+B+C+D và amendment ngân sách S/M/L.
2. Xác minh license, tải và trạng thái video còn sống của MMSum, VideoXum, TAO, BDD100K, SportsMOT (đọc trang chính thức, tải thử vài mẫu, không tải full).
3. Pilot độ dài trên TIB train: đo phân phối token đầu vào, chọn tỷ lệ nén và sàn/trần.
4. Chốt schema timeline + template fact (nền chung cho A–D).
5. Chạy bộ perturbation tests trên A để duyệt metric trước khi freeze.

## Câu hỏi còn mở

- Bạn muốn B là MMSum hay VideoXum (hoặc cả hai)? Quyết định theo license và độ dài video thực tế sau khi xác minh.
- Chấp nhận kết luận fusion tách riêng từng modality vì không có bộ đủ cả hai?
- Ba mức S/M/L hay nhiều hơn? Tôi đề xuất ba để giữ chi phí và số phép so sánh thấp.
- Giữ TIB ở mức nào cho thực nghiệm chính khi miền đã mở rộng?
