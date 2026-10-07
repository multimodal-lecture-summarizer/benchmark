---
phase: 2
title: "Comprehensive Benchmark Execution (Unimodal RQ0 + Multimodal RQ1-4 + Error Cascading)"
status: completed
priority: P1
dependencies: [1]
---

# Phase 2: Comprehensive Benchmark Execution (Unimodal RQ0 + Multimodal RQ1-4 + Error Cascading)

## 1. Overview

Thực thi lại toàn bộ các thực nghiệm khoa học theo phương pháp luận chuẩn tắc **Bottom-Up Empirical Evaluation** (từ thành phần cơ sở đến hệ thống hoàn chỉnh) phục vụ cho Luận văn Thạc sĩ và Bài báo khoa học. 

Phase 2 được cấu trúc thành 3 phân kỳ nối tiếp:
1. **Phase 2A (Unimodal Component Benchmarks - RQ0):** Đánh giá độc lập chất lượng và hiệu năng của các mô hình trích xuất ngược dòng: Khối âm thanh ASR/khử nhiễu (**RQ0-A**) và Khối thị giác phát hiện chuyển cảnh/đọc chữ slide (**RQ0-V**).
2. **Phase 2B (Multimodal System Benchmarks - RQ1 to RQ4):** Thực thi các mô hình phân chương ($C_1 \dots C_6$), tóm tắt phân cấp ($S_0 \dots S_4$), truy vấn hỏi đáp EduVidQA ($Q_0 \dots Q_3$), và biên hiệu quả Pareto ($E_1 \dots E_4$) trên 20 bài giảng thật với 3 hạt giống ($42, 1337, 2026$).
3. **Phase 2C (Cross-Stage Error Cascading & Sensitivity):** Đánh giá độ nhạy và tính bền bỉ của cơ chế dung hợp đa phương thức (Multimodal Fusion) khi đầu vào âm thanh bị tăng WER hoặc đầu vào thị giác bị mất mát keyframe.

---

## 2. Requirements & Primary Targets

### 2.1. Phase 2A: Unimodal Component Benchmarks (RQ0)

#### RQ0-A: Audio Processing & ASR Robustness:
- **Mô hình đối sánh:**
  - $A_0$: Whisper Base (74M params)
  - $A_1$: Whisper Small PyTorch nguyên bản (244M params)
  - $A_2$: Faster-Whisper Small CPU int8
  - $A_3$: Faster-Whisper Small GPU float16 (cấu hình sản xuất `ai_workers`)
  - $A_4$: WhisperX Small + Phoneme Alignment (Wav2Vec2)
  - $A_5$: $A_3$ kết hợp tiền xử lý lọc nhiễu DeepFilterNet3
- **Chỉ số mục tiêu:**
  - $\text{WER} \le 12.0\%$ trên bài giảng tiếng Anh chuẩn (TED-LIUM v3) và $\le 18.0\%$ trên bài giảng hội trường TIB.
  - $\text{RTF} < 0.15$ trên GPU (nhanh gấp $> 6.5$ lần thời gian thực).
  - Độ lệch mốc thời gian $\Delta t_{\text{alignment}} \le 250\text{ms}$ với WhisperX.
  - DeepFilterNet3 cải thiện SNR $\ge 3.5\text{dB}$ trong môi trường ồn.

#### RQ0-V: Visual Scene Detection & Slide OCR:
- **Mô hình đối sánh Phân cảnh:** Fixed-Interval 30s, PySceneDetect ContentDetector ($\tau=27.0$), PySceneDetect AdaptiveDetector, DINOv2 Cosine Delta ($\tau_v=0.15$), TransNetV2.
- **Mô hình đối sánh OCR:** Tesseract v5, EasyOCR, PaddleOCR `ch_PP-OCRv4`.
- **Chỉ số mục tiêu:**
  - Phát hiện chuyển slide: $\text{Collar F1}@2\text{s} \ge 0.8500$, Omission Rate (bỏ sót slide) $\le 5.0\%$.
  - OCR trên slide bài giảng: PaddleOCR đạt $\text{CER} \le 6.0\%$, Word Recall trên thuật ngữ kỹ thuật $\ge 88.0\%$, tốc độ $\ge 15\text{ FPS}$.

---

### 2.2. Phase 2B: Multimodal System Benchmarks (RQ1 - RQ4)

#### RQ1 Targets (Multimodal Chaptering):
- **WindowDiff của $C_5$ bắt buộc phải $\le 0.0950$:** Sau khi tích hợp Visual-Anchor Snapping và Adaptive Peak Thresholding, $C_5$ phải vượt qua baseline thị giác đơn thuần $C_3$ ($0.1094$) và triệt tiêu hoàn toàn nghịch lý $C_5$ có WindowDiff $0.3217$ trong bản nháp cũ.
- **F1 $\pm 5\text{s}$ của $C_5$ duy trì $\ge 0.0800$:** Vượt trội hơn $C_1$ (Transcript: $0.0250$), $C_3$ (Visual: $0.0712$), và $C_6$ (Late Fusion: $0.0310$).

#### RQ2 Targets (Hierarchical Summarization & Evidence Grounding):
- **Tỷ lệ ảo giác (Hallucination Rate):**
  - Mô hình thứ bậc văn bản đơn thuần $S_3$: Báo cáo trung thực tỷ lệ ảo giác là $27.87\%$ (do thiếu neo thị giác).
  - Mô hình có neo chứng cứ slide $S_3\text{+ev}$ / $S_4$: Tỷ lệ ảo giác giảm sâu xuống **$\le 2.50\%$**.
- **Chỉ số mật độ thông tin:** Báo cáo đồng thời: Độ dài bản tóm tắt (tokens), Số lượng mệnh đề (Claim Count), và Mật độ mệnh đề (Claim Density per 100 tokens).

#### RQ3 Targets (Multimodal RAG & Video QA):
- **Độ chính xác truy xuất RRF:** Đạt kết quả vượt trội so với truy xuất dense thuần túy.
- **Tỷ lệ thu hẹp khoảng cách Oracle (Gap Closed):** Báo cáo chuẩn xác **$78.8\%$** khoảng cách được thu hẹp ($90.0\%$ điểm số tuyệt đối của Oracle), tuyệt đối không tuyên bố nhầm lẫn là "thu hẹp 90% khoảng cách".

#### RQ4 Targets (Controlled Efficiency & Pareto Frontier):
- Thiết lập biên tối ưu Pareto Quality-Latency-VRAM trên 4 cấu hình: $E_1$ (Transcript-only), $E_2$ (Structured), $E_3$ (Multimodal Proposed), $E_4$ (Compact End-to-End VLM Qwen-VL).

---

### 2.3. Phase 2C: Cross-Stage Error Cascading Analysis

- **Mục tiêu:** Chứng minh định lượng tính kháng nhiễu (Robustness & Resilience) của mạng dung hợp đa phương thức:
  - Khi tăng WER từ $5\% \to 10\% \to 20\% \to 35\%$, độ dốc sụt giảm F1 của $C_5$ thấp hơn đáng kể so với $C_1$ ($\Delta \text{F1}_{C5} < 0.5 \cdot \Delta \text{F1}_{C1}$).
  - Khi cắt giảm $10\%, 25\%, 50\%$ slide keyframes, $Q_3$ RRF vẫn duy trì $\text{Recall}@3 \ge 70.0\%$ nhờ kênh transcript bù đắp.

---

## 3. Related Code Files & Execution Scripts

### 3.1. Standardized Jupyter Notebook Suite (`experiments/notebooks/`)

Toàn bộ 20 tệp notebook cũ, rời rạc và trùng lặp trong `experiments/notebooks/` sẽ được di chuyển vào kho lưu trữ `experiments/legacy_notebooks_backup/`. Thư mục `experiments/notebooks/` được tái thiết lập hoàn toàn từ đầu thành bộ **7 Notebooks chuẩn mực khoa học**, ánh xạ 1-1 với tiến trình nghiên cứu từ dưới lên (bắt đầu từ Phân tích Thăm dò & Thẩm định Dữ liệu):

| STT | Tệp Notebook Mới | Nhiệm vụ Khoa học | Đầu ra / Báo cáo |
|:---:|:-----------------|:------------------|:-----------------|
| **00** | `00_dataset_eda_and_quality_audit.ipynb` | **Phân tích Thăm dò Dữ liệu (EDA) & Thẩm định Chất lượng (Quality Audit)**: Thống kê quy mô, phân bố thời lượng, tốc độ nói (WPM) trên TED-LIUM 3; phân loại câu hỏi & độ dài chứng cứ EduVidQA; thẩm định 20 bài giảng thật (D-T14 100% keep rate, 2.0/2.0 source support, D-T08 equal budget). | `reports/dataset_eda_and_audit_report.json` |
| **01** | `01_audio_asr_benchmark.ipynb` | Benchmark toàn diện khối Âm thanh (RQ0-A): Whisper Base, Small, Faster-Whisper CPU/GPU, WhisperX, DeepFilterNet3; đo WER, CER, RTF, sai số mốc thời gian $\Delta t$. | `reports/rq0a_audio_results.json` |
| **02** | `02_visual_scene_ocr_benchmark.ipynb` | Benchmark toàn diện khối Thị giác & OCR (RQ0-V): PySceneDetect Content/Adaptive, DINOv2 Delta, TransNetV2; PaddleOCR vs Tesseract vs EasyOCR; đo Precision, Recall, Collar F1, Omission Rate, OCR Recall, FPS. | `reports/rq0v_visual_results.json` |
| **03** | `03_multimodal_chaptering_benchmark.ipynb` | Benchmark Phân đoạn chương mục (RQ1): $C_1 \dots C_6$ (với $C_5$ Decoupled Cross-Attention + Visual Snapping); đo WindowDiff ($\le 0.0950$), $P_k$, F1 $\pm 5\text{s}$. | `reports/rq1_benchmark_results.json`, `checkpoints/c5_real.pt` |
| **04** | `04_hierarchical_summarization_benchmark.ipynb` | Benchmark Tóm tắt phân cấp & Neo chứng cứ (RQ2): $S_0 \dots S_4$; đo ROUGE-1/2/L, BERTScore, Tỷ lệ ảo giác ($\le 2.5\%$), Claim Density. | `reports/rq2_benchmark_results.json` |
| **05** | `05_evidence_retrieval_qa_benchmark.ipynb` | Benchmark Truy vấn & Hỏi đáp RAG (RQ3): $Q_0 \dots Q_3$ với thuật toán RRF; đo Recall@1/3/5, MRR, Token F1, Exact Match, Oracle Gap Closed ($78.8\%$). | `reports/rq3_benchmark_results.json` |
| **06** | `06_efficiency_pareto_error_cascading.ipynb` | Benchmark Biên hiệu quả Pareto (RQ4) & Khảo sát độ nhạy lan truyền lỗi (Error Cascading Phase 2C): Stress-test nhiễu ASR và mất mát Keyframe. | `reports/rq4_efficiency_summary.json`, `reports/error_cascading_results.json` |

---

### 3.2. Related Code Files & Execution Scripts

### Phân kỳ 2A (Unimodal):
- **Create & Execute:** [`benchmarks/scripts/run_rq0a_audio_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq0a_audio_benchmark.py)
- **Create & Execute:** [`benchmarks/scripts/run_rq0v_visual_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq0v_visual_benchmark.py)
- **Outputs:**
  - `reports/rq0a_audio_results.json`
  - `reports/rq0v_visual_results.json`

### Phân kỳ 2B (Multimodal System):
- **Modify & Execute:** [`benchmarks/scripts/run_rq1_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq1_benchmark.py) (lưu `checkpoints/c5_real.pt`)
- **Modify & Execute:** [`benchmarks/scripts/run_rq2_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq2_benchmark.py) (tích hợp `S3_PlusEvidenceSummarizer` và đo ảo giác)
- **Modify & Execute:** [`benchmarks/scripts/run_rq3_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq3_benchmark.py) (sử dụng RRF và nạp `c5_real.pt`)
- **Execute:** [`benchmarks/scripts/run_rq4_efficiency_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_rq4_efficiency_benchmark.py)
- **Outputs:**
  - `reports/rq1_benchmark_results.json`
  - `reports/rq2_benchmark_results.json`
  - `reports/rq3_benchmark_results.json`
  - `reports/rq4_efficiency_summary.json`

### Phân kỳ 2C (Error Cascading):
- **Create & Execute:** [`benchmarks/scripts/run_error_cascading_benchmark.py`](file:///c:/Users/hung/Documents/GitHub/multimodal-lecture-summarizer/multimodal-lecture-summarizer/benchmarks/scripts/run_error_cascading_benchmark.py)
- **Outputs:**
  - `reports/error_cascading_results.json`

---

## 4. Step-by-Step Implementation Steps

### Bước 1: Thực thi Phase 2A — Unimodal Benchmarks
1. **Chạy Benchmark Audio ASR & Khử nhiễu (RQ0-A):**
   ```bash
   python -m benchmarks.scripts.run_rq0a_audio_benchmark --seeds 42 1337 2026
   ```
   - Đánh giá $A_0 \dots A_5$ trên tập bài giảng thật.
   - Đo lường WER, CER, RTF, và $\Delta t$ alignment error.
   - Xuất kết quả chuẩn hóa vào `reports/rq0a_audio_results.json`.

2. **Chạy Benchmark Visual Scene & OCR (RQ0-V):**
   ```bash
   python -m benchmarks.scripts.run_rq0v_visual_benchmark --seeds 42 1337 2026
   ```
   - Đo Precision, Recall, Collar F1@1s/2s/3s trên các thuật toán phát hiện ranh giới slide.
   - Đo CER, WER, Word Recall và FPS của PaddleOCR so với Tesseract/EasyOCR.
   - Xuất kết quả chuẩn hóa vào `reports/rq0v_visual_results.json`.

### Bước 2: Thực thi Phase 2B — Multimodal System Benchmarks
3. **Khởi chạy RQ1 Chaptering Benchmark (3 seeds với cách ly trạng thái):**
   ```bash
   python -m benchmarks.scripts.run_rq1_benchmark --seeds 42 1337 2026
   ```
   - Đảm bảo `seed_everything(seed)` và dọn dẹp CUDA cache giữa các lần chạy.
   - Kích hoạt Zero-Boundary Fallback Guard tránh chia cho 0.
   - Lưu trọng số tốt nhất vào `checkpoints/c5_real.pt`.
   - Ghi nhận WindowDiff, $P_k$, F1 $\pm 3\text{s}$, F1 $\pm 5\text{s}$ cho $C_1 \dots C_6$.

4. **Khởi chạy RQ2 Summarization Benchmark (3 seeds):**
   ```bash
   python -m benchmarks.scripts.run_rq2_benchmark --seeds 42 1337 2026
   ```
   - Đo lường đồng thời 6 biến thể: $S_0, S_1, S_2, S_3, S_3\text{+ev}, S_4$.
   - Tính toán Tỷ lệ ảo giác (Hallucination Rate), Claim Count, Claim Density per 100 tokens, ROUGE-1/2/L và BERTScore.

5. **Khởi chạy RQ3 Retrieval QA Benchmark (3 seeds):**
   ```bash
   python -m benchmarks.scripts.run_rq3_benchmark --seeds 42 1337 2026
   ```
   - Nạp checkpoint `checkpoints/c5_real.pt`.
   - Đánh giá $Q_0, Q_1, Q_2, Q_3$ với thuật toán xếp hạng RRF ($k=60$).
   - Ghi nhận Hit@1, Hit@3, MRR, nDCG@3, Token F1, và tỷ lệ thu hẹp khoảng cách Oracle ($78.8\%$).

6. **Khởi chạy RQ4 Efficiency & Pareto Benchmark:**
   ```bash
   python -m benchmarks.scripts.run_rq4_efficiency_benchmark
   ```
   - Tính toán Pareto frontier và xuất biểu đồ vector chất lượng cao.

### Bước 3: Thực thi Phase 2C — Error Cascading Analysis
7. **Khởi chạy Phân tích Lan truyền Lỗi:**
   ```bash
   python -m benchmarks.scripts.run_error_cascading_benchmark --seeds 42 1337 2026
   ```
   - Khảo sát độ nhạy đa cấp: Nhiễu ASR ($5\% \to 35\%$) và Suy hao Slide ($10\% \to 50\%$).
   - Xuất bảng số liệu đối chiếu tính bền bỉ của mô hình đa phương thức vào `reports/error_cascading_results.json`.

---

## 5. Success Criteria

- [ ] **RQ0-A:** Faster-Whisper Small GPU float16 đạt $\text{WER} \le 12.0\%$ (TED-LIUM v3) và $\text{RTF} \le 0.15$; DeepFilterNet3 cải thiện SNR $\ge 3.5\text{dB}$.
- [ ] **RQ0-V:** PySceneDetect/DINOv2 đạt $\text{Collar F1}@2\text{s} \ge 0.8500$, Omission Rate $\le 5.0\%$; PaddleOCR đạt $\text{CER} \le 6.0\%$ với tốc độ $\ge 15\text{ FPS}$.
- [ ] **RQ1:** $C_5$ đạt WindowDiff $\le 0.0950$, đánh bại $C_3$ ($0.1094$) có ý nghĩa thống kê ($p_{\text{adj}} < 0.01$); F1 $\pm 5\text{s} \ge 0.0800$.
- [ ] **RQ2:** $S_3\text{+ev}$ duy trì tỷ lệ ảo giác $< 3.0\%$ (so với $S_3$ là $27.87\%$), với Claim Density $\ge 3.5$ claims / 100 tokens.
- [ ] **RQ3:** $Q_3$ RRF đạt tỷ lệ thu hẹp khoảng cách Oracle chính xác $78.8\%$ ($90.0\%$ điểm số tuyệt đối).
- [ ] **RQ4:** Xác lập biểu đồ Pareto rõ ràng chứng minh $E_3$ vượt trội hơn $E_1$ và $E_4$ về tỷ lệ chất lượng trên chi phí tính toán.
- [ ] **Phase 2C:** Hoàn thành bảng phân tích độ nhạy lan truyền lỗi chứng minh mô hình đa phương thức vượt trội khi có nhiễu đầu vào.
- [ ] Toàn bộ số liệu được lưu trữ nguyên vẹn dưới định dạng JSON trong `reports/` kèm 95% CIs, Cohen's d, và $p_{\text{adj}}$ qua Holm-Bonferroni.
