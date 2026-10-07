# Nghiên cứu toàn bộ nguồn RQ1: YTSeg và MITFLD

Kiểm tra ngày 2026-09-28 (Asia/Bangkok). Phạm vi: metadata của toàn bộ 276 ID trong YTSeg CC BY subset và 538 ID MITFLD, ánh xạ khóa học MITFLD, trang nguồn OCW và mẫu 10 MP4. Chỉ đọc metadata, HTML và HTTP `HEAD`; không tải hay giải mã media. Không dùng các số liệu dưới đây như xác nhận pháp lý hoặc kết quả benchmark.

## Kết quả đã xác minh

| Hạng mục | Kết quả | Giới hạn của kết quả |
|---|---:|---|
| YTSeg CC BY subset | 276/276 ID trả về từ YouTube Data API; cả 276 có `license=creativeCommon`, `privacyStatus=public`, `embeddable=true`; channel ID khớp manifest | Chỉ là trạng thái metadata hiện hành, không cấp quyền tải tự động hoặc xác nhận từng thành phần bên thứ ba |
| MITFLD | 538/538 ID trả về; cả 538 thuộc kênh MIT OpenCourseWare, `license=youtube`, công khai và nhúng được | Giấy phép chuẩn trên YouTube khác với giấy phép MIT OCW công bố trên trang tài nguyên; không lấy video qua YouTube từ phép kiểm này |
| MITFLD course map | 538 ID vào 25 nhóm khóa học; 536 có URL khóa học trong mô tả, 1 có tên khóa không URL, 1 cần khớp tiêu đề tài nguyên OCW | Hai ánh xạ ngoại lệ dựa vào bằng chứng yếu hơn URL trực tiếp; cần kiểm tra khi đóng băng D2 |
| Loại tài nguyên OCW | 65 ID thuộc 4 khóa được OCW gắn “Lecture Audio”; 473 ID thuộc 21 nhóm khóa ứng viên video | 473 là ứng viên theo nhóm khóa, chưa xác nhận từng MP4 có khung hình mang thông tin, GT hoặc quyền đủ điều kiện |
| 10 video MITFLD mẫu | 10/10 trang OCW công bố MP4; `HEAD 200`/`video/mp4`; 2 file trên OCW, 8 file trên Archive.org | Chỉ xác minh đường dẫn và header; chưa giải mã để khớp thời lượng, hình/âm thanh và mốc GT |
| Archive.org của mẫu | 8 file thuộc 7 Archive items có metadata `creator=MIT OpenCourseWare`, `uploader=ocw-prod@mit.edu`, `licenseurl=CC BY-NC-SA 4.0` | Metadata item không xử lý ngoại lệ bên thứ ba; cần đối chiếu credit và nội dung từng video |
| Đồng nhất file HF/OCW | 10/10 MP4 Hugging Face và MP4 do OCW dẫn tới có `Content-Length` khác nhau | Chứng minh không cùng byte; không kết luận khác nội dung hay khác timebase nếu chưa giải mã |

[Ledger YTSeg](./ytseg-260928-1031-current-license-ledger.csv) ghi revision dataset `282b0a039e82ed78f85adc1f99a94f87e1d47a97`, thời điểm kiểm tra, ID/kênh và ba trạng thái API. SHA-256: `dafdd41b870e7611f90de4f694243ddf28ac214680cedd3493be4af51a83a76a`.

[Ledger MITFLD](./mitfld-260928-1031-youtube-course-metadata-ledger.csv) ghi revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec`, metadata API, tiêu đề, mô tả đầu, course URL và thời lượng YouTube. SHA-256: `a2a0c1265f411a69a6ef441b4aa97336d1166c44d8b29018e8311814ce0220c2`. API dùng [`videos.list`](https://developers.google.com/youtube/v3/docs/videos/list) với xác thực; khóa không được ghi vào ledger hay báo cáo.

[Course map chuẩn hóa](./mitfld-260928-1031-normalized-course-map.csv) ghi 538 `video_id`, khóa group, URL OCW, bằng chứng ánh xạ, loại tài nguyên và cờ rà soát. SHA-256: `b9fced1fb98d24c21fc0bc0480bcf2f18acfc8dc125e57276203b93e7d9c2a62`. 513 hàng có URL mô tả trực tiếp; 23 hàng 18.217 dùng URL OCW được sửa; 2 hàng là ngoại lệ. URL ngắn `https://ocw.mit.edu/18-217F19` hiện chuyển tới khóa 18.225 năm 2023, trái với mô tả video “MIT 18.217 ... Fall 2019”; dùng [trang 18.217 Fall 2019](https://ocw.mit.edu/courses/18-217-graph-theory-and-additive-combinatorics-fall-2019/) làm canonical. `rL25BoFW1V4` có tên khóa 11.165 trong mô tả nhưng thiếu URL; `_GRVq26jIHs` không có mô tả, khớp tiêu đề [tài nguyên HST.508 trên OCW](https://ocw.mit.edu/courses/hst-508-genomics-and-computational-biology-fall-2002/resources/mithst_508f02_lec2b/).

Bốn nhóm “Lecture Audio”: [ESD.932](https://ocw.mit.edu/courses/esd-932-engineering-ethics-spring-2006/), [HST.508](https://ocw.mit.edu/courses/hst-508-genomics-and-computational-biology-fall-2002/), [MAS.531](https://ocw.mit.edu/courses/mas-531-computational-camera-and-photography-fall-2009/), [9.00](https://ocw.mit.edu/courses/9-00-introduction-to-psychology-fall-2004/). Ngược lại, trang khóa 6.801 không hiển thị “Lecture Videos” trong loại tài nguyên ở landing page nhưng [trang download 6.801](https://ocw.mit.edu/courses/6-801-machine-vision-fall-2020/download/) có mục Lecture Videos; không loại 6.801 chỉ theo landing metadata. Năm hàng 6.006 có tiêu đề “Problem Session”, cần quy tắc loại bài trước khi chốt cohort.

## Quyền và đường lấy media

[YTSeg CC BY subset](https://huggingface.co/datasets/retkowski/ytseg-cc-by) công bố text/audio và chapter metadata, không cung cấp MP4 trong subset. Trạng thái `creativeCommon` của 276 video đáp ứng bước kiểm tra giấy phép metadata hiện hành. [YouTube Terms](https://www.youtube.com/t/terms) và [API Developer Policies](https://developers.google.com/youtube/terms/developer-policies) vẫn phải được xét đối với tải/thu thập media; `yt-dlp` là khả năng kỹ thuật, không tự tạo quyền tải. Chưa có đường MP4 được xác nhận phù hợp cho visual/full trên YTSeg.

[MIT OCW Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) nêu CC BY-NC-SA 4.0 cho tài liệu thuộc phạm vi OCW, kèm điều kiện sử dụng và ngoại lệ bên thứ ba. Việc YouTube ghi `license=youtube` không tự phủ định giấy phép OCW cho tài nguyên do OCW xuất bản; quyền phải gắn với đúng file/nguồn. Tám file mẫu trên Archive.org thuộc bảy item do OCW upload, cùng `licenseurl=CC BY-NC-SA 4.0` trong metadata; ví dụ [MIT8.962S20](https://archive.org/details/MIT8.962S20). Đây là bằng chứng item-level tốt hơn trạng thái HTTP đơn thuần, nhưng chưa xác nhận credit hoặc ngoại lệ xuất hiện trong từng file.

Do cả 10 cặp HF/OCW có kích thước khác nhau, không được gán GT MITFLD sang file OCW chỉ bằng `video_id`. Cần so sánh decoded duration, timebase, vị trí sự kiện và quy tắc biên GT trước khi dùng MP4 OCW cho benchmark. Dùng direct link OCW/Archive được trang OCW chỉ định là hướng kiểm tra tiếp; không suy ra bản MP4 trên Hugging Face có cùng quyền.

## GT, split và ý nghĩa khoa học

[MITFLD card](https://huggingface.co/datasets/robotwang/MITFLD) gọi `frags` là ground truth nhưng không công khai trong phần đã kiểm được ai gán nhãn, tiêu chí ranh giới, mức đồng thuận hoặc giấy phép riêng. [Loader tác giả](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/mitfld.py) đọc JSON ranh giới; [base dataset](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/base_dataset.py) có thể chèn mốc 0 và duration. Hàm `random_split` chia ở cấp video, nên không đạt split độc lập theo khóa. Course map 25 nhóm là cơ sở để **thiết kế** group-disjoint split, chưa phải split đã khóa.

[YTSeg paper](https://aclanthology.org/2024.eacl-long.25.pdf) mô tả chapters do người tạo video cung cấp và split phân tầng theo channel. Subset 276 video chỉ có train, 14 channel rất lệch và không có `course_id`. Channel-disjoint split có thể thử như phép kiểm khác nếu sửa protocol, nhưng không đồng nghĩa course-disjoint hoặc expert GT. Không trộn nhãn YTSeg với MITFLD hay 35 video MIT001 theo vị trí hoặc theo tên.

35 video MIT001 đã có [paired diagnostic visual/acoustic/full](../../multimodal-lecture-summarizer/plans/reports/rq1-mit001-multimodal-260928-0909-paired-diagnostic-report.md), nhưng thuộc một khóa và nhãn đã từng được nhìn thấy; không được biến thành final test độc lập. Nguồn mới cần qua quyền, GT, split và D2 rồi mới chạy official RQ1. Thay dataset, split, GT hoặc claim phải sửa [master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) trước khi đóng băng.

## Quyết định nghiên cứu hiện tại

1. Giữ YTSeg ở trạng thái **metadata license verified, media access/GT/split chưa đạt**. Không dùng `yt-dlp` cho official visual/full từ chứng cứ hiện có.
2. Ưu tiên pilot MITFLD từ nhóm `lecture_video_candidate_course`: loại trước 65 hàng thuộc khóa “Lecture Audio”, rà 5 Problem Sessions, lấy mẫu nhiều khóa qua đường OCW công bố, kiểm credit/quyền từng file, giải mã duration và so khớp GT. Ghi riêng quyền media OCW, quyền MP4/GT Hugging Face và quyền tái phân phối.
3. Chỉ tạo train/validation/final test course-disjoint sau khi đủ hàng qua tất cả gate. Mẫu 10 hiện có 9 khóa, trong đó 1 Problem Session; 538/25 là **trần metadata**, không phải số cohort đủ điều kiện.
4. Chưa gửi email cho tác giả MITFLD. Cần hỏi về nguồn nhãn `frags`, cách gán nhãn, giấy phép GT/transcript/MP4, bảng `video_id` sang khóa và độ khớp với bản OCW. Các câu trả lời này quyết định có thể dùng MITFLD làm GT chính hay phải gán nhãn độc lập.

## Câu hỏi chưa giải quyết

- Từng file OCW/Archive được chọn có credit/ngoại lệ bên thứ ba nào, và điều kiện dùng cho nghiên cứu phi thương mại, lưu cục bộ, công bố aggregate ra sao?
- Thời lượng và nội dung của MP4 OCW có khớp các mốc `frags` MITFLD sau chuẩn hóa không; nếu lệch, quy tắc căn chỉnh có thể đóng băng trước test không?
- Ai tạo GT MITFLD, chất lượng/giấy phép của GT là gì; có thể dùng làm chapter GT độc lập cho RQ1 không?
- Sau lọc lecture, visual usefulness, quyền, media và GT, còn bao nhiêu video từ bao nhiêu khóa để split và ước lượng bất định ở cấp khóa?
- Có đường MP4 YTSeg phù hợp điều khoản nền tảng và quyền của từng video hay không; nếu không, có cần sửa protocol chính thức sang nguồn khác?
