# RQ1 SSLectures: kiểm gói phát hành và truy nguồn chín bài

**Truy nguồn tiếp 14:40:** [Kiểm snapshot/quy trình cho `zMlEb29UlKw` và `TgrNa_Guigs`](./rq1-sslectures-260929-1440-single-video-source-trace-report.md) chưa tìm được mắt xích nguồn chapter gốc. Kiểm cấu trúc thấy 9 cặp mốc cách dưới 10 giây trong 4/9 bài, không tương thích với danh sách chapter thủ công theo quy tắc YouTube hiện hành; vẫn không suy ra nguồn gốc nhãn. 9/9 tiếp tục HOLD.

**Kiểm:** 2026-09-29 14:32, Asia/Bangkok. Phạm vi: [mẫu khóa trước 9 bài/5 khóa](./rq1-sslectures-260929-1401-prelocked-source-screen-receipt.json). Không tải video, không đọc YouTube bằng pipeline tự động, không tạo/chỉnh GT. [Ledger từng bài](./rq1-sslectures-260929-1431-nine-row-provenance-ledger.csv) và [receipt máy đọc được](./rq1-sslectures-260929-1431-nine-row-provenance-receipt.json) lưu định danh, vị trí nhãn, nguồn phát hành, hash, media link và lý do HOLD.

## Kết luận

**Đã tìm được file annotation và đường nối video cho cả 9 bài, nhưng 0/9 có đường truy nguồn *người tạo/cách tạo* mốc chapter hoàn chỉnh.** `mit_videos_all_courses_segmentations.csv` chứa các danh sách `true_chapters_start`, `true_chapters_end`, `titles` ở đúng từng dòng. Đây là chapter **bên trong video**, không phải số thứ tự bài hoặc timestamp từng câu transcript. File `mit_chapters_summarized.csv` có `video_URL` cho cùng khóa/tên bài; 9/9 YouTube ID này xuất hiện trong HTML trang MIT OCW tương ứng, và 9/9 trang có link tải MP4. Đối chiếu này xác nhận danh tính nguồn ở mức trang, **chưa chứng minh** MP4 cùng timebase hoặc nhãn do MIT/creator tạo.

[Record SSLectures trên Zenodo](https://zenodo.org/records/10498680) ghi dữ liệu được scrape từ nguồn công khai MIT OCW/AK Lectures và mô tả file segmentation, nhưng không cung cấp provenance/QC cho từng cặp mốc–tiêu đề. `auto_generated=False` trong hai CSV không định nghĩa ai gắn nhãn hoặc cách phân biệt chapter người đăng với chapter tự động. [Bài báo của nhóm tác giả](https://link.springer.com/chapter/10.1007/978-981-97-9255-9_4) ở phần abstract nói GPT-3.5 tạo **summary cho segment**; phần xem công khai không nói nguồn/cách tạo boundary và title. Không suy từ summary GPT rằng chapter cũng do GPT tạo. [YouTube Help](https://support.google.com/youtube/answer/9884579?hl=en) xác nhận có cả chapter do creator nhập trong mô tả và chapter tự động; thấy chapter trong trình phát không đủ để gắn `creator_provided`.

**Trạng thái:** 9 bản ghi annotation đang kiểm, **0 GT official được xác nhận, 0 D2**. Con số 1.378 dòng/69 khóa chỉ là quy mô CSV thô, không phải số mẫu GT tiềm năng đã xác nhận.

## A. Kiểm gói dữ liệu trước truy website

| Câu hỏi | Bằng chứng | Kết luận |
|---|---|---|
| Nhãn ở đâu? | `mit_videos_all_courses_segmentations.csv`: `true_chapters_start` + `titles`, kèm `true_chapters_end`; 9 dòng có tổng 145 cặp start/title. `Video numbers` chỉ là `video_N` theo khóa, không phải ID toàn cục. | Tìm thấy annotation artifact, xác định đúng loại nhãn. |
| Ai tạo, bằng cách nào? | Zenodo nói scrape từ MIT OCW; không có trường provenance/annotator/method/snapshot ở mức dòng. `auto_generated=False` thiếu định nghĩa. Abstract paper mô tả sinh summary, không chứng minh chapter origin. | **Không xác minh được** publisher/creator, researcher, thuật toán hay auto chapter. |
| Gắn video nào? | `mit_chapters_summarized.csv`: khóa `course_name` + `video_name`, `video_URL`; 9/9 YouTube ID khớp ID trong HTML MIT OCW và trang có link MP4. File summarized chỉ có 101 chapter rows cho 9 bài, so với 145 chapter trong file segmentation; không thay thế file GT chính. | Có ID và URL nguồn để kiểm tiếp; **chưa so duration/hash/timebase media**. |

Zenodo API record `10498680` trả DOI `10.5281/zenodo.10498680`, ngày phát hành metadata `2024-01-12`, `updated=2025-04-24T07:58:12.166303+00:00`. API chỉ liệt kê ba CSV, không kèm repository hay tài liệu bổ sung trong `related_identifiers`. File segmentation: 83.829.839 byte, MD5 `923d0747e1a85e6991b3053737682c86` khớp Zenodo, SHA-256 `c9261cccb1f637c25d0e0ccb1cbc72ecf78128dc790bb69eb1c9826efd6be609`. File summarized: 74.521.289 byte, MD5 `4759e0b0b99e08a47be06d687870562c` khớp Zenodo, SHA-256 `fa134cdd666b978a5e31d82cc088d6bf8ab82dec78f09f67ab48d1c2588d51fe`. [Receipt](./rq1-sslectures-260929-1431-nine-row-provenance-receipt.json) lưu hash metadata trả về và HTML của chín trang.

## B. Bảng bằng chứng chín bài đã khóa

**Quy ước:** Vị trí nhãn là `S:<dòng>` trong file segmentation nêu trên (`true_chapters_start` + `titles`); `C:<số dòng>` là số row tìm được trong file summarized để truy YouTube ID. Bằng chứng phát hành ở mỗi dòng là [Zenodo record](https://zenodo.org/records/10498680) và trang OCW được liên kết. Hash S/C là hai SHA-256 ở mục A; hash từng trang nằm trong [ledger](./rq1-sslectures-260929-1431-nine-row-provenance-ledger.csv). `HOLD-P` = chưa tìm thấy bản phát hành chapter gốc hoặc mô tả tạo nhãn, nên chưa phân biệt manual/automatic/dataset-generated. Tất cả row đều `gt_provenance_hold`; không row nào được đánh dấu `creator_provided`.

| S / C | Khóa – bài | Source video ID và trang OCW | Nhãn trong S | Nguồn gốc; bằng chứng phát hành | Trạng thái / lý do |
|---|---|---|---:|---|---|
| 4 / 16 | Atomic and Optical Physics I – Atoms in External Fields II | `zMlEb29UlKw` · [OCW](https://ocw.mit.edu/courses/8-421-atomic-and-optical-physics-i-spring-2014/resources/lecture-10-atoms-in-external-fields-ii/) | 19 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 404 / 7 | Fundamentals of Photovoltaics – Thin Films Part II | `PLVjevMsQpQ` · [OCW](https://ocw.mit.edu/courses/2-627-fundamentals-of-photovoltaics-fall-2013/resources/2011-lecture-13-thin-films-materials-choices-and-manufacturing-part-ii/) | 9 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 405 / 7 | Fundamentals of Photovoltaics – Solar Cell Characterization | `yHzpj_MDOdk` · [OCW](https://ocw.mit.edu/courses/2-627-fundamentals-of-photovoltaics-fall-2013/resources/2011-lecture-16-solar-cell-characterization/) | 7 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 736 / 10 | Laboratory Chemistry – The Ferrocene Lecture | `EuVpZmQ5v6A` · [OCW](https://ocw.mit.edu/courses/5-310-laboratory-chemistry-fall-2019/resources/lecture-2-the-ferrocene-lecture/) | 15 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 740 / 16 | Laboratory Chemistry – Catalase Part 1 | `TgrNa_Guigs` · [OCW](https://ocw.mit.edu/courses/5-310-laboratory-chemistry-fall-2019/resources/lecture-11-catalase-part-1/) | 33 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 1016 / 11 | Psychology and Economics – Social Preferences II | `S6JHQ3-bsHk` · [OCW](https://ocw.mit.edu/courses/14-13-psychology-and-economics-spring-2020/resources/lec11-social-pref-ii/) | 17 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 1017 / 21 | Psychology and Economics – Social Preferences IV | `K7QVIqV2QMk` · [OCW](https://ocw.mit.edu/courses/14-13-psychology-and-economics-spring-2020/resources/lec13-social-pref-iv/) | 29 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 1365 / 9 | Topics in Mathematics with Applications in Finance – Introduction | `wvXDB9dMdEo` · [OCW](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/resources/lecture-1-introduction-financial-terms-and-concepts/) | 12 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |
| 1370 / 4 | Topics in Mathematics with Applications in Finance – Time Series Analysis II | `_IFUfFuyQlU` · [OCW](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/resources/lecture-11-time-series-analysis-ii/) | 4 | Unknown; Zenodo + OCW, không có timed TOC nguồn | HOLD-P |

**Cần đọc chính xác bảng:** `S / C` là dòng CSV segmentation / **số row chapter** trong summarized, không phải timestamp. `Video numbers` và thứ tự bài không dùng làm GT. Timestamp transcript trong summarized không dùng thay `true_chapters_start`. [Trang OCW và PDF transcript ví dụ](https://ocw.mit.edu/courses/8-421-atomic-and-optical-physics-i-spring-2014/resources/lecture-10-atoms-in-external-fields-ii/) giúp kiểm bài/video, không có timed TOC chapter tương ứng trên trang đã xem.

## C. Nguồn đã dò và đường xử lý tiếp

Đã đọc [Zenodo API record](https://zenodo.org/api/records/10498680) cùng danh sách file/checksum, hai CSV, [abstract paper của nhóm tác giả](https://link.springer.com/chapter/10.1007/978-981-97-9255-9_4), chín trang MIT OCW và kết quả tìm kiếm web theo tên file/tác giả/ID + tiêu đề chapter. Không tìm thấy repository/supplement được record liên kết hoặc chapter snapshot độc lập trong phạm vi này. Các PDF transcript OCW là lời nói, không phải bảng nhãn chapter. Thử Wayback CDX cho ID `zMlEb29UlKw` trả HTTP 503 (Internet Archive temporarily offline), không có snapshot để xác minh. Không kiểm YouTube player/description bằng pipeline tự động; nếu có chứng cứ description do creator nhập, cần snapshot chính mô tả có ID, mốc, title và phân biệt auto chapter theo [YouTube Help](https://support.google.com/youtube/answer/9884579?hl=en).

**Bước kiểm tiếp:** tìm một bản mô tả/snapshot creator hoặc phương pháp gán nhãn đã phát hành cho **một ID trong chín ID trên**, đối chiếu ít nhất vài cặp start/title nguyên văn với S. Nếu tìm được, lặp cùng quy trình cho tám bài còn lại; một bài đạt chỉ chứng minh đường truy nguồn khả thi. Nếu không có, giữ `gt_provenance_hold`; không tải hàng loạt, không retime, không khóa D2. Có thể chuẩn bị yêu cầu maintainer hỏi file chứa chapter, nguồn nhãn và snapshot thu thập cho **chín ID đã khóa**; không yêu cầu tạo nhãn mới. Chưa gửi liên hệ ra ngoài.

**Nội dung liên hệ chuẩn bị, chưa gửi:** “Với chín video ID `zMlEb29UlKw`, `PLVjevMsQpQ`, `yHzpj_MDOdk`, `EuVpZmQ5v6A`, `TgrNa_Guigs`, `S6JHQ3-bsHk`, `K7QVIqV2QMk`, `wvXDB9dMdEo`, `_IFUfFuyQlU`, file hoặc snapshot nguồn nào chứa chapter timestamps và titles? Nhãn lấy từ publisher/creator hay được tạo khi xây dataset? Có bản phát hành, mã thu thập hoặc tài liệu QC để đối chiếu từng video không?”

## Câu hỏi chưa giải quyết

1. Các cặp mốc/title trong S được lấy từ creator description, chapter tự động, MIT OCW nội bộ hay thuật toán/nhóm SSLectures?
2. Có snapshot/repository/protocol công khai liên kết từng ID với chính các cặp mốc/title đó không?
3. Nếu xác minh được GT, cùng bản media MP4 được OCW liên kết có duration/timebase khớp S và qua quyền/chất lượng/split không?
