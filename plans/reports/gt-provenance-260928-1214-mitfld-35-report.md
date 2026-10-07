# MITFLD 35: nguồn gốc, quyền dùng GT và phương án GT độc lập

**Kiểm tra:** 2026-09-28 (Asia/Bangkok). **Phạm vi:** đúng [35 ID đã chọn](./mitfld-rq1-35-260928-1120-selected.csv), revision MITFLD `f5a5047e040ecf0f80a3cb67d64e324407f323ec`. Đây là nghiên cứu tài liệu và thiết kế quy trình; chưa liên hệ tác giả, chưa tạo nhãn mới.

**Cập nhật quyết định cùng ngày:** người dùng giữ official GT có sẵn và dùng cohort MITFLD này làm pilot/diagnostic. Xếp hạng phương án và quy trình GT độc lập bên dưới là phân tích lịch sử, **không còn là kế hoạch triển khai cho official RQ1**. Xem [trạng thái hiện hành](./rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md).

## Kết luận và bằng chứng

1. [Dataset card của tác giả trên Hugging Face](https://huggingface.co/datasets/robotwang/MITFLD) gọi `frags/<video_id>.json` là “ground truth fragment annotations” và ghi MIT OpenCourseWare là nguồn video. Card không nêu cách tạo `frags`, số người gán, rubric, kiểm định, độ lệch thời gian so MP4, hoặc giấy phép cho `frags`/transcript/video. Viewer của HF còn báo lỗi cast do trộn schema `frags` và transcript; nên phải đọc file riêng tại revision đã khóa.
2. [Repo framework của tác giả](https://github.com/wjq1015-hku/lecture-fragmentation) hướng dẫn tải MITFLD và trích dẫn bài báo, mô tả dataset abstraction và metric. Trang repo hiện có hai commit, không hiện file LICENSE ở root hoặc tuyên bố cấp quyền dữ liệu. **Quyền dùng code và quyền dùng nhãn là hai câu hỏi riêng.**
3. [Bản ghi công bố của HKMU](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) xác nhận bài báo đã xuất bản ngày 21-07-2025, MITFLD là dataset cho *lecture video fragmentation*, không dùng video tổng hợp. Abstract không giải thích provenance của từng nhãn. Toàn văn DOI `10.1145/3746640` bị ACM trả 403 trong phiên này; vì vậy **không thể khẳng định bài báo đầy đủ cũng thiếu phương pháp gán nhãn**.
4. [Ledger kiểm 35 file](./mitfld-rq1-35-260928-1126-annotation-ledger.csv) xác nhận 35/35 `frags` tải và parse được, 479 mốc thô, tăng nghiêm ngặt và nằm trong khoảng transcript. Đây chỉ là **đúng cấu trúc**. Tổng transcript dài **37,04 giờ**. Không chứng minh mốc là chapter ngữ nghĩa do người tạo, không chứng minh chất lượng hay quyền sử dụng.

**Trạng thái:** `gt_provenance_license=unverified` cho 35/35. Không gọi `frags` là “expert chapter GT”; không xuất bản lại file JSON hay dùng làm official D2 khi chưa có quyền/phương pháp. Việc card công khai và yêu cầu citation không tự tạo một giấy phép tái sử dụng.

## Quyết định xếp hạng cho RQ1

| Hướng | Khớp RQ1 | Chi phí/độ phức tạp | Rủi ro và bảo trì | Xếp hạng |
|---|---|---|---|---:|
| Tác giả xác nhận bằng văn bản về quy trình, media/timebase, QC và quyền cụ thể cho `frags`; kiểm thêm tương đương chapter | Giữ được GT gốc và khả năng so với paper; cần kiểm semantic alignment | Thấp nếu phản hồi đủ; phụ thuộc thời gian tác giả | Phụ thuộc phản hồi; quyền MP4 và ngoại lệ vẫn là gate riêng | **1** |
| Tạo GT chapter độc lập, hai người gán mù, adjudication, quyền của bộ nhãn mới rõ | Trực tiếp đo đúng endpoint chapter RQ1; linh hoạt với bản OCW đã kiểm | Cao: ước tính khoảng **128–177 giờ người**, chưa kể rà quyền video | Khác target fragmentation của MITFLD, không so trực tiếp kết quả paper; cần quản lý phiên bản, QA | **2** |
| Dùng ngay `frags` vì public trên HF | Chưa chứng minh đúng endpoint hoặc quyền | Thấp trước mắt | Rủi ro khoa học và quyền cao; không đạt gate D2 | **Không chọn** |

**Quyết định người dùng lúc 12:24:** bỏ qua kiểm chứng bằng email. Tiếp tục chuẩn bị GT chapter độc lập sau gate quyền và căn chỉnh MP4 OCW; không dùng `frags` MITFLD làm official GT trên bằng chứng hiện có. Không pha trộn `frags` gốc với nhãn độc lập trong cùng official test. Thay GT primary cần sửa protocol có ngày trước khi mở final test.

## Câu hỏi gửi tác giả (lưu để tham khảo, không gửi theo quyết định hiện tại)

**To:** `kwok@hkmu.edu.hk` (địa chỉ trong hồ sơ HKMU); có thể liên hệ thêm chủ dataset `robotwang` qua kênh HF. **Subject:** MITFLD `frags` provenance, timing and permission for 35 lecture videos

> Dear Professor Kwok,  
> We are assessing a fixed 35-video, course-disjoint subset of MITFLD for noncommercial lecture chaptering research. Could you please clarify, separately for `frags`, transcripts and MP4s:
>
> 1. Who created the `frags` boundaries (human annotators, OCW chapters, algorithm or a combination)? What were the exact instructions/rubric, number of annotators, adjudication and quality checks? Were timestamps revised after video re-encoding?
> 2. Which precise media version/hash and time origin does each timestamp use? Are boundaries meant as semantic chapter starts, lecture key points, slide changes, or another target? Are 0 and the final video time sentinel values?
> 3. What explicit permission/license permits local noncommercial research evaluation on these 35 IDs, model development (if applicable), publication of aggregate scores, and distribution of derived chapter labels or individual `frags`? Please identify any third-party restrictions or required attribution.
> 4. Is there a frozen course mapping or recommended course-disjoint split, and are any of the 35 IDs unsuitable because of label generation or media edits?
>
> We can provide the exact ID list and SHA-256 hashes privately. Thank you.

Không gửi thông điệp khi chưa được ủy quyền liên hệ. Lưu câu trả lời nguyên bản, ngày, người trả lời và phạm vi quyền; xác minh người trả lời có thẩm quyền với dữ liệu và media.

## Quy trình GT độc lập khả thi cho đúng 35 ID

1. **Khóa đối tượng:** chỉ dùng 35 ID đã chọn và bản OCW MP4 đã kiểm quyền/căn chỉnh; lưu URL, hash media, duration decoded, time origin, split/course, revision rubric. Nếu file fail rights/alignment, dừng nhãn bài đó và dùng reserve cùng khóa theo thứ tự đã khóa, không chọn theo điểm mô hình.
2. **Rubric trước khi gán:** chapter boundary là lúc chủ đề/khái niệm giảng dạy thay đổi đủ để đặt tiêu đề có nghĩa cho người xem. Không tự coi chuyển slide, ngừng nói, đổi camera, ví dụ ngắn là chapter. Cho phép intro/outro và đoạn không thuộc bài học với mã riêng. Ghi `start_s`, `title`, `rationale`, modality evidence, confidence; thời gian tính từ frame/PCM decoded OCW. Quy định cách xử lý bài review, nghiên cứu ngắn, trình bày sinh viên trước khi xem split.
3. **Pilot rubric:** dùng bài *ngoài 35* và ngoài final test để hiệu chỉnh hướng dẫn, không dùng model prediction hay `frags` MITFLD làm đáp án. Khóa rubric/tolerance sau pilot. Nếu không có pilot phù hợp quyền, cần ghi rõ hạn chế và giữ rubric ban đầu.
4. **Hai lượt độc lập:** hai người được đào tạo xem/nghe toàn bài, có transcript để định vị nhưng mù với `frags`, dự đoán mô hình và split. Mỗi người tạo nhãn riêng; không trao đổi cho tới lúc khóa file cá nhân. Có thể cho xem tài liệu OCW được cấp quyền; log tài liệu đã xem.
5. **QC:** ghép boundary một đối một trong ngưỡng thời gian đã đăng ký (đề xuất báo cáo song song ±15/30/60 s, ngưỡng adjudication chọn từ pilot). Báo cáo precision/recall/F1 giữa hai người, số chapter/video, phân bố chênh lệch, tỷ lệ bất đồng theo khóa. Người thứ ba xem mọi boundary thiếu ghép hoặc khác target/tiêu đề; quyết định được lưu cùng lý do, không xóa nhãn gốc. Rà ngẫu nhiên 10% bài đã thống nhất và toàn bộ bài review/khác chuẩn.
6. **Freeze:** lưu nhãn cá nhân, bản adjudicated, rubric, log chỉnh sửa, media hashes, chữ ký người gán/quyền đóng góp, manifest version. Chỉ release nhãn mới theo giấy phép đã được người tạo nhãn đồng ý và khi không vi phạm quyền OCW/media; tránh kèm video, frame, transcript/slide có bản quyền. Giữ final test niêm phong sau freeze và đánh giá một lần theo protocol.

**Công ước ước lượng công sức:** 37,04 giờ video × 2 người × 1,5–2,0 giờ làm/giờ video = 111–148 giờ người; adjudication 0,3–0,5 giờ/giờ video = 11–19 giờ; pilot/rubric 6–10 giờ; tổng khoảng **128–177 giờ người**. Đây là kế hoạch năng lực, chưa đo tốc độ gán thực tế. Không bao gồm quyền, tải media, kiểm căn chỉnh, tuyển người hay đào tạo chuyên môn sâu.

## Độ tin cậy và giới hạn

- Nguồn chính: dataset card/file tree của người phát hành, repo framework của tác giả, bản ghi công bố của trường. Chúng xác nhận **mục đích và sự tồn tại** MITFLD; không nguồn nào trong phần truy cập được cung cấp hợp đồng quyền/rubric chi tiết. Ledger nội bộ chứng minh cấu trúc 35 file, không chứng minh chất lượng nhãn.
- Không đọc được toàn văn ACM, không nhận phản hồi tác giả, không kiểm lịch sử commit HF/GitHub đến mức chứng minh chưa từng có license. Kết luận đúng là **chưa tìm thấy đủ bằng chứng trong nguồn đã kiểm**, không phải tác giả không có quyền hoặc dữ liệu không dùng được.
- GT độc lập vẫn phụ thuộc gate quyền nội dung video, căn chỉnh và việc hai người có đủ năng lực về 21 khóa. RQ1 chaptering có thể khác lecture fragmentation/KPI; cần coi đó là thay đổi endpoint/protocol khi chuyển GT.

## Câu hỏi chưa giải quyết

1. Có tài liệu công khai bổ sung nào xác nhận nguồn gốc, QC, semantic target, phiên bản media/timebase và quyền `frags`/transcript/MP4 cho 35 ID mà không cần liên hệ tác giả?
2. Có người gán nhãn độc lập đủ năng lực cho 21 khóa, và ai nắm quyền cấp phép bộ nhãn mới?
3. Sau gate quyền và alignment, còn bao nhiêu bài đủ điều kiện để gán GT và giữ split course-disjoint?
