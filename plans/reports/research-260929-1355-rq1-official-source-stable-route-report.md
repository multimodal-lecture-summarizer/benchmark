# RQ1: hướng ổn định để có GT chapter official

**Ưu tiên nguồn đã đổi 2026-09-29 14:14:** Người dùng bỏ nhánh Yale, tiếp tục riêng SSLectures. [Quyết định hiện hành](./rq1-sslectures-260929-1414-route-decision-report.md) thay thế các khuyến nghị quay lại Yale trong nghiên cứu này; các số Yale dưới đây chỉ là lịch sử đối chiếu.

**Nghiên cứu:** 2026-09-29 13:58, Asia/Bangkok. **Phạm vi:** RQ1 đa phương thức, video bài giảng dài, mốc chương đã được publisher/tác giả phát hành trước dự án, xử lý media nội bộ và chỉ công bố số liệu tổng hợp. Không có người kiểm độc lập; không tự gắn nhãn, sửa mốc hay sinh GT. MITFLD 35 giữ vai trò pilot. Đây là quyết định nghiên cứu, **không phải D2 freeze hoặc kết quả official**.

**Cập nhật sau pilot nguồn, 14:08:** [Sàng lọc mẫu SSLectures đã khóa](./research-260929-1401-sslectures-mit-ocw-gt-source-screen-report.md) tìm 9/9 trang video MIT OCW nhưng 0/9 trang có mốc chapter nội bộ; nhánh này hiện `gt_provenance_hold`. Khuyến nghị ưu tiên SSLectures bên dưới là **giả thuyết trước sàng lọc**, chưa được xác nhận và không còn là đường tải/khóa D2 ngay. Ưu tiên tiếp là truy nguồn mốc của đúng chín bài; nếu không có bằng chứng độc lập, dừng nhánh.

## Tóm tắt quyết định

**Giả thuyết trước sàng lọc:** dùng bảng SSLectures như **chỉ mục ứng viên**, nhưng lấy trang MIT OCW gốc làm nguồn có thẩm quyền cho GT, video và điều kiện dùng. Thực hiện một vòng qualification nhỏ, khóa bài trước khi xem kết quả mô hình. Nếu không tìm được video dài với mốc chương nội bộ đúng bản media, dừng nhánh. Không nhập nguyên CSV SSLectures vào D2: kiểm trước đã thấy 7 hàng lệch cấu trúc, 4 chapter cuối âm và 974/1.378 hàng có chênh timebase trên 30 giây giữa hai trường thời gian. [Kiểm toàn CSV](./rq1-preexisting-gt-260928-1843-source-rights-d2-qualification-report.md); [record SSLectures](https://zenodo.org/records/10498680).

**Không có bộ nào hiện được xác nhận đủ mọi gate official.** MIT OCW có điều khoản cho phép dùng nội dung OCW để huấn luyện AI nếu đáp ứng attribution, phi thương mại và ShareAlike; nhiều trang resource cho tải video. Đây là lợi thế về đường media so với YouTube, **không tự chứng minh** một bài cụ thể có chapter GT, quyền mọi thành phần, chất lượng hình/OCR, split hay nguồn video không đổi. [MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), [ví dụ resource video](https://ocw.mit.edu/courses/3-020-thermodynamics-of-materials-spring-2021/resources/mit3_020s21_lecture_29_1080p_mp4/). Phạm vi dự án chỉ xử lý nội bộ; nếu sau này phát hành model/media, phải kiểm lại các điều kiện tương ứng.

## Phương pháp và tiêu chí

Đối chiếu báo cáo nguồn/receipt của dự án với nguồn chính của Yale, MIT OCW, YTSeg, AVLectures và paper CLVTS ngày 2026-09-29. Tìm trực tiếp trang điều khoản, dataset card, paper và repo tác giả; không tải thêm video hay dùng truy cập tự động YouTube. Thứ tự ưu tiên: (1) GT độc lập đúng nghĩa chapter/topic, (2) đường media và quyền dùng nội bộ, (3) khớp GT với media giải mã, (4) đủ giảng viên/khóa cho split và suy luận thống kê, (5) visual phù hợp, tài nguyên D2. Số bài trong paper/card chỉ là **trần metadata**, không phải mẫu đủ điều kiện.

## So sánh lựa chọn

| Lựa chọn | Điểm mạnh đã có | Nút thắt quyết định | Vai trò nên giữ |
|---|---|---|---|
| **SSLectures → MIT OCW gốc** | 1.378 bài/69 khóa trong [CSV đã kiểm](./rq1-preexisting-gt-260928-1843-source-rights-d2-qualification-report.md); MIT có [điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) nêu AI training phi thương mại và nhiều resource có tải video. | SSLectures không cấp quyền thay chủ video; thiếu mapping file gốc; chênh timebase lớn; chưa rõ bao nhiêu khóa có chapter **nội bộ** do publisher công bố. | **Ứng viên chính để sàng lọc có giới hạn; 0 confirmed D2.** |
| **Open Yale Courses** | Sáu MOV đã tải, hash/full decode sạch; 34 cặp mốc/tiêu đề publisher đã snapshot, 6/6 qua kiểm cấu trúc. [Receipt](./rq1-yale-260929-publisher-gt-mov-structural-audit.md). | [Yale Terms/Help](https://oyc.yale.edu/help) loại trừ thành phần bên thứ ba khỏi CC mặc định; 0/6 MOV có rights pass toàn thành phần. Tối đa mẫu chín bài hiện xét chỉ tám giảng viên; split đánh giá rất ít cụm. [Audit split](./rq1-yale-260929-1003-chart-rights-gt-split-report.md). | **Qualification/external diagnostic** sau kiểm quyền; không làm official chính từ mẫu hiện có. |
| **YTSeg / CC BY subset** | Chapter do creator công bố; bản gốc có quy mô lớn, CC BY subset có 276 video/14 kênh và audio đóng gói. [Card subset](https://huggingface.co/datasets/retkowski/ytseg-cc-by). | Bản CC BY chỉ có train; bản gốc có chồng kênh/ID giữa split theo [audit](./rq1-preexisting-gt-260928-1843-source-rights-d2-qualification-report.md). Giấy phép dataset/video không tự cấp đường tải MP4 qua YouTube; [YouTube Terms](https://www.youtube.com/t/terms) hạn chế tải nội dung và truy cập tự động. | Giữ làm đối chứng **text/audio** đúng giới hạn nếu protocol cho phép; chưa đáp ứng so sánh đa phương thức official trên cùng media. |
| **AVLectures CwS** | Repo tác giả mô tả 15 khóa có `segments_ts.txt`, video và OCR; MIT001 35 bài đã chạy pilot. [Repo](https://github.com/Darshansingh11/AVLectures). | Archive khóa khác từng trả 401; license repo không chứng minh quyền mọi MP4. `segments_ts.txt` và media đã qua xử lý cần kiểm timebase/nguồn từng khóa. | Duy trì pilot, không mở rộng official trước khi giải quyết access/quyền. |
| **CLVTS** | Paper mô tả 510 video, annotation/QC độc lập có sẵn. | Tác giả chỉ cung cấp transcript ẩn danh, visual features, annotation và link gốc; quyền truy cập qua liên hệ/điều kiện, không có raw video trong gói mặc định. [Paper, phụ lục đạo đức](https://aclanthology.org/2025.findings-acl.904.pdf). | Dự phòng nếu quyền truy cập và media được xác nhận; không phải đường D2 nhanh. |

## Quy trình đề xuất, theo cổng dừng

1. **Khóa pilot sàng lọc MIT OCW trước inference.** Từ danh sách 69 khóa SSLectures, chọn một mẫu nhỏ gồm nhiều khóa/giảng viên theo quy tắc cố định dựa trên metadata nguồn; ghi denominator, lý do chọn và cả các hàng lỗi cấu trúc. Không chọn theo OCR, F1 hoặc bất kỳ dự đoán nào. Chỉ đọc URL, metadata và GT ở bước đầu; chưa tải hàng loạt.
2. **Xác minh GT ở trang gốc.** Với từng bài, tìm chính publisher công bố chapter/topic start trong **một video dài**, cặp tiêu đề–mốc, timebase và revision. Nếu chỉ có clip rời, slide transition, `true_fragment_boundary` hoặc mốc tác giả dataset suy ra, loại khỏi official; không ghép clip hay sửa mốc để lấp chỗ trống.
3. **Kiểm media/quyền cho đúng bài.** Dùng link tải do MIT OCW công bố hoặc nguồn chủ quyền tương đương; lưu URL/revision, điều khoản, ngoại lệ trên trang/resource và nguồn các thành phần cần thiết cho xử lý nội bộ. Bài còn nghi vấn giữ HOLD. MIT OCW có chính sách chung cho AI, nhưng vẫn cần đối chiếu điều kiện từng resource. [Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/).
4. **Chỉ tải mẫu đã qua hai cổng trên.** Hash byte, full decode/PTS, so GT với duration của **file đó**, đo visual bằng lịch cố định không tạo OCR GT. Không biến kiểm cấu trúc thành chứng nhận onset ±3 giây. Giữ nguyên GT nguồn và báo sai số nhãn chưa đo được.
5. **Quyết định tiếp hay dừng trước khi mở rộng.** Nếu pilot nhiều khóa không tìm được đủ trường hợp GT gốc + media/rights + alignment, dừng MIT route và giữ RQ1 multimodal `not_eligible`. Nếu qua, mở rộng cohort bằng cùng quy tắc; đếm số giảng viên/khóa **sau attrition**, lập power/CI theo cụm, rồi sửa [master protocol](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) trước model selection nếu nguồn/split khác YTSeg. Split train/validation/final_test phải disjoint theo giảng viên và khóa; final_test niêm phong. Không gọi D2 chỉ vì đã có vài video.

## Vì sao cách này ổn định hơn

- Chỉ có **một nguồn gốc có thẩm quyền** cho mốc và media mỗi bài; SSLectures giúp tìm bài, không thay GT nguồn. Nếu không map được, không có lỗi im lặng do đổi timebase.
- Tránh phụ thuộc tải video YouTube khi [Terms](https://www.youtube.com/t/terms) chưa cho đường tải phù hợp; tránh xem nhãn CC BY ở dataset là quyền mọi thành phần.
- Dừng sớm ở metadata/GT/quyền trước khi tốn tải và decode; cap D2 ≤50 GiB và ≤12 giờ vẫn áp dụng khi mở rộng. [Handoff hiện hành](./rq1-readiness-260929-1013-official-gt-d2-handoff-report.md).
- Không đổi chuẩn GT để cứu dataset. MITFLD 35 vẫn là pilot; Yale vẫn hữu ích cho kiểm phương pháp nhưng không bị gọi nhầm official. Kết quả âm tính hoặc không đủ dữ liệu được báo đúng trạng thái.

## Bước kế tiếp cụ thể

Lập ledger qualification MIT OCW từ **trang gốc**, chọn mẫu nhiều khóa trước khi xem kết quả mô hình, ghi `publisher_chapter_url`, `media_url`, `license/exception`, `course_id`, `speaker_id`, `GT revision`, `timebase` và trạng thái từng gate. Chỉ khi các dòng mẫu qua GT và quyền mới tải/decode. Giữ [Yale handoff](./rq1-readiness-260929-1013-official-gt-d2-handoff-report.md) là trạng thái bằng chứng hiện tại. Không chạy official 04a/04b trong lúc chưa có D2.

## Câu hỏi chưa giải quyết

1. Trong 69 khóa SSLectures, có bao nhiêu bài mà trang MIT OCW gốc công bố chapter starts **nội bộ** cho một video dài, với timebase khớp file tải?
2. Sau loại ngoại lệ quyền, lỗi GT/timebase, media và visual, còn bao nhiêu giảng viên/khóa độc lập? Có đủ theo power/CI và mục tiêu `n=300` trong [unified plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/plan.md) không?
3. Nếu MIT route qua gate, protocol amendment sẽ giữ YTSeg cho đối chứng text/audio riêng hay thay RQ1 official bằng cohort MIT có so sánh cùng unit?
