# Research: IbR của nhóm TIB và độ tin cậy metric trên văn bản dài

Date: 2026-10-22. Đọc **toàn văn** (trích bằng pypdf) ba bài: [Gigant et al., EMNLP 2024](https://arxiv.org/pdf/2410.10867), [LLM-ReSum](https://arxiv.org/pdf/2604.25665), [Gigant et al. 2025, VLM trên TIB](https://arxiv.org/pdf/2504.10049). Sửa và làm rõ báo cáo trước ([research-261022-1509](research-261022-1509-text-summarization-papers-metrics-report.md)).

## Kết luận ngắn

1. **Mục "UNVERIFIED" trong kế hoạch đã được xác định:** metric không tham chiếu EMNLP 2024 của nhóm TIB là **Importance-based Relevance (IbR)**, trong "Mitigating the Impact of Reference Quality on Evaluation of Summarization Systems with Reference-Free Metrics" (Gigant, Guinaudeau, Decombas, Dufaux; EMNLP 2024 main, trang 19355–19368). Bài này đã xuất hiện trong kết quả tìm kiếm đầu tiên, và tôi đã bỏ sót.
2. **Metric tự chế của tôi thực chất là bản chưa kiểm chứng của IbR** (độ phủ có trọng số tf-idf của n-gram nguồn). IbR có kiểm chứng với người; bản của tôi trượt 3/7. Đây là một lý do nữa để chọn hướng đơn giản.
3. **Sửa lại cảnh báo của báo cáo trước:** tôi viết "ROUGE trên văn bản dài có thể không đáng tin" dựa trên LLM-ReSum. Đọc toàn văn cho thấy cảnh báo đó **sai mức** đối với cách ta dùng (xem mục 2). ROUGE vẫn là lựa chọn chính hợp lý.

## 1. IbR

- **Công thức:** với n-gram *t* của nguồn *d* trong kho *D*, trọng số `W = tanh(w_tfidf / rank)`. Điểm = `α(|s|,|d|) · Σ_{t∈s} W / Σ_{t∈d} W`, `α = 1 / (1 + exp(20·|s|/|d| − 10))`.
- **Cấu hình các tác giả chọn:** tokenizer huấn luyện trên kho, trigram, tf-idf, trọng số tanh, có phạt độ dài.
- **Với ta:** `|s|/|d|` ≈ 120/4.700 ≈ 0,03, nên phạt độ dài ≈ 1 (chỉ phạt khi tóm tắt dài cỡ một nửa nguồn). Không phạt gì trong thực tế.
- **Chi phí:** rất rẻ, chạy CPU. Mã có công bố nhưng **tôi chưa tìm được URL** (chú thích trong bài); cần lấy từ trang ACL Anthology. Dễ cài lại từ công thức.
- **Hiệu lực (tương quan cấp hệ thống, Spearman, tương quan với độ liên quan do người chấm):**

| Metric | SummEval (23 hệ thống) | ArXiv (12) | GovReport (12) |
|---|---:|---:|---:|
| ROUGE-1 | 0,59 | **0,88** | **0,92** |
| ROUGE-2 | 0,61 | 0,52 | 0,91 |
| ROUGE-L | 0,47 | 0,72 | 0,90 |
| chrF | 0,75 | 0,83 | 0,87 |
| BERTScore | 0,40 | 0,32 | 0,91 |
| IbR (bài này) | 0,67 | 0,78 | 0,71 |
| ROUGE-1 + IbR | 0,80 | 0,90 | 0,85 |
| LLM judge (Gemini 1.5 Flash) | 0,88 | 0,76 | 0,63 |
| ESTIME / GRUEN | âm hoặc rất thấp | | |

- **Bền với tham chiếu nhiễu:** ROUGE-1 giảm khi thay dần tham chiếu bằng câu ngẫu nhiên; IbR không bị ảnh hưởng theo thiết kế, và trộn với ROUGE-1 làm ROUGE bền hơn. **Rất liên quan:** abstract TIB do tác giả viết nên chất lượng không đều (lý do cả bài 2025 lọc abstract bằng LLM judge).

### Giới hạn của IbR (từ chính bài)

- Chỉ kiểm với **độ liên quan** do người chấm, không phải trung thực.
- Tương quan **cấp tóm tắt đơn lẻ yếu** (Spearman với độ liên quan: 0,23 / 0,45 / 0,18 trên SummEval/ArXiv/GovReport); chỉ tốt khi xếp hạng **hệ thống**.
- Tương quan với **độ dài tóm tắt** ngang hoặc hơn tương quan với độ liên quan trên vài tập (Pearson độ dài 0,32 / 0,40 / 0,02 / 0,30). Vì vậy chỉ so sánh các hệ thống **ở cùng một view/ngân sách**; điểm IbR của view S/M/L khác nhau không so trực tiếp được.
- Nhạy với độ trích xuất và tỷ lệ nén của tác vụ; có thể bị đánh lừa bằng tóm tắt trích xuất theo chính trọng số đó.
- Số hệ thống để xác nhận nhỏ (12–23). Ta chỉ có 5 hệ thống, nên không tự kiểm chứng tương quan hệ thống được.

## 2. Hiểu lại LLM-ReSum: cấp tóm tắt khác cấp hệ thống

LLM-ReSum báo ROUGE/BERTScore/BLEU **âm** trên ArXiv/GovReport (BERTScore τ = −0,46 trên GovReport; BLEU τ = −0,61 trên ArXiv accuracy). Nhưng:

- Đó là Kendall τ ở **cấp tóm tắt**, trên **17 tài liệu** × 12 mô hình, nguồn ~27.000 từ, nhãn người là nhị phân cấp câu. Tập rất nhỏ và nguồn dài gấp ~6 lần TIB (trung vị 4.700 từ).
- Bài EMNLP 2024 dùng cùng ArXiv/GovReport (Koh et al. 2022) và báo **cấp hệ thống** ROUGE-1 = 0,88 / 0,92. Hai kết quả mâu thuẫn nhau chỉ nếu bỏ qua mức tương quan.
- Ta so **5 hệ thống trên hàng trăm tài liệu**, tức là dùng ở **cấp hệ thống**. Khuyến nghị: ROUGE giữ nguyên làm chính; không cần cảnh báo "ROUGE kém trên văn bản dài" như báo cáo trước.
- Điều đáng nhớ từ LLM-ReSum còn đứng vững: **LLM judge không ổn trên nguồn rất dài** (LLM-Accuracy τ = −0,35 trên ArXiv, 0,22 trên GovReport), và **SummaC-CV** là tốt nhất về nhất quán sự thật trên ArXiv (τ = 0,70), SummEval (0,65). Điều này ủng hộ chọn họ entailment (đang thử bằng notebook T4), và ủng hộ không dùng LLM judge làm chính.

## 3. Bài 2025 về TIB (VLM)

- Dựng benchmark 822 bài từ 9.103: giữ **chỉ abstract được SmolLM2 chấm 9/9** (thang 1–9, dựa trên tiêu đề + abstract) và bỏ bài có <3 slide hợp lệ.
- Tác giả cho rằng BARTScore/ESTIME không tin cậy khi nguồn dài hơn 10 lần giới hạn ~1.000 token, nên dùng ROUGE-1/2, GRUEN và IbR (tính riêng cho transcript, OCR slide, và gộp).
- Kết luận về đầu vào: biểu diễn xen kẽ slide + transcript cho kết quả tốt nhất; đầu vào là khung hình then chốt tốt hơn video thô.
- **Ý nghĩa cho ta:** có tiền lệ dùng ROUGE-1/2 + IbR trên TIB; cách lọc abstract bằng LLM judge là một lựa chọn ngoài phân loại A/B/C của ta (chưa cần). Không dùng BARTScore.

## 4. Đề xuất cập nhật (chờ bạn duyệt, chưa sửa tài liệu)

| Thay đổi | Lý do | Chi phí |
|---|---|---|
| Thêm **chrF** làm phân tích phụ | Cấp hệ thống 0,75/0,83/0,87, rẻ, không phụ thuộc mô hình | Rất thấp |
| Thêm **IbR** làm phân tích phụ, tính ở từng view | Không tham chiếu, bền với abstract nhiễu, do chính nhóm TIB kiểm chứng; bổ sung cho ROUGE | Thấp, cần cài lại từ công thức hoặc lấy mã tác giả |
| Giữ ROUGE-L (chính), BERTScore, họ trung thực entailment | Đã đóng băng / đã chọn | — |
| **Không** dùng BARTScore, ESTIME, GRUEN | Giới hạn token; ESTIME/GRUEN không ổn định | — |
| So sánh chỉ ở cùng view | IbR và ROUGE đều phụ thuộc độ dài | — |

IbR chỉ thay thế vai trò của metric tự chế một cách có kiểm chứng; không thêm độ phức tạp đáng kể.

**Cập nhật theo quy tắc của người dùng ("metric tự chế thì không dùng"):** cài lại IbR từ công thức cũng là một dạng tự chế nếu sai chi tiết, nên **chỉ dùng IbR qua mã chính thức của tác giả**. URL chưa xác minh (cần chú thích 1 trong bài hoặc trang ACL Anthology) nên IbR chưa được đưa vào hợp đồng. chrF (sacrebleu) và các metric entailment đã công bố thì dùng được.

## Câu hỏi còn mở

- URL mã IbR chính thức là gì? (Chưa xác minh; cần chú thích 1 trong bài.)
- Với 5 hệ thống, IbR có xếp hạng giống người trên TIB không? Không thể biết nếu không có người; chỉ báo cáo như phân tích phụ.
- Có nên thêm chrF và IbR vào hợp đồng phân tích phụ không? (Chờ bạn quyết định.)
- LLM-ReSum chưa được bình duyệt đầy đủ theo thông tin tôi có; số liệu cấp tóm tắt trên n=17 tài liệu chỉ nên dùng như cảnh báo thận trọng.
