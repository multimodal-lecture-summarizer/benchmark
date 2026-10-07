# RQ1 YTSeg: rà lại một lần cổng quyền theo giấy phép hoặc Điều 37a

> **Lưu vết:** Các câu “chưa đổi manifest” bên dưới đúng tại thời điểm 17:58. [Quyết định qualification 18:11](./rights-decision-260929-1811-ytseg-scoped-research-report.md) đã ghi 2 `pass`, 8 `hold` trong [manifest mới](./ytseg-qualification-260929-1811-scoped-research-gate-decision.csv); D2 vẫn chưa khóa.

**Ngày:** 2026-09-29. **Cohort:** đúng 10 ID TRAIN đã qua GT/media. **Trạng thái:** khuyến nghị sửa tiêu chí và tái phân loại; [manifest quyết định cũ](./ytseg-qualification-260929-1659-gate-decision.csv) **chưa đổi**; không phải D2 hoặc kết quả official. [Ledger rà lại từng ID](./rights-review-260929-1758-ytseg-three-basis-ledger.csv) là bản máy đọc. Chỉ dùng chứng cứ đã ghi; không tải hay kiểm lại media.

## Tiêu chí sửa trong protocol dự thảo

[Protocol dự thảo](../260929-1659-rq1-ytseg-evaluation-protocol/rq1-ytseg-evaluation-protocol-draft.md) nay chấp nhận **giấy phép công khai đúng phạm vi** hoặc **ngoại lệ pháp luật áp dụng đúng thao tác**. Không lấy việc chưa hỏi publisher/pháp lý làm điều kiện giữ `hold`. Cũng không giữ chỉ vì giấy phép không viết riêng chữ “AI” hay vì trong bài có tài sản bên thứ ba mà chưa gắn được với MP4. Một `hold` phải có câu hỏi chứng cứ cụ thể có thể trả lời, hoặc dừng mẫu nếu không đáng chi phí giải quyết.

Phạm vi dùng: nghiên cứu phi thương mại trong môi trường hạn chế truy cập, ASR, trích frame/cảnh, OCR, embedding, huấn luyện và đánh giá theo split. Công bố mã nguồn của nhóm, cấu hình, ID, checksum và số liệu; **đợt này không phát hành** MP4, frame, clip, transcript nguồn. Đây là ranh giới thao tác, không phải suy đoán rằng CC cấm phát hành. Giấy phép MIT hiện cho phép AI training với nội dung OCW **thuộc phạm vi** kèm attribution, NC và ShareAlike; [MIT FAQ](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content) phân biệt tài sản bên thứ ba được phép kèm credit với nội dung “all rights reserved” ngoài CC. [Điều khoản MIT](https://ocw.mit.edu/pages/privacy-and-terms-of-use/).

## Nhóm 1 — giấy phép công khai đủ cơ sở cho phạm vi nghiên cứu: 2 video, 2 nhóm

| ID | Căn cứ gắn đúng resource | Kết luận rà lại |
| --- | --- | --- |
| `-7xg8pGcP6w` | [Giấy phép CS50P](https://cs50.harvard.edu/python/license/) CC BY-NC-SA 4.0 cho khóa; [Week 2](https://cs50.harvard.edu/python/weeks/2/) liên kết MP4 bài đúng ID trong receipt. Credit Harvard CS50/David J. Malan, URL và license; dùng nghiên cứu phi thương mại. | **Khuyến nghị `pass_rights_scoped_research`**. Không có ngoại lệ thành phần cụ thể được chỉ ra trong trang đã kiểm. Việc chưa hỏi Harvard hoặc giấy phép không viết “AI” không phải lý do `hold`. Nếu xuất hiện notice trái trong đúng file, xét lại đúng thành phần. |
| `tCKk22kaZi4` | [Item Archive do MIT-OCW đăng](https://archive.org/details/MIT14.01F18) liệt kê Lecture 2 và CC BY-NC-SA 4.0; [MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) có điều khoản AI cho nội dung được bao phủ. Credit MIT OCW/Jonathan Gruber và license. DSpace ZIP không có A/V nên không tạo xung đột giấy phép đã chứng minh cho MP4. | **Khuyến nghị `pass_rights_scoped_research`** theo nguồn hiện có. Không giữ chỉ vì chưa làm kiểm kê mọi pixel/credits hoặc chưa gửi thư; notice ngoại lệ cụ thể nếu có sẽ xét riêng. |

Hai video thuộc **hai** `course_id`/nhóm giảng viên khác nhau. Đây là khuyến nghị cổng quyền sau thay tiêu chí, **không** là N/G của manifest chính thức và chưa đủ để đóng D2.

## Nhóm 2 — ngoại lệ Điều 37a cần xét đúng nội dung: 1 video

`xsO2Ip6eiaY`: clip máy bay ngoài slide xuất hiện **240 s**, trang/ảnh sản phẩm SeaRey **1260 s** trong MP4 đã kiểm. Phần OCW thuộc phạm vi vẫn có giấy phép MIT; đối với hai thành phần quan sát được, không suy giấy phép của ảnh Public Domain trong PDF sang clip/webpage. Có thể xét [khoản 5 Điều 7 Luật SHTT và Điều 37a Nghị định 17/2023 sau sửa đổi bởi Nghị định 134/2026/NĐ-CP](https://vanban.chinhphu.vn/?classid=1&docid=217833&orggroupid=2&pageid=27160) cho hoạt động nghiên cứu tại Việt Nam, thay vì mặc định phải xin phép.

| Điều kiện Điều 37a | Chứng cứ hiện có / giới hạn |
| --- | --- |
| Công bố hợp pháp; tiếp cận bằng hành vi và nguồn hợp pháp | MP4 tải từ liên kết publisher tới Archive theo receipt. Nguồn gốc **clip gốc** ở 240 s chưa rõ; bản ghi việc MIT công bố không tự chứng minh nguồn clip đã được công bố hợp pháp. Trang SeaRey là website đã được quay lại, nhưng quyền ảnh cụ thể chưa được ghi. |
| Không vô hiệu biện pháp công nghệ bảo vệ | Receipt tải HTTP/giải mã bình thường, chưa ghi hành vi vượt DRM; cần lưu xác nhận phương pháp không vượt biện pháp bảo vệ. |
| Chỉ nghiên cứu/thử nghiệm/huấn luyện phi thương mại | Protocol dự thảo đã định mục đích. Cần áp dụng hạn chế truy cập thực tế và ghi địa điểm xử lý để xác định ngoại lệ Việt Nam có áp dụng. |
| Không mâu thuẫn khai thác bình thường; không gây thiệt hại bất hợp lý | Trích đặc trưng nội bộ và không phát hành nguồn giảm tác động. Chưa có đánh giá riêng về thị trường của **clip gốc** hoặc ảnh/site SeaRey, nhất là nếu đặc trưng/checkpoint có thể tái tạo nội dung. |
| Đầu ra không thay thế thị trường/không cạnh tranh không lành mạnh | Chỉ công bố mã/cấu hình/ID/hash/metric; không công bố clip, frame, transcript. Cần duy trì kiểm soát đầu ra và lưu hồ sơ nguồn/dữ liệu sử dụng theo Điều 37c. |

**Quyết định rà lại:** tiếp tục `hold` **riêng** vì nguồn/công bố hợp pháp của clip, khả năng áp dụng ngoại lệ theo nơi xử lý và đánh giá tác động clip/website chưa xác lập; không phải vì chưa gửi thư. Có thể chọn mẫu thay thế thay vì theo đuổi clearance vô thời hạn. [Công báo Nghị định 134/2026](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-134-2026-nd-cp-469388/64378.htm) ghi hiệu lực 09/04/2026; [Báo Chính phủ trích các điều 37a–37c](https://baochinhphu.vn/dieu-kien-de-tac-pham-do-ai-ho-tro-tao-ra-duoc-phap-luat-bao-ho-quyen-tac-gia-102260415163902936.htm).

## Nhóm 3 — chưa đủ căn cứ cho toàn MP4: 7 video

`-dOX_4lI6HY`, `3sB64Au76h0`, `Th2N_rDfkDw`, `alLh1Jdqwvg`, `ksyY5wa5_50`, `kiCNa95DnnE`, `MoEaRpLNo9A` đều có **giấy phép MIT cho phần được bao phủ** và nguồn publisher. Từng PDF bài tương ứng **nêu tài sản cụ thể bị loại khỏi CC**, nhưng ledger cũ chưa chứng minh chính tài sản đó có trong MP4. Riêng `alLh1Jdqwvg`, frame khoảng 50% có ATIS; chưa xác minh đó là đối tượng bị loại trong PDF. Không dùng PDF để tuyên bố cả MP4 ngoài giấy phép.

Điều kiện còn thiếu được ghi theo từng ID ở [CSV](./rights-review-260929-1758-ytseg-three-basis-ledger.csv): **tài sản được nêu trên PDF có hiện trong MP4 không; nếu có, căn cứ Điều 37a cho sao chép nội bộ/trích frame/OCR/embedding/huấn luyện với tài sản đó đã đáp ứng chưa?** Theo chứng cứ hiện tại, chưa nâng bảy ID vào cohort chính thức; giữ GT/media `pass`. Không cần mở lại audit GT/media. Nếu chi phí định vị/đánh giá quyền vượt lợi ích, chọn nguồn thay thế theo cohort rules; không giữ quy trình liên hệ mở vô hạn. Dòng `hold` cũ “thiếu publisher/legal confirmation” và “không nói rõ AI” được loại khỏi lý do quyết định.

## Kết quả và giới hạn

| Phân loại rà lại | Video | Nhóm độc lập theo `course_id`/giảng viên | Có đổi manifest? |
| --- | ---: | ---: | --- |
| Khuyến nghị đủ giấy phép cho phạm vi nghiên cứu | 2 | 2 | Chưa |
| Điều 37a cho ngoại lệ cụ thể còn điều kiện chưa xác lập | 1 | 1 khóa MIT 16.687 | Chưa |
| Thiếu chứng cứ ghép ngoại lệ PDF với MP4, hoặc căn cứ thay thế nếu có | 7 | 2 khóa MIT (6 cùng MIT 16.687, 1 MIT 6.S897) | Chưa |

**Manifest hiện tại:** 10 GT/media `pass`, 10 quyền `hold`, **N=0/G=0 chính thức** cho đến khi ghi amendment và cập nhật manifest từ quyết định đã kiểm. Theo rà lại, **2 video/2 nhóm là ứng viên quyền `pass`** dưới tiêu chí mới; số này chưa đủ tự nó xác nhận thiết kế thống kê hoặc khóa split/D2. Không chọn mô hình hay chạy official RQ1. Không xem ID giao với VidChapters là đơn vị độc lập thứ hai.

## Câu hỏi chưa giải quyết

1. Có áp dụng Điều 37a tại địa điểm xử lý thực tế không, và có đủ chứng cứ cho clip 240 s/trang 1260 s của `xsO2Ip6eiaY` về nguồn hợp pháp và ảnh hưởng thị trường không?
2. Với bảy video có ngoại lệ PDF, có bằng chứng đã có trong publisher/credits giúp xác định nó xuất hiện trong MP4, hay nên thay mẫu ngay theo quy tắc khóa cohort?
3. Sau khi chấp nhận hoặc bác bỏ khuyến nghị hai video nhóm 1 và chọn mẫu thay thế, N/G có đủ để hoàn tất split và xét D2 không?
