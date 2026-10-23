# Research: đánh giá tóm tắt không dùng người

Date: 2026-10-22. Input summarizer = timeline văn bản có timestamp (speech/OCR/caption/track/event). Scope: video tổng quát, người+vật, có tracking.

## Kết luận ngắn

Không có metric tự động nào "chứng minh" chất lượng theo cảm nhận người nếu không có người. Cái làm được: đo **trung thực + độ phủ so với đầu vào** bằng ground truth dựng từ chính timeline, và chứng minh metric hoạt động bằng **kiểm thử nhiễu có kiểm soát** (không cần người). Claim phải giới hạn: "faithfulness/coverage vs timeline", không phải "người thấy tốt hơn".

## Bằng chứng từ tìm kiếm

- AlignScore (355M, unified alignment) ngang/hơn metric dựa ChatGPT/GPT-4 trên factual consistency: [arXiv 2305.16739](https://arxiv.org/abs/2305.16739v1).
- QuestEval: reference-free, đo cả precision (consistency) và recall (coverage); cần cả hai mới khớp cảm nhận người: [HAL](https://hal.sorbonne-universite.fr/hal-03923328).
- QAFactEval: +14% so QA-metric trước trên SummaC; QA và entailment bổ sung nhau, gộp được: [arXiv 2112.08542](https://arxiv.org/pdf/2112.08542).
- Stress test 6 metric reference-free (gồm AlignScore, SummaC, MiniCheck) trên tóm tắt tài liệu dài, 11/2025: [arXiv 2511.07689](https://arxiv.org/pdf/2511.07689).
- Synthetic facts: sinh nguồn từ fact đã biết, đo fact nào còn trong tóm tắt, không cần reference. Validation gốc vẫn so với người: [arXiv 2204.04869](https://arxiv.org/pdf/2204.04869), [thesis](https://digitalcommons.calpoly.edu/theses/2474).
- LLM-judge không grounding người có giới hạn rõ (position/verbosity/self-preference, bỏ sót lỗi sự thật): [No Free Labels](https://arxiv.org/html/2503.05061v1); giảm bias bằng hoán đổi thứ tự, judge khác họ.

Giới hạn bằng chứng: các metric trên được validate bằng người trên miền khác (chủ yếu tin tức/tài liệu). Chuyển sang timeline có timestamp **chưa được kiểm chứng**. Chưa tìm thấy meta-eval dạng perturbation thuần cho metric tóm tắt; mục 4 là thiết kế đề xuất, không phải phương pháp đã công bố.

## Thiết kế đề xuất (4 tầng, 0 người)

### 1. Fact inventory dựng từ timeline (ground truth cơ học)
- Mỗi dòng timeline có cấu trúc (event, OCR string, entity+class, track id, mốc thời gian) -> atomic fact bằng template, không dùng LLM sinh.
- Salience rule chốt trước, ví dụ: track sống lâu, sự kiện lặp, nội dung vừa nói vừa hiện, OCR lớn/lâu. Fact "quan trọng" = qua ngưỡng.
- Coverage = recall fact quan trọng được tóm tắt nhắc tới (khớp bằng NLI/embedding + khớp chuỗi cho entity/số).

### 2. Faithfulness
- AlignScore hoặc MiniCheck/SummaC (chạy được T4, 355M-ish).
- Hallucination cơ học: entity, lớp vật, số, timestamp trong tóm tắt không tồn tại trong timeline.
- Temporal grounding: mốc thời gian tóm tắt nêu phải nằm trong cửa sổ của fact gốc.

### 3. QA templated
- Câu hỏi sinh bằng template từ fact table ("Khi nào X xuất hiện?", "Có bao nhiêu Y?"). Tránh lỗi của question generator.
- QA model trả lời **chỉ từ tóm tắt**; accuracy = information retention. Bổ sung: QuestEval/QAFactEval làm đối chứng độc lập.

### 4. Needle injection (kiểm soát hoàn toàn)
- Chèn K fact tổng hợp vào vị trí ngẫu nhiên trong timeline, đo tỷ lệ còn lại sau tóm tắt theo vị trí, độ dài, nguồn (speech vs visual).
- Cho ground truth tuyệt đối về recall; lộ ra bias đầu/cuối (lost-in-the-middle) và nguồn nào bị bỏ.

### Judge LLM: phụ, không là metric chính
Nếu dùng: hoán đổi thứ tự, 3 lần lặp, judge khác họ với generator, cross-family agreement. Chỉ báo cáo như đối chứng hội tụ, không dùng để xếp hạng chính.

## Chứng minh metric có hiệu lực mà không cần người

Known-groups / perturbation tests, chạy trước khi dùng:
1. **Oracle vs random**: tóm tắt oracle (chọn thẳng fact quan trọng) phải điểm cao hơn random; tóm tắt xáo thứ tự thời gian bị phạt ở ordering.
2. **Dose-response**: xóa k% fact -> coverage giảm đơn điệu; chèn m% fact sai -> faithfulness giảm đơn điệu.
3. **Length bias**: điểm có tăng chỉ vì dài không? Kiểm ở độ dài cố định.
4. **Hội tụ**: Kendall tau giữa họ metric độc lập (NLI, QA, cơ học). Tau thấp = metric đo cái khác nhau, báo cáo không gộp.
5. **Mượn validity ngoài**: ghi rõ các metric đã được validate bởi người trong bài gốc (không phải của đề tài), kèm cảnh báo chuyển miền.

## Tách lỗi upstream khỏi lỗi tóm tắt

Hai điều kiện đầu vào:
- **Gold timeline**: dựng từ nhãn có sẵn của dataset (transcript gốc, GT track của MOT/DanceTrack, caption có sẵn). Không cần người mới.
- **Pipeline timeline**: ASR + detector + tracker thật.
Chênh lệch = chi phí lỗi upstream; phần còn lại thuộc bộ tóm tắt. Metric trên timeline đo trung thực với timeline, nên claim về video thật chỉ đến mức gold timeline.

## Thống kê

- Metric chính chốt trước: **recall fact quan trọng ở độ dài cố định**, ràng buộc cổng: hallucination rate không vượt baseline + ngưỡng đã định. Không gộp thành điểm tổng hợp.
- Bootstrap cặp theo cụm video, Holm, effect size. Khoảng chứa 0 -> `no_selection`.
- Tính cỡ mẫu từ phương sai pilot trước khi freeze.

## Rủi ro

- Salience rule là lựa chọn chủ quan; kết quả có thể đổi theo rule. Giảm: báo cáo độ nhạy với 2-3 rule.
- Vòng tròn: metric và generator cùng dùng timeline nên chỉ đo trung thực nội tại.
- NLI/AlignScore xử lý tốt câu văn, kém với dữ liệu dạng bảng/timestamp: cần tuần tự hóa câu hoàn chỉnh.
- Không có người: không thể bác claim "người thấy khác". Ghi rõ như giới hạn, không che.

## Bước tiếp theo

1. Chốt schema timeline và template fact (nền cho cả metric lẫn đầu vào summarizer).
2. Định nghĩa salience rule + 2 rule dự phòng.
3. Cài và thử AlignScore/MiniCheck, QA model trên T4; đo thời gian.
4. Chạy bộ perturbation tests trên 20-30 timeline để duyệt metric trước khi freeze protocol.
5. Viết amendment: bỏ ràng buộc bài giảng; đánh giá tóm tắt không dùng người, claim giới hạn như trên.

## Câu hỏi còn mở

- Có chấp nhận claim giới hạn "faithfulness/coverage vs timeline" thay "chất lượng theo người" không?
- Salience rule: ai duyệt? (mặc định: chốt bởi đề tài, ghi vào protocol).
- Dataset nào có GT đủ để dựng gold timeline (transcript + track + caption) trên cùng video?
- Có cần đánh giá tóm tắt nhiều mức độ dài không?
