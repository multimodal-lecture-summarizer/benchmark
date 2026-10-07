# YTSeg RQ1: quyết định quyền nghiên cứu nội bộ và bước qualification kế tiếp

**Ngày:** 2026-09-29. **Quyết định hiện hành:** [manifest 12 ID có phiên bản](./ytseg-qualification-260929-1811-scoped-research-gate-decision.csv); chỉ 10 ID TRAIN được xét GT/media/quyền. [Manifest 16:59](./ytseg-qualification-260929-1659-gate-decision.csv) giữ làm lịch sử. [Rà chứng cứ từng ID](./rights-review-260929-1758-ytseg-three-basis-ledger.csv) là nguồn lý do. Đây là quyết định qualification theo phạm vi sử dụng, **chưa phải D2**.

## Phạm vi và kết quả

Sử dụng phi thương mại trong môi trường nghiên cứu hạn chế truy cập: lưu file nguồn publisher, ASR, trích frame/cảnh, OCR, embedding, huấn luyện/đánh giá trên split hợp lệ. Công bố mã nguồn của nhóm, cấu hình, ID, checksum và kết quả tổng hợp. Không phát hành MP4, frame, clip hoặc transcript nguồn trong đợt này. Cổng quyền xét **xử lý nội bộ** bằng giấy phép công khai phù hợp hoặc ngoại lệ Điều 37a đủ điều kiện; không đòi thư riêng và không xét quyền phát hành nguồn ở cổng này. [MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) và [CS50P license](https://cs50.harvard.edu/python/license/) là hai nguồn cấp phép chính; [Điều 37a sau Nghị định 134/2026](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-134-2026-nd-cp-469388/64378.htm) là nhánh ngoại lệ khi cần.

| Cổng | Kết quả 10 TRAIN |
| --- | ---: |
| GT `target_ts` đúng representation | 10 pass |
| Media full-file/timeline | 10 pass |
| Quyền xử lý nghiên cứu đúng phạm vi | **2 pass**, 8 hold |
| Qua ba cổng qualification trên | **N=2 video thuộc G=2 nhóm độc lập** |
| Split/final-test/D2 | chưa khóa |

Hai video `pass`: `-7xg8pGcP6w` (Harvard CS50P, `group-01`) và `tCKk22kaZi4` (MIT 14.01, `group-04`). Credit và điều kiện NC/SA được ghi tại [ledger rà quyền](./rights-review-260929-1758-ytseg-three-basis-ledger.csv). Đây là quyền cho hoạt động đã mô tả, không là quyền không giới hạn đối với mọi đầu ra sau này.

Sáu video MIT 16.687 và một MIT 6.S897 còn `hold` vì PDF nêu tài sản ngoài CC nhưng chứng cứ hiện có chưa xác định **tài sản được gọi tên có hiện trong MP4 hay không**; `alLh1Jdqwvg` còn thiếu xác định ATIS thấy ở khoảng 50% có phải đúng ngoại lệ. `xsO2Ip6eiaY` còn `hold` vì clip ở 240 s/trang ở 1260 s cần xác lập điều kiện nguồn và tác động theo Điều 37a nếu dùng nhánh ngoại lệ. Không cần lặp GT/media hay mở quy trình xin thư không có điểm dừng; mẫu không hiệu quả để giải quyết được giữ `hold` và thay theo quy tắc cohort.

## Chuẩn bị bước kế tiếp

G=2 chưa đủ cơ sở cho suy luận theo nhóm và phân bổ split train/validation/final-test hợp lý. **Mở rộng nhóm bằng VidChapters có chọn lọc**, nhưng không tính ID giao YTSeg lần hai và không chuyển ngầm target. Dùng [prescreen năm khóa](./vidchapters-qualification-260929-1637-five-course-prescreen.csv): ưu tiên `3MOahpLxj6A` (MIT 6.041) và `AW3a2ECNFlE` (MIT 14.772) vì publisher mapping đúng ID; `LFOsw1Vccac` (MIT 21L.011) là reserve cần xem ngoại lệ phim trước media. Hai ID còn lại đang `hold_identity`, chưa khóa.

Trước khi tải media mới: (1) quyết định bằng amendment cách chuyển cặp `label,time` VidChapters thành cùng endpoint mốc chapter nội bộ, kiểm nội dung GT chứ không chỉ cấu trúc; (2) kiểm giấy phép/ngoại lệ cho đúng video và thao tác nội bộ; (3) khóa danh sách ID và reserve theo khóa/giảng viên, ghi lịch sử đã dùng train/tuning/pilot. Sau đó mới tải/đối chiếu media theo danh sách khóa, cập nhật N/G, kiểm khả năng chia split và xét D2. Không chọn mô hình hoặc chạy official RQ1 ở bước này.

## Câu hỏi chưa giải quyết

1. GT `label,time` của các bài VidChapters ngoài giao có cùng nghĩa mốc chapter bắt đầu như target YTSeg sau kiểm nội dung không?
2. Các khóa mới có đủ quyền và media đúng timeline để nâng G cho split/CI không, hay cần chọn thêm nhóm theo quy tắc prescreen?
3. Lịch sử sử dụng ngoài các receipt hiện có có ảnh hưởng vai trò final-test của hai ID `pass` hoặc ứng viên VidChapters không?
