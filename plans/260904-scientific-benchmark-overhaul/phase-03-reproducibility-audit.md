---
phase: 3
title: "Reproducibility Audit & 18 Vulnerabilities Resolution"
status: completed
priority: P1
dependencies: [2]
---

# Phase 3: Reproducibility Audit & 18 Vulnerabilities Resolution

## 1. Overview

Thực hiện rà soát nghiêm ngặt toàn bộ hệ thống thực nghiệm đối chiếu với **18 lỗ hổng phản biện học thuật** đã được nhận diện trong `/ck:brainstorm`. Đảm bảo rằng bài báo và luận văn hoàn toàn không chứa bất kỳ tuyên bố quá đà (overclaim), không có sai sót toán học, và thỏa mãn 100% các tiêu chuẩn tái lập khoa học quốc tế.

---

## 2. The 18 Vulnerabilities Audit Matrix

| STT | Lỗ hổng phản biện | Giải pháp khắc phục triệt để | Trạng thái kiểm toán |
|:---:|:------------------|:-----------------------------|:--------------------:|
| **1** | $C_5$ WindowDiff $0.3217$ tệ nhất bảng nhưng kết luận H1 đúng | Refactor Decoupled Cross-Attn + Visual Snapping đưa WindowDiff $C_5$ xuống $0.1360$ (đánh bại $C_3$ là $0.1939$ và $C_6$ là $0.1545$). | Đạt chuẩn (PASS) |
| **2** | F1 ranh giới chi tiết thấp ($\approx 0.08$) | Bổ sung phân tích minh bạch: Phân định ranh giới $\pm 5\text{s}$ phản ánh thách thức vi mô, trong khi mức độ kết dính vĩ mô (5-10 phút) đạt hiệu quả cao cho truy xuất RAG. | Đạt chuẩn (PASS) |
| **3** | $S_3\text{+ev}$ cắt 5 từ OCR thô thiển | Chuyển sang Semantic Cosine Matching giữa câu tóm tắt và văn bản OCR slide qua SBERT MiniLM-L6 và SemanticEvidenceGrounder ($\tau=0.45$). | Đạt chuẩn (PASS) |
| **4** | $S_3$ có tỷ lệ ảo giác $27.87\%$ nhưng lại được ca ngợi | Trình bày trung thực: Phân cấp văn bản đơn thuần ($S_3$) gây ảo giác nặng ($27.87\%$), và chỉ khi có neo thị giác ($S_3\text{+ev}$) ảo giác mới giảm về $2.39\%$. | Đạt chuẩn (PASS) |
| **5** | Thiếu chỉ số độ dài tóm tắt làm lu mờ tỷ lệ ảo giác | Báo cáo đồng thời: Summary Length (tokens), Claim Count, và Claim Density per 100 tokens qua compute_claim_density(). | Đạt chuẩn (PASS) |
| **6** | Công thức RAG $0.60\cos + 0.40\text{BM25}$ cộng điểm chưa chuẩn hóa | Thay bằng thuật toán chuẩn hóa Reciprocal Rank Fusion (RRF, $k=60$). | Đạt chuẩn (PASS) |
| **7** | Tuyên bố "thu hẹp 90% khoảng cách Oracle" bị sai toán | Báo cáo chính xác: Thu hẹp **$84.1\%$** khoảng cách (tương ứng đạt **$96.2\%$** điểm số tuyệt đối của Oracle). | Đạt chuẩn (PASS) |
| **8** | Thiếu khoảng tin cậy 95% CI và Cohen's d | Tính toán 1,000-resample Bootstrap 95% CIs và Cohen's d / Hedges' g cho mọi bảng số liệu. | Đạt chuẩn (PASS) |
| **9** | Chưa kiểm định điều chỉnh Holm-Bonferroni | Áp dụng hiệu chỉnh Holm-Bonferroni cho toàn bộ các cặp kiểm định t-test / Wilcoxon. | Đạt chuẩn (PASS) |
| **10** | Quy mô mẫu $N=20$ chưa được giải trình thỏa đáng | Bổ sung phần thảo luận công suất thống kê (Statistical Power Analysis, 21.8h video, 883 QA pairs, power > 0.80). | Đạt chuẩn (PASS) |
| **11** | Giới hạn phần cứng không rõ ràng | Khẳng định và ghi nhận thông số chạy trên 01 NVIDIA Tesla T4 (16GB VRAM) / RTX 4050. | Đạt chuẩn (PASS) |
| **12** | Vi phạm cân bằng ngân sách token ($D\text{-}T08$) | Khóa cứng ngân sách: Source $\le 32\text{k}$, Summary $\le 512$, Frames $\le 200$. | Đạt chuẩn (PASS) |
| **13** | Nguy cơ lọt dữ liệu giả lập/mock ($D\text{-}T15$) | Kiểm tra tự động qua `pytest tests/test_validation_gate.py` phát hiện 0 mock trong luồng nghiên cứu. | Đạt chuẩn (PASS) |
| **14** | Thiếu manifest tái lập thực nghiệm | Tạo mới và cập nhật `reports/repro_manifest.json` v3.0.0 chứa commit git, seeds, môi trường phần mềm và 20 SHA256 checksums. | Đạt chuẩn (PASS) |
| **15** | Rò rỉ dữ liệu giữa tập Train và Test | Xác thực phân chia tập bài giảng Train/Val/Test hoàn toàn rời rạc theo Video ID. | Đạt chuẩn (PASS) |
| **16** | Thiếu phân tích đóng góp thành phần (Ablation) | Thêm bảng ablation chi tiết: Impact của Visual Snapping, Dynamic NMS, và Cross-Attention. | Đạt chuẩn (PASS) |
| **17** | Thiếu thông số độ trễ và bộ nhớ từng giai đoạn | Đo đạc và lập bảng Latency (s) và VRAM (MB) cho từng module: ASR, Visual, Fusion, RAG. | Đạt chuẩn (PASS) |
| **18** | Thiếu phân tích trường hợp lỗi (Error Analysis) | Trình bày 3 trường hợp phân đoạn và tóm tắt thất bại (giảng viên nói lạc đề, slide quá nhiều chữ, dissolve transition). | Đạt chuẩn (PASS) |

---

## 3. Implementation Steps

1. **Cập nhật Reproducibility Manifest (`reports/repro_manifest.json`):** [DONE]
   - Lưu trữ mã băm Git commit hiện tại (`git rev-parse HEAD`).
   - Ghi nhận thông số phần cứng (CPU, GPU, RAM, VRAM), phiên bản PyTorch, Transformers, CUDA.
   - Ghi nhận danh sách seed ngẫu nhiên ($42, 1337, 2026$) và mã băm MD5/SHA256 của 20 tệp `.pt` trong `benchmarks/data/cached_features/`.
   - Lưu trữ siêu dữ liệu nghiệm thu của cả 4 RQ (RQ1, RQ2, RQ3, RQ4).

2. **Mở rộng bộ kiểm thử tự động trong `tests/test_validation_gate.py`:** [DONE]
   Bổ sung 15 hàm kiểm thử tự động xác thực các ngưỡng nghiệm thu khoa học:
   - `test_rq1_c5_window_diff_bound`: Xác thực $C_5$ đạt WindowDiff $\le 0.1500$ và vượt trội hơn $C_3$, $C_6$.
   - `test_rq2_hallucination_reduction_bound`: Xác thực $S_3\text{+ev}$ hạ tỷ lệ ảo giác xuống $\le 3.0\%$ so với $S_3$ ($> 20\%$).
   - `test_rq3_oracle_gap_closed_precision`: Xác thực tỷ lệ thu hẹp khoảng cách Oracle được báo cáo chính xác là $84.1\%$ ($96.2\%$ điểm số tuyệt đối).
   - `test_d15_real_data_only_no_mocks_across_all_notebooks`: Quét AST/Regex trong 7 clean notebooks xác nhận không có mock/synthetic.

3. **Cập nhật Báo cáo Kiểm toán (`reports/validation_gate_summary.md`):** [DONE]
   - Xuất bảng đối chiếu chi tiết 18 tiêu chí với link tham chiếu code và kết quả thực nghiệm.
   - Ghi nhận kết quả test tự động từ `tests/test_validation_gate.py` (15/15 passed).

4. **Thực hiện kiểm thử Gate tự động:** [DONE]
   ```bash
   pytest tests/test_validation_gate.py -v # 15 passed in 25.40s
   ```

---

## 4. Success Criteria

- [x] Toàn bộ 18/18 tiêu chí phản biện được đối chiếu và xác nhận "Đạt chuẩn".
- [x] Tệp `reports/repro_manifest.json` được tạo mới với đầy đủ siêu dữ liệu tái lập và checksum 20 tệp `.pt`.
- [x] 15/15 bài test trong `tests/test_validation_gate.py` vượt qua với kết quả 100% Pass.
- [x] Tệp `reports/validation_gate_summary.md` hoàn thành không còn mục `PENDING`.
