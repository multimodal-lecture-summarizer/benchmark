# RQ1: sàng lọc GT nguồn SSLectures → MIT OCW

**Quyết định sau báo cáo:** Người dùng đã bỏ Yale và chọn SSLectures làm nhánh khảo sát tiếp theo. [Handoff hiện hành](./rq1-sslectures-260929-1414-route-decision-report.md) thay thế khuyến nghị quay về Yale ở cuối báo cáo này. Kết quả sàng lọc 9/9 `gt_provenance_hold` vẫn giữ nguyên.

**Kiểm:** 2026-09-29 14:08, Asia/Bangkok. Đây là cổng metadata/source đầu tiên theo [hướng đã đề xuất](./research-260929-1355-rq1-official-source-stable-route-report.md). Không tải video, không chạy model, không tạo hoặc sửa GT. Chỉ xử lý nội bộ; MITFLD 35 vẫn là pilot. [Receipt khóa mẫu trước khi mở trang publisher](./rq1-sslectures-260929-1401-prelocked-source-screen-receipt.json); [receipt kết quả từng trang](./rq1-sslectures-260929-1401-mit-ocw-source-screen-receipt.json).

## Kết luận

**9/9 bài tìm được trang video MIT OCW và liên kết “download the video”; 0/9 trang lecture công bố bảng mốc/tiêu đề chapter nội bộ tương ứng.** Vì thế CSV SSLectures chưa được xác nhận là `publisher_timed_toc` trên mẫu đã khóa. Có thể tồn tại nguồn creator/author khác cho các mốc này, nhưng chưa được truy ra và xác minh. Giữ **9/9 `gt_provenance_hold`, 0 D2**; dừng trước tải và giải mã theo đúng cổng dừng. Đây không phải kết luận nhãn SSLectures sai hoặc media không tải được.

## Mẫu và đối chiếu

Tải duy nhất CSV metadata [Zenodo 10498680](https://zenodo.org/records/10498680), 83.829.839 byte, SHA-256 `c9261cccb1f637c25d0e0ccb1cbc72ecf78128dc790bb69eb1c9826efd6be609` (đọc lại file cache và xác nhận hash). Có 1.378 hàng/69 khóa. Quy tắc khóa trước khi xem trang nguồn: sắp 69 tên khóa, lấy chỉ số 0/17/34/51/68; trong mỗi khóa lấy tối đa hai tên bài đầu theo thứ tự chữ. Khóa đầu chỉ có một bài; giữ nguyên **9 hàng/5 khóa**, không bù mẫu. Số chapter và title trong CSV khớp cho 9 hàng; `auto_generated=False` ở 9 hàng **không đủ chứng minh** nguồn mốc, chất lượng hoặc quyền.

| Dòng CSV | Khóa / bài đã khóa | Trang MIT OCW | Mốc nội bộ trên trang |
|---:|---|---|---|
| 4 | Atomic and Optical Physics I / Atoms in External Fields II | [Lecture 10](https://ocw.mit.edu/courses/8-421-atomic-and-optical-physics-i-spring-2014/resources/lecture-10-atoms-in-external-fields-ii/) | Không thấy |
| 404 | Fundamentals of Photovoltaics / Thin Films Part II | [Lecture 13](https://ocw.mit.edu/courses/2-627-fundamentals-of-photovoltaics-fall-2013/resources/2011-lecture-13-thin-films-materials-choices-and-manufacturing-part-ii/) | Không thấy |
| 405 | Fundamentals of Photovoltaics / Solar Cell Characterization | [Lecture 16](https://ocw.mit.edu/courses/2-627-fundamentals-of-photovoltaics-fall-2013/resources/2011-lecture-16-solar-cell-characterization/) | Không thấy |
| 736 | Laboratory Chemistry / The Ferrocene Lecture | [Lecture 2](https://ocw.mit.edu/courses/5-310-laboratory-chemistry-fall-2019/resources/lecture-2-the-ferrocene-lecture/) | Không thấy |
| 740 | Laboratory Chemistry / Catalase Part 1 | [Lecture 11](https://ocw.mit.edu/courses/5-310-laboratory-chemistry-fall-2019/resources/lecture-11-catalase-part-1/) | Không thấy |
| 1016 | Psychology and Economics / Social Preferences II | [Lecture 11](https://ocw.mit.edu/courses/14-13-psychology-and-economics-spring-2020/resources/lec11-social-pref-ii/) | Không thấy |
| 1017 | Psychology and Economics / Social Preferences IV | [Lecture 13](https://ocw.mit.edu/courses/14-13-psychology-and-economics-spring-2020/resources/lec13-social-pref-iv/) | Không thấy |
| 1365 | Topics in Mathematics with Applications in Finance / Introduction | [Lecture 1](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/resources/lecture-1-introduction-financial-terms-and-concepts/) | Không thấy |
| 1370 | Topics in Mathematics with Applications in Finance / Time Series Analysis II | [Lecture 11](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/resources/lecture-11-time-series-analysis-ii/) | Không thấy |

Cả chín trang công bố tên bài/giảng viên, mô tả, liên kết tải và transcript; không hiển thị mục “Video Chapters” hay cặp timestamp–title chương trong nội dung trang. Kiểm trực tiếp HTML `200`, lưu SHA-256 mỗi trang trong receipt; không tải archive media. Vài tiêu đề trong CSV cũng xuất hiện như từ vựng mô tả bài, nhưng **không có mốc gắn với chúng** trên trang. Trang [Zenodo](https://zenodo.org/records/10498680) mô tả CSV có segmentation và nói quyền video/transcript/chapter/title thuộc các chủ nội dung; record không cho mapping tới nguồn mốc gốc của từng bài hoặc protocol QC đủ để mặc định coi CSV là annotation expert.

## Hệ quả cho hướng official

- **Hạ ưu tiên SSLectures → MIT OCW.** Đường video được publisher liên kết là điểm thuận lợi, nhưng cổng GT nguồn đã không qua ở mẫu cố định. Không mở rộng download 69 khóa hay retime CSV. Nếu tìm được nguồn chapter riêng do MIT/creator công bố hoặc tài liệu annotation độc lập có QC, kiểm lại **đúng 9 bài** trước; không thay bài sau khi thấy HOLD.
- **Yale vẫn là nhánh publisher GT rõ nhất hiện có**, với [34 mốc/tiêu đề đã snapshot trên sáu MOV](./rq1-yale-260929-publisher-gt-mov-structural-audit.md), song quyền thành phần và cỡ cụm giảng viên vẫn HOLD; không tự nâng lên official.
- [CLVTS](https://aclanthology.org/2025.findings-acl.904.pdf) có annotation/QC rõ hơn nhưng truy cập có điều kiện, gói mặc định không chứa raw video. Chỉ xem là dự phòng sau khi điều kiện truy cập/media được xác nhận; không liên hệ tác giả thay người dùng.
- [YTSeg CC BY](https://huggingface.co/datasets/retkowski/ytseg-cc-by) có creator chapters nhưng 276 hàng chỉ ở train và đường tải YouTube vẫn là gate riêng theo [Terms](https://www.youtube.com/t/terms). Không coi nhãn CC BY là quyền dùng pipeline tải tự động.

**Trạng thái quyết định:** chưa có cohort official RQ1. [Master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) còn ghi YTSeg official split + multimodal subset; thay nguồn phải có amendment trước selection. Bước ổn định tiếp theo là tìm **nguồn GT độc lập cho đúng chín bài** bằng chứng publisher/creator hoặc protocol annotation đã phát hành. Nếu không có, ngừng nhánh SSLectures và tập trung vào Yale qualification có giới hạn; nếu Yale cũng không qua quyền/sức mạnh split, báo RQ1 multimodal `not_eligible` thay vì tạo nhãn mới.

## Câu hỏi chưa giải quyết

1. Mốc trong `true_chapters_start`/`titles` của chín bài lấy từ trang creator nào, phiên bản nào? Có thể đối chiếu mà không phụ thuộc truy cập/tải YouTube trái điều khoản không?
2. SSLectures có công bố protocol gán/QC để mốc CSV là annotation độc lập được phát hành, thay cho publisher GT hay không?
3. Yale có thể đạt đủ quyền thành phần và số cụm giảng viên sau attrition để lập protocol official mới không?
