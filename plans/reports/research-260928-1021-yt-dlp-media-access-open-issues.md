# Nghiên cứu: yt-dlp và các cổng còn mở của YTSeg/MITFLD

Kiểm tra: 2026-09-28 10:21 (Asia/Bangkok). Phạm vi: 14 ID YTSeg đã xác minh metadata bằng API, subset YTSeg CC BY 276 video, mẫu MITFLD 10 ID. Phân tích tài liệu hiện hành; không tải, phát, giải mã video hoặc kiểm tra khả năng chạy `yt-dlp` trên một ID cụ thể. Đây là đánh giá vận hành và nguồn quyền, không phải ý kiến pháp lý.

## Kết luận ngắn

**Về kỹ thuật, `yt-dlp` là công cụ tải video và có extractor YouTube. Nhưng không chọn `yt-dlp` làm đường lấy MP4 YTSeg cho benchmark tại thời điểm này.** [README chính thức của yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/README.md) mô tả chức năng tải; [wiki extractor](https://github.com/yt-dlp/yt-dlp/wiki/extractors) ghi một số định dạng/tính năng YouTube có thể cần PO Token và việc dùng cookie tài khoản có rủi ro. Khả năng tải thực tế thay đổi theo video và thời điểm.

[YouTube Terms](https://www.youtube.com/t/terms) giới hạn tải nội dung trừ khi dịch vụ cho phép hoặc có phép bằng văn bản từ YouTube và chủ thể quyền liên quan; đồng thời giới hạn truy cập bằng phương tiện tự động. Với ứng dụng dùng YouTube API, [Developer Policies](https://developers.google.com/youtube/terms/developer-policies) nêu riêng rằng API client không được tải/lưu bản sao audiovisual nếu chưa có chấp thuận trước bằng văn bản của YouTube. API key đã dùng để **đọc metadata** không cấp quyền tải MP4. Không sử dụng cookie, PO Token hay cấu hình extractor như cách thay thế cổng quyền.

**Nhãn CC BY vẫn có ý nghĩa**: YouTube [giải thích](https://support.google.com/youtube/answer/2797468?hl=en) người đăng có thể chọn Creative Commons Attribution để cho phép tái sử dụng tác phẩm của họ. Nhưng [Creative Commons FAQ](https://creativecommons.org/faq/) nói rõ giấy phép tác phẩm và điều khoản của nơi phân phối là hai lớp khác nhau; tải từ một site cấm tải có thể vi phạm điều khoản site dù không vi phạm CC. CC cũng không bảo đảm người cấp phép sở hữu mọi yếu tố bên thứ ba. Đây là lý do 14/14 ID có `creativeCommon`, `public`, `embeddable=true` qua API vẫn **chưa đủ** để chuyển sang `rights_cleared` cho tải bằng `yt-dlp`.

## Lựa chọn media cho benchmark

| Nguồn | Bằng chứng hiện có | Quyết định hiện tại |
|---|---|---|
| YTSeg YouTube MP4 qua `yt-dlp` | 14/14 ID mẫu còn public, CC và embeddable qua API; [YTSeg card](https://huggingface.co/datasets/retkowski/ytseg-cc-by) chỉ phát hành audio/text/titles, không phát hành MP4. | **Chưa dùng để tải MP4.** Cần một đường truy cập được YouTube cho phép, hoặc bản sao trực tiếp từ chủ thể có quyền kèm phạm vi cấp phép phù hợp. |
| YTSeg audio trên Hugging Face | [Subset card](https://huggingface.co/datasets/retkowski/ytseg-cc-by) phát hành `audio` 16 kHz mono, `text`, `titles` với giấy phép gói CC BY 4.0; 276 video, 14 kênh, train-only. Card nói video gốc YouTube là CC BY 3.0. | Có thể đánh giá **nhánh acoustic** từ tệp audio do dataset phát hành sau kiểm tra điều khoản gói, provenance và đơn vị/GT; không suy ra quyền visual MP4 hay test độc lập. |
| MITFLD MP4 trên Hugging Face | [Dataset card](https://huggingface.co/datasets/robotwang/MITFLD) và [repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation) chỉ dẫn tải dataset, nhưng không công bố giấy phép riêng rõ ràng cho MP4/transcript/`frags` trong các nguồn đã kiểm. 10/10 ID mẫu ánh xạ đúng trang OCW. | Chưa coi bản phát hành thứ cấp là `rights_cleared`. Hỏi tác giả về quyền MP4 và GT; đồng thời tìm đường tải chính thức ở từng trang MIT OCW. |
| MIT OCW direct | [Trang OCW](https://ocw.mit.edu/pages/get-started/) khuyến khích tải/lưu tài liệu; một số [trang download khóa](https://ocw.mit.edu/courses/6-100l-introduction-to-cs-and-programming-using-python-fall-2022/download/) có liên kết video trực tiếp. [Điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) nêu CC BY-NC-SA 4.0 và ngoại lệ theo quyền thành phần. | Ứng viên đường lấy hợp lệ hơn cho **video OCW cụ thể** nếu chính trang nguồn cung cấp link tải, điều kiện và credits của video đã kiểm. Chưa xác minh link tải tương ứng cho cả 10 ID mẫu hay đủ 538 ID. |

## Các vấn đề còn mở được làm rõ đến đâu

1. **YTSeg quyền/tải:** đã phân biệt ba lớp: giấy phép video, giấy phép gói dataset, điều khoản phương thức truy cập. Metadata API mới giải quyết phần đầu ở 14 ID. Hướng khả thi cho visual là lấy bản video từ nguồn có link tải được phép hoặc thỏa thuận trực tiếp; `yt-dlp` không tự giải quyết quyền. Audio-only có nguồn tệp trong subset nhưng không đáp ứng visual/full.
2. **YTSeg split/GT:** subset chỉ có train, 14 kênh lệch mạnh, không có `course_id`; chapter timestamps là nhãn biên tập của nguồn. Không có sẵn validation/test độc lập. Cần lập group nguồn/khóa học và xác minh GT trước khi đề xuất custom split, rồi sửa master protocol trước khi dùng làm official RQ1. [Card subset](https://huggingface.co/datasets/retkowski/ytseg-cc-by) xác nhận train-only và cấu trúc gói.
3. **MITFLD quyền/GT:** MIT OCW cấp CC BY-NC-SA 4.0 cho tài liệu thuộc phạm vi giấy phép; [điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) có mục riêng về AI training. Bản phát hành MITFLD và mốc `frags` chưa có chứng cứ giấy phép/provenance cụ thể. HTTP 200 và ánh xạ trang không chứng minh quyền hay GT đúng video.
4. **MITFLD split:** 10 ID mẫu cho 9 khóa, trong đó một Problem Session; sau loại mục đó là 9 lecture-like từ 8 khóa. Đây là dấu hiệu có thể group theo khóa; chưa biết số khóa đủ điều kiện trong toàn bộ 538 sau lọc quyền, loại bài và GT. Xem [báo cáo mẫu trước](./research-260928-1006-mitfld-rights-course-map-ytseg-api-report.md).

## Hành động kế tiếp

1. Giữ YTSeg visual/full ở `blocked_access` hoặc `blocked_rights` cho tới khi ghi được đường lấy MP4 được phép cùng quyền từng video; không chạy `yt-dlp` hàng loạt từ kết quả API metadata.
2. Nếu cần pilot sớm, dùng YTSeg **audio** được phát hành trong gói cho nhánh acoustic, hoặc một video **OCW có link tải trực tiếp đã xác minh** cho visual; ghi rõ đây là diagnostic, chưa là official RQ1.
3. Hỏi tác giả MITFLD về phạm vi cấp phép MP4/transcript/`frags`, người tạo GT và quy ước timestamp. Với 10 video mẫu, kiểm tra credits/ngoại lệ từng trang OCW và direct download link trước khi tải.
4. Sau khi có media hợp lệ, kiểm tra decoded duration, đối chiếu GT, mở rộng course map và thiết kế group-disjoint split. Không dùng 35 video MIT001 đã lộ nhãn làm final test mới.

## Câu hỏi chưa giải quyết

Nghiên cứu tiếp theo đã giải quyết một phần câu hỏi OCW: [10/10 trang mẫu có link MP4 do OCW công bố, đều `HEAD 200`](./research-260928-1023-mitfld-direct-media-gt-split-report.md). Tám link sang Archive.org còn cần kiểm tra điều khoản item-level; quyền và provenance `frags` vẫn mở.

- YouTube hoặc chủ thể quyền có cấp đường lấy MP4 ngoài player cho các ID YTSeg dự kiến hay không; video nào có thành phần bên thứ ba cần loại?
- Credits/quyền cụ thể của từng MP4 OCW-linked, nhất là tám item Archive.org, là gì; bản MP4 MITFLD có cùng nội dung và thời lượng với bản nguồn không?
- Tác giả MITFLD xác nhận giấy phép và provenance của `frags` thế nào; số khóa đủ điều kiện trên toàn bộ 538 là bao nhiêu?
