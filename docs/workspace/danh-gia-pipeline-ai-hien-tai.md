# Danh giá pipeline AI hiện tại theo scope dự án

## Phạm vi

Tài liệu này đánh giá hiện trạng của pipeline AI (trong `multimodal-lecture-summarizer/ai_workers`) so với mục tiêu và phạm vi (scope) cụ thể của dự án:
- **Loại video**: Video bài giảng ngắn (3-15 phút).
- **Ngôn ngữ**: Tiếng Anh (English only).
- **Người nói**: Một người nói chính (single speaker).
- **Trọng tâm**: Trích xuất tóm tắt (summary), phân chương (chapters), khung hình chính (keyframes) và hỏi đáp (Q&A/RAG).

Đánh giá này không bao gồm các phần như UI, xác thực (auth), hay admin. Mục đích là để làm rõ thành phần nào đã phù hợp, thành phần nào có thể đang dư thừa hoặc thiếu sót, qua đó định hướng tối ưu MVP.

## Tóm tắt kết luận tạm thời

- **Core ASR (Audio)**: Phù hợp với hướng scope hiện tại (sử dụng WhisperX / Faster-Whisper base.en cho tiếng Anh).
- **Speaker Diarization**: Có khả năng là dư thừa (overhead) vì phạm vi chỉ có 1 người nói.
- **Visual / RAG**: Nên được xem là các tính năng tuỳ chọn (optional) tuỳ thuộc vào việc video có slide hay bật tính năng Q&A hay không.
- **Tổng quan**: ASR `01c` đã so sánh đủ sáu kiến trúc trên TED-LIUM; native test là diagnostic và chưa chứng minh lựa chọn triển khai cho video demo.

## Bảng đánh giá thành phần

| Thành phần | Đã phù hợp scope? | Bằng chứng hiện có | Cần bổ sung |
| --- | --- | --- | --- |
| **Audio ASR** | Có khả năng phù hợp | Ứng dụng mặc định Faster-Whisper `base.en`. Benchmark `01c` đã hoàn tất sáu candidate trên 507 validation và 1.155 native-test unit; Qwen3-ASR 0.6B đứng đầu validation WER 3,91%. | Native test chỉ diagnostic; cần đánh giá riêng trên dữ liệu phù hợp ứng dụng nếu muốn đổi model triển khai. |
| **Speaker handling** | Chưa phù hợp (Dư thừa) | Module SpeakerDiarizer đang được chạy mặc định cho mọi video, dù scope chỉ là 1 người nói. Dễ gay lỗi nếu có nhạc nền/overlap. | Đo lường Latency saving nếu bỏ/tắt module này. Chạy DER proxy (nếu cần chứng minh bỏ là đúng). |
| **Scene/keyframe** | Có khả năng phù hợp | Đang dùng PySceneDetect trích xuất slide keyframes. Có tính năng lọc K-Means. | Cần benchmark Keyframe recall, tỷ lệ sót slide quan trọng do K-Means. |
| **Semantic/caption** | TBD (Cần cẩn trọng) | Có tích hợp Florence/BLIP-2. Chạy tốn tài nguyên và có rủi ro hallucination (caption sinh nội dung không có trên slide). | Số liệu đánh giá thực tế về mức độ hallucination trên corpus. |
| **Timeline** | Có rủi ro | Đang có fallback overlap thời gian đơn giản nếu semantic alignment thất bại. | Đo lường Chapter/timestamp MAE. Đánh giá tính chính xác của fallback. |
| **Summary** | Cơ bản đáp ứng | Đang gọi LLM (Groq) với prompt. Có fallback mock khi lỗi API. Chưa có verify grounding. | Cần chấm điểm Summary factuality / human score. Tính điểm ROUGE-L/BERTScore so với reference. |
| **RAG/Q&A** | Tuỳ chọn | Đang lưu chỉ mục vào ChromaDB. Lỗi ChromaDB không làm sập pipeline (có mock store). | Đo lường RAG Hit@3/Hit@5 và citation correctness (nếu Q&A được bật). |
| **Latency/tài nguyên** | Yếu (Chưa tối ưu) | Pipeline hiện đang chạy tuần tự (ASR -> Speaker -> Visual -> Semantic -> Timeline -> Summary). Chậm và không scale tốt. | Cần benchmark Latency per stage và Latency/video-minute thực tế. |

## Số liệu đã có

- Các kết quả đo lường và đánh giá cũ có thể tham khảo trong `../archive/visuals/synthesis_analysis_report.html` (chạy trên các cấu hình/model trước đây).
- Các rủi ro về mặt kiến trúc và xử lý mã nguồn đã được liệt kê chi tiết trong `diem-yeu-pipeline-xu-ly-ai.md` (03/08/2026).
- [Báo cáo ASR `01c`](../results/asr-architecture-evaluation-2026-10-05.md) là nguồn WER/CER cho TED-LIUM. Kết quả này không phải benchmark end-to-end của ứng dụng trên corpus video demo.

## Số liệu cần chạy thêm (Từ Phase 1-4)

Để có kết luận chính xác, các metric sau bắt buộc phải được thu thập:
1. **WER/CER**: Đã có kết quả `01c` trên TED-LIUM; chỉ cần cohort video demo độc lập nếu đánh giá quyết định đổi model ứng dụng.
2. **Latency per stage**: Đo thời gian chạy của từng module và tổng thời gian (RTF).
3. **Keyframe recall**: Tỷ lệ bắt đúng các thay đổi slide quan trọng.
4. **Summary factuality & Human score**: Độ chính xác thông tin và mức độ hữu ích của bản tóm tắt.
5. **RAG Citation Accuracy**: Nếu tính năng Q&A được coi là deliverable.

## Kết luận

Dựa trên mã nguồn hiện hành và thiết kế pipeline:
- Nền tảng cốt lõi (ASR và Summary bằng LLM) cơ bản đi đúng hướng cho phạm vi dự án.
- Nhược điểm lớn nhất là việc thực thi tuần tự (làm tăng latency) và giữ lại các module không cần thiết cho single-speaker (như Diarization) làm lãng phí tài nguyên và tăng rủi ro sai sót.
- Để hoàn thiện MVP, cần có cơ chế bật/tắt các module (Speaker, Visual, RAG) một cách linh hoạt, đồng thời thiết lập Quality Gates rõ ràng giữa các stage.
- Quyết định cuối cùng sẽ được đưa ra sau khi hoàn thành các Phase benchmark (1-4).

## Câu hỏi chưa rõ

- Báo cáo và file đánh giá có bắt buộc viết bằng tiếng Việt có dấu không, hay nên giữ ASCII để tránh lỗi encoding trên một số môi trường? (Tạm thời file này sử dụng tiếng Việt có dấu).
- Khi chạy benchmark trên corpus mới, có chấp nhận sử dụng kết quả từ fallback/mock (khi gọi LLM lỗi) không hay phải fail rõ ràng để phản ánh đúng độ ổn định?
