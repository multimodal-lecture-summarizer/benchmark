# Pilot40 — kiểm tay có hệ thống điểm MiniCheck theo câu (23/10)

Mục đích: ước lượng cờ "không được nguồn hỗ trợ" (xác suất < 0,5) của MiniCheck đúng bao nhiêu, trên mẫu phân tầng thay vì chỉ các bản điểm thấp nhất. Thay thế phần ước lượng của kiểm tay lần 1 (báo cáo theo bản, không nằm trong repo này).

## Dữ liệu và cách lấy mẫu

- Nguồn: `PRIVATE_pilot_sentence_scores.jsonl` (riêng tư, ngoài repo), 191 bản, đã kiểm: điểm trung bình view L khớp receipt lần 1 ở 191/191 bản; lần chạy lại lệch 0,0 trên 573 điểm view.
- Mẫu: bart, led, qwen3 × nguồn short/medium/long = 9 ô; mỗi ô 3 câu bị cờ + 2 câu không cờ, ngẫu nhiên có hạt giống cố định (seed 7), tổng 45 câu (27 cờ, 18 không cờ). lead3 và lexrank không lấy mẫu (câu trích nguyên văn, cờ rất ít: 3/120 và 4/579 câu).
- Chấm: một người chấm (tôi). Với mỗi câu tôi truy xuất hai đoạn nguồn gần nhất theo từ khóa, rồi tra thêm khi cần. S = nguồn hỗ trợ đầy đủ; P = ý chính đúng nhưng có chi tiết sai, bịa hoặc nâng quá mức; U = nguồn không nói hoặc mâu thuẫn; N = mảnh không phải khẳng định. Không đọc hết các nguồn 1.500–11.700 từ.
- Báo cáo này không chép nội dung câu. Muốn xem lại câu nào, tra theo (profile, bản, chỉ số câu) trong bảng ở cuối.

## Kết quả

| Profile | Cờ: S (cờ sai) | P | U | N | Không cờ: S | P | U |
|---|---|---|---|---|---|---|---|
| bart | 0/9 | 4 | 4 | 1 | 5/6 | 1 | 0 |
| led | 3/9 | 5 | 1 | 0 | 6/6 | 0 | 0 |
| qwen3 | 5/9 | 3 | 1 | 0 | 6/6 | 0 | 0 |
| **Cộng** | **8/27** | 12 | 6 | 1 | **17/18** | 1 | 0 |

Khoảng tin cậy Wilson 95% cho tỷ lệ cờ sai (S trong số câu bị cờ): tất cả 8/27 ≈ 30% (16–48%); bart 0/9 (0–30%); led 3/9 (12–65%); qwen3 5/9 (27–81%). Mỗi ô chỉ 9 câu nên các khoảng rất rộng.

## Đọc kết quả

1. **Phần lớn cờ có lý do thật.** 18/27 cờ (67%) trỏ tới câu có chi tiết sai, bịa hoặc nguồn không nói (P hoặc U); chỉ 8/27 (30%) là câu nguồn hỗ trợ đầy đủ. Lỗi thật thường gặp: tên bị phiên âm sai, vai trò bị nâng ("đồng sáng lập"), ghép hai phát biểu, thay tên thư viện.
2. **Ở bart, 8/8 cờ có thể đánh giá đều trỏ tới câu có lỗi; ở led 6/9; ở qwen3 4/9.** Cờ của qwen3 sai nhiều hơn, nhưng mẫu nhỏ nên không đủ để nói chênh lệch giữa ba profile là thật.
3. **Không cờ ít bỏ sót.** 17/18 câu không cờ được nguồn hỗ trợ đầy đủ; 1 câu có sai lệch nhỏ (dịch vụ managed viết thành việc Microsoft tự dùng).
4. **Cờ sai có xác suất rất thấp.** Ví dụ câu qwen3 liệt kê kế hoạch phát hành của một dự án (nguồn nói rõ từng ý) có p = 0,02; câu led dàn ý ghép hai chỗ của nguồn có p = 0,08. MiniCheck không do dự ở các câu này.
5. **Mẫu cờ sai cùng kiểu:** câu gom nhiều ý hoặc ghép từ hai đoạn khác nhau của nguồn (kể cả khi từng nửa là nguyên văn) hay bị cờ. Phù hợp với giả thuyết MiniCheck chấm theo từng đoạn nguồn ngắn, nhưng **giả thuyết này chưa được kiểm chứng**.
6. **Điều chỉnh so với kiểm tay lần 1.** Lần 1 (8 bản điểm thấp nhất, đọc theo bản) kết luận cờ của qwen3 "gần như toàn bộ không khớp"; mẫu phân tầng theo câu cho khoảng một nửa (5/9). Ước lượng lần 1 quá cao do chọn đúng bản điểm thấp. Lần 1 cũng cho rằng cờ sai tập trung ở nguồn dài: mẫu này không xác nhận (qwen3: long 1/3, medium 2/3, short 2/3 cờ sai; quá ít để kết luận).
7. **Điểm trung bình theo bản của qwen3 ~0,5 không phải "lưỡng lự".** Phân bố điểm theo câu của qwen3 là hai đầu: 91 trong 355 câu ở dưới 0,1 và 82 ở trên 0,9; điểm trung bình bản là trung bình của các câu cực đoan. Nhận định lần trước ("MiniCheck lưỡng lự") sai.

## Hệ quả cho thiết kế

- Điểm MiniCheck cho thấy tín hiệu thật (phần lớn cờ trỏ tới lỗi), nên không vô dụng. Nhưng với cờ sai ~30% (có thể cao hơn ở qwen3), **chênh lệch `flagged_share` giữa các profile không diễn giải được như chênh lệch trung thực**, và không dùng để chọn mô hình.
- Đóng băng MiniCheck làm scorer cho selection300 chỉ hợp lý nếu ghi rõ: đo xác suất câu được một đoạn nguồn hỗ trợ, thiên về câu trích nguyên văn, có tỷ lệ cờ sai đáng kể trên câu tóm tắt gom ý.
- Các hướng thử trước khi đóng băng (chưa làm): chia câu gom ý thành khẳng định nhỏ trước khi chấm; kích thước đoạn hoặc mô hình MiniCheck khác; họ khác (AlignScore không chạy được trên transformers 5).

## Giới hạn

- Một người chấm, không có độ đồng thuận giữa người chấm; ranh giới S/P là chủ quan.
- 45 câu từ 3 profile; khoảng tin cậy rộng. Chưa đánh giá lead3 và lexrank.
- Truy xuất đoạn nguồn bằng từ khóa có thể bỏ sót đoạn hỗ trợ câu tổng hợp (thiên về gán nhãn P/U), hoặc chấp nhận quá dễ câu có từ vựng trùng (thiên về S).

## Bảng phán định (profile, bản, chỉ số câu trong file riêng tư)

| # | Loại | Profile | Bản | Nguồn | Câu | p | Phán định | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| 0 | cờ | bart | valid:398 | long | 0 | 0.03 | P | mơ hồ; chỉ gợi tương tác với C# |
| 1 | cờ | bart | valid:288 | long | 0 | 0.36 | P | vai trò nâng quá mức (tự xây và vận hành → đồng sáng lập) |
| 2 | cờ | bart | valid:398 | long | 2 | 0.40 | U | lộn xộn, nguồn không nói |
| 3 | không cờ | bart | valid:229 | long | 2 | 0.99 | S |  |
| 4 | không cờ | bart | valid:27 | long | 0 | 0.86 | P | dịch vụ managed bị viết thành việc Microsoft tự dùng |
| 5 | cờ | bart | valid:415 | medium | 2 | 0.24 | U | sai loại VPN (nguồn dùng OpenVPN, bỏ IPsec) |
| 6 | cờ | bart | valid:207 | medium | 0 | 0.12 | U | đúng ngoài đời nhưng nguồn không nói |
| 7 | cờ | bart | valid:230 | medium | 0 | 0.02 | P | vai trò nâng quá mức (làm việc tại → đồng sáng lập) |
| 8 | không cờ | bart | valid:220 | medium | 0 | 0.67 | S |  |
| 9 | không cờ | bart | valid:409 | medium | 1 | 0.99 | S |  |
| 10 | cờ | bart | valid:178 | short | 0 | 0.25 | P | lặp lại lỗi phiên âm, không có nghĩa |
| 11 | cờ | bart | valid:488 | short | 3 | 0.11 | U | Boost bị gọi là type system |
| 12 | cờ | bart | valid:368 | short | 0 | 0.40 | N | mảnh tên người nói, không phải khẳng định |
| 13 | không cờ | bart | valid:414 | short | 0 | 0.92 | S |  |
| 14 | không cờ | bart | valid:168 | short | 0 | 0.96 | S |  |
| 15 | cờ | led | valid:288 | long | 1 | 0.46 | P | ý chính có; so sánh với JSON không thấy trong đoạn truy xuất |
| 16 | cờ | led | valid:229 | long | 4 | 0.28 | P | ghép hai phát biểu khác nhau |
| 17 | cờ | led | valid:622 | long | 0 | 0.25 | P | 'phiên cuối' nâng quá mức |
| 18 | không cờ | led | valid:229 | long | 0 | 0.70 | S |  |
| 19 | không cờ | led | valid:826 | long | 1 | 0.98 | S |  |
| 20 | cờ | led | valid:220 | medium | 1 | 0.08 | S | câu dàn ý ghép từ hai chỗ |
| 21 | cờ | led | valid:457 | medium | 1 | 0.05 | U | sai tên thư viện; 'giới thiệu ngắn' bịa |
| 22 | cờ | led | valid:653 | medium | 1 | 0.44 | S |  |
| 23 | không cờ | led | valid:665 | medium | 1 | 0.97 | S |  |
| 24 | không cờ | led | valid:532 | medium | 2 | 0.97 | S |  |
| 25 | cờ | led | valid:114 | short | 1 | 0.27 | P | 'policy server' không thấy; nguồn nói API server |
| 26 | cờ | led | valid:542 | short | 1 | 0.34 | S | ghép hai câu của nguồn |
| 27 | cờ | led | valid:542 | short | 3 | 0.28 | P | tên tính năng bị sai |
| 28 | không cờ | led | valid:414 | short | 3 | 0.96 | S |  |
| 29 | không cờ | led | valid:168 | short | 5 | 0.97 | S |  |
| 30 | cờ | qwen3 | valid:273 | long | 10 | 0.02 | S |  |
| 31 | cờ | qwen3 | valid:102 | long | 6 | 0.03 | P | tổng hợp; so sánh ECB suy ra từ một nhận xét phần hỏi đáp |
| 32 | cờ | qwen3 | valid:826 | long | 0 | 0.01 | P | bịa nền tảng cá nhân; phần WPF/Silverlight có trong nguồn |
| 33 | không cờ | qwen3 | valid:288 | long | 1 | 0.96 | S |  |
| 34 | không cờ | qwen3 | valid:469 | long | 10 | 0.97 | S |  |
| 35 | cờ | qwen3 | valid:409 | medium | 0 | 0.08 | S | sai nhẹ một tên |
| 36 | cờ | qwen3 | valid:220 | medium | 6 | 0.44 | P | 'hỗ trợ C++' không thấy |
| 37 | cờ | qwen3 | valid:457 | medium | 8 | 0.42 | S |  |
| 38 | không cờ | qwen3 | valid:230 | medium | 1 | 0.56 | S |  |
| 39 | không cờ | qwen3 | valid:457 | medium | 6 | 0.60 | S |  |
| 40 | cờ | qwen3 | valid:488 | short | 7 | 0.27 | U | lời nói với khán giả bị đọc thành hành động của diễn giả |
| 41 | cờ | qwen3 | valid:690 | short | 7 | 0.02 | S |  |
| 42 | cờ | qwen3 | valid:178 | short | 8 | 0.06 | S |  |
| 43 | không cờ | qwen3 | valid:178 | short | 2 | 0.96 | S |  |
| 44 | không cờ | qwen3 | valid:196 | short | 8 | 0.98 | S |  |

## Câu hỏi còn mở

- Giả thuyết "chấm theo đoạn nguồn" có đúng không: thử cấu hình hoặc chia khẳng định, so lại trên cùng 45 câu.
- Có cần người chấm thứ hai hoặc mẫu lớn hơn (nhất là qwen3, lead3, lexrank) trước khi đóng băng scorer?
