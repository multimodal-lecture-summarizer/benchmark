# RQ2 TIB 120: semantic-only rescore v2

Notebook: `benchmark/experiments/notebooks/rq2-tib-120-semantic-rescore-colab.ipynb`.

## Phạm vi và lý do

Lần chạy gốc đã sinh 240 tóm tắt và có ROUGE-L cho 120 cặp; semantic scoring dừng tại `valid/208` với lỗi `Retokenized sentence window exceeds capacity; no truncation allowed`. Scorer v1 chia theo token offsets rồi cắt lại văn bản, nên lần tokenize thứ hai có thể vượt giới hạn. Scorer v2 chia trực tiếp content token IDs, thêm special tokens và pad đúng giới hạn, chạy toàn bộ SentenceTransformer pipeline, gộp theo số content tokens rồi chuẩn hóa. Không decode/retokenize, không truncation. BERTScore và hai checkpoint/revision giữ nguyên khai báo gốc.

Scorer, runtime và notebook v1 không bị sửa. Thay đổi này là scoring amendment sau lỗi implementation, không phải kết quả semantic của protocol code v1. Toàn bộ 120 cặp được chấm lại; không trộn 28 semantic scores cũ.

## Chạy trên Colab

1. Giữ thư mục Drive `MyDrive/RQ2_TIB_120_20261012/data` và `formal-run-v1`, gồm receipt gốc và `dispatches.jsonl`. Notebook xác minh cohort/protocol/bundle hashes, receipt seal, 240 prediction, nguồn, dispatch usage và tính lại ROUGE để đối chiếu.
2. Dừng phiên cũ, mở notebook mới. Nên chọn T4; có thể đặt `DEVICE='cpu'`. Notebook không nạp Qwen hoặc gọi generation.
3. Chạy lần lượt. Nếu cell dependencies cài/đổi package, Restart session rồi chạy lại từ đầu để tránh module cũ trong kernel. Không cài pin NumPy 1.x vào kernel Colab.
4. Cell encoder kiểm equivalence câu ngắn và windowing thực tế trên source/S1/S3 của `valid/208`. Chỉ chạy vòng 120 mẫu khi preflight qua.
5. Kết quả ghi vào `MyDrive/RQ2_TIB_120_20261012/semantic-rescore-v2`, tách khỏi run gốc. Dùng cùng output để resume khi code/scorer/package/device/batch identity khớp. Đổi identity cần output mới. Lỗi được giữ và các mẫu sau tiếp tục; chỉ bật `RETRY_FAILED=True` khi chủ động thử lại lỗi đã xem.
6. Không chạy hai phiên cùng output. Nếu kill tiến trình để lại `.rescore.lock`, xác nhận phiên cũ đã dừng rồi chỉ xóa lock trước resume. Không sửa/xóa receipt gốc.

## Kết quả hiển thị

- Metric coverage/means; bảng theo short/medium/long; grouped exploratory intervals.
- Bảng đầy đủ 120 ID và toàn bộ reference/S1/S3 có thể mở từng mẫu; failure/pending CSV.
- Sáu PNG: coverage, paired delta histograms, paired scatter, stratum deltas, interval plots, original generation costs.
- `rescore-receipt.json`, `aggregate-report.json`, per-item CSV và các bảng metric.
- Chi phí generation kế thừa nguyên trạng; rescore attempts/durations/initialization sessions và environment files báo riêng. Không cộng lại chi phí generation và không gọi rescore device timing là speedup generation.

Hoàn tất khi hai semantic metrics đều có 120/120 paired scores và không còn failure/pending/interrupted. Output thiếu điểm vẫn được xuất, với null và no-data panels; không gán điểm thiếu bằng 0. Grouped intervals chỉ exploratory; creator abstracts không phải factual-summary GT đã xác minh.

## Xác minh và giới hạn

Scorer: năm kiểm thử trên pipeline thật tạo offline (BertModel + FastTokenizer + SentenceTransformer Pooling/Dense/Normalize), gồm short encode equivalence, Unicode/UNK/MASK IDs, coverage/length, weighted pooling và batch invariance. Runtime: bảy kiểm thử receipt integrity, 120-pair recomputation, immutability, failure/explicit retry, interruption/resume, identity/lock và unchanged generation costs. Visualization: hai kiểm thử không có/một semantic success, giữ null và vẫn xuất ledger/PNG. Notebook schema/source syntax/embedded bytes được kiểm tra; source cũ khớp frozen protocol hashes, giữ đúng CRLF bytes.

**2026-10-13 execution update:** notebook đã chạy trên Tesla T4; preflight `valid/208` qua, cả 120 cặp có BERTScore và source SBERTScore v2, không có failure/interrupted/pending. Sáu code cells đã thực thi, sáu PNG và không có error output. Reference và 240 tóm tắt khớp nguyên văn notebook gốc. Đây là kiểm tra output notebook; receipt gốc trên Drive chưa có ở local để audit độc lập. Fixtures unit tests không phải điểm benchmark.

[Kết quả hiện tại](rq2-tib-120-results-261013.md): delta S3−S1 ROUGE-L +0,003269; BERTScore +0,002108; source SBERTScore +0,003572. Mọi grouped exploratory interval 95% đều đi qua 0; chưa xác lập winner. Chi phí rescore báo riêng với generation, không chạy lại Qwen. Không cần rerun chỉ để tìm kết quả có lợi hơn.
