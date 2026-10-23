# Research: paper tóm tắt văn bản bằng AI và metric đánh giá

Date: 2026-10-22. 5 lượt tìm kiếm (giới hạn skill). Kết quả đến từ bản tóm tắt của công cụ tìm kiếm, **chưa đọc toàn văn bài nào**; số liệu phải kiểm lại trước khi trích trong báo cáo.

## Kết luận ngắn

1. **ROUGE/BERTScore làm metric chính trên văn bản dài là rủi ro.** Một bài 2026 (LLM-ReSum) báo ROUGE-L τ=0,55 và BERTScore τ=0,53 trên SummEval (tin tức ngắn), nhưng tương quan "giảm mạnh, thậm chí âm" trên tập tài liệu dài. Transcript TIB dài ~4.700 từ trung vị, nên gần với trường hợp xấu. Cần kiểm lại ở bài gốc.
2. **Metric trung thực dựa trên entailment (SummaC, AlignScore, MiniCheck) là lựa chọn hợp lý và rẻ**; SummaC-CV đạt τ=0,65 trên SummEval về nhất quán sự thật (cùng bài).
3. **Metric dùng LLM (FineSurE, G-Eval) đo được cả độ đủ ý và độ ngắn gọn**, nhưng cần LLM mạnh (API hoặc Llama3-70B), nặng hơn nhiều so với T4 và không có người kiểm chứng trên miền của ta.
4. Không tìm thấy bài nào đánh giá tóm tắt **transcript bài giảng/hội nghị dài** bằng metric không tham chiếu một cách chuẩn mực. Đây là khoảng trống, nên mọi claim phải khiêm tốn.

## Paper và metric tìm được

| Mục | Nguồn | Đo gì | Cần tham chiếu | Chi phí | Nhận xét cho đề tài |
|---|---|---|---|---|---|
| **TIB dataset** (CBMI 2023, Gigant et al.) | [HAL](https://hal.ip-paris.fr/LISN-TLP/hal-04168911v1) | Dataset 9.103 bản ghi video-hội nghị + abstract | — | — | Nguồn gốc dữ liệu của ta. Search **không xác nhận** bài EMNLP 2024 nào về relevance không tham chiếu cho TIB; mục này trong kế hoạch vẫn là UNVERIFIED |
| Bài 2025 dùng TIB | [arXiv 2504.10049](https://arxiv.org/pdf/2504.10049) | Tóm tắt thuyết trình đa phương thức (VLM); giữ 822 bài sau khi lọc abstract bằng LLM judge | Có | — | Ai đó cũng lọc chất lượng abstract TIB. Đối chiếu với cách lọc A/B/C của ta; đáng đọc toàn văn |
| **SummEval** | [arXiv 2007.12626](https://arxiv.org/pdf/2007.12626) | Meta-đánh giá metric theo người chấm (tin tức) | — | — | Chuẩn tham chiếu để biết metric nào tương quan với người; miền ngắn |
| **SummaC / AlignScore / MiniCheck** | đã nêu ở báo cáo trước ([AlignScore](https://arxiv.org/abs/2305.16739v1)) | Nhất quán sự thật bằng entailment | Không | Thấp, chạy T4 | **Khuyến nghị dùng** |
| **QAFactEval / QuestEval** | [QAFactEval](https://arxiv.org/pdf/2112.08542) | Hỏi đáp: nhất quán + độ phủ | Không | Trung bình, nhiễu theo bộ sinh câu hỏi | Tùy chọn |
| **G-Eval** | trích trong [FineSurE](https://arxiv.org/html/2407.00908v3) | LLM chấm Likert theo tiêu chí; Spearman >0,5 với người (tin tức, GPT-4) | Không | Cần LLM mạnh | Thiên lệch judge đã biết ([No Free Labels](https://arxiv.org/html/2503.05061v1)) |
| **FineSurE** (ACL 2024) | [arXiv 2407.00908](https://arxiv.org/html/2407.00908v3), [ACL](https://aclanthology.org/2024.acl-long.51) | Trung thực **cấp câu**, độ đủ ý (keyfact), độ ngắn gọn; Llama3-70B gần bằng mô hình thương mại | Không | Cao (LLM 70B hoặc API) | Metric đầy đủ nhất không cần tham chiếu; không chạy được trên T4 miễn phí |
| **UniSumEval** | [arXiv 2409.19898](https://arxiv.org/html/2409.19898v2) | Benchmark đa chiều: trung thực, bỏ sót thông tin, dài dòng | Có nhãn người | — | Dùng để biết đánh giá nào bám người; không là công cụ chấm |
| Đánh giá đa chiều theo miền/ngôn ngữ (2025) | [arXiv 2506.00549](https://arxiv.org/pdf/2506.00549) | So G-Eval, FineSurE… trên nhiều miền | — | — | Xem độ bám người theo miền |
| **BooookScore** (ICLR 2024) | [ICLR](https://iclr.cc/virtual/2024/poster/19359), [arXiv](https://arxiv.org/html/2310.00785v4) | Mạch lạc của tóm tắt sách dài đã chia đoạn và gộp; 8 loại lỗi; tỷ lệ câu không lỗi | Không | Cần GPT-4 | Cùng cấu trúc map-reduce như pipeline ta (hierarchical merge); đáng đọc nếu muốn đo mạch lạc |
| **FABLES** | [tóm tắt](https://deeplearn.org/arxiv/531597/fables:-evaluating-faithfulness-and-content-selection-in-book-length-summarization) | Đánh giá người về trung thực và chọn nội dung, sách dài 2023–24 | Người | — | Thiết kế đáng học cho dữ liệu tránh nhiễm; không áp dụng trực tiếp |
| **QEVA** (EMNLP 2025 Findings) | [ACL](https://preview.aclanthology.org/new-sigs/2025.findings-emnlp.1340/) | Tóm tắt **video** không tham chiếu bằng hỏi đáp đa phương thức: độ phủ, thật, mạch thời gian | Không | Cao | **Liên quan trực tiếp đến phạm vi video tổng quát**; cân nhắc cho phần đánh giá tóm tắt video về sau |
| Ảnh hưởng chất lượng tham chiếu | [arXiv 2410.10867](https://arxiv.org/pdf/2410.10867) | Giảm tác động tham chiếu kém khi dùng metric không tham chiếu | Một phần | — | Khớp với vấn đề abstract TIB chất lượng không đều |
| Khảo sát hệ thống | [arXiv 2406.11289](https://arxiv.org/pdf/2406.11289) | Khảo sát tóm tắt từ thống kê đến LLM | — | — | Nền tảng chung; ghi ROUGE bỏ qua từ đồng nghĩa và phạt cách diễn đạt mới |

Không tìm được kết quả cho FActScore, BARTScore, UniEval trong lần này (không loại trừ chúng tồn tại hay phù hợp).

## Áp dụng cho hướng đơn giản đã chọn

- **Giữ:** ROUGE-L (chính, đã đóng băng), BERTScore, một metric trung thực entailment (AlignScore/MiniCheck/SummaC).
- **Đề xuất thêm một mục vào báo cáo:** ghi rõ rằng ROUGE trên văn bản dài có thể kém tin cậy, và báo cáo kèm metric trung thực để cân bằng. Đây là ý kiến, kiểm lại bài LLM-ReSum trước khi viết.
- **Tùy chọn, ngoài phạm vi hiện tại:** FineSurE hoặc G-Eval với một LLM mở nhỏ để đo độ đủ ý và ngắn gọn; chỉ làm khi có ngân sách và chấp nhận không có người kiểm chứng. BooookScore cho mạch lạc của map-reduce.
- **Cho video về sau:** QEVA là ứng viên đáng xem khi đến lúc đánh giá tóm tắt video, vì nó không cần tham chiếu và dùng hỏi đáp đa phương thức.
- **Không làm:** tự chế metric mới. Đã tốn công và trượt cổng hiệu lực.

## Bước tiếp theo

1. Đọc toàn văn LLM-ReSum (arXiv 2604.25665) và 2504.10049 để xác nhận hai điểm: độ tin cậy của ROUGE trên tài liệu dài và cách lọc abstract TIB bằng LLM.
2. Chạy notebook T4 để chọn họ trung thực.
3. Quyết định có thêm một judge LLM nhỏ làm phân tích thăm dò hay không.

## Câu hỏi còn mở

- Có bài nào kiểm chứng metric không tham chiếu trên transcript bài giảng/hội nghị dài? Chưa tìm thấy.
- Số liệu tương quan trong LLM-ReSum có áp dụng cho văn bản nói (ASR) không?
- Bài 2504.10049 lọc abstract bằng tiêu chí nào, và có nên áp dụng cho cohort TIB của ta?
