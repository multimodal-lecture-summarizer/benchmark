# YTSeg RQ1: hồ sơ quyết định quyền theo video và thao tác

> **Lưu vết lịch sử:** Hồ sơ này phản ánh tiêu chí cũ yêu cầu chuẩn bị hỏi pháp lý/publisher. [Lần rà lại theo giấy phép công khai hoặc Điều 37a](./rights-review-260929-1758-ytseg-three-basis-report.md) là tiêu chí dự thảo hiện hành: không bắt buộc thư xác nhận, không lấy quyền phát hành media làm cổng ở đợt RQ1 này. Các số `hold` bên dưới chỉ là snapshot của manifest trước khi điều chỉnh, không phải kết luận sau rà lại.

**Ngày:** 2026-09-29. **Trạng thái:** bản chuẩn bị để bộ phận pháp lý của trường và publisher xem xét; chưa gửi ra ngoài, chưa có ý kiến pháp lý, chưa khóa D2. **Phạm vi:** đúng 10 video YTSeg TRAIN đã kiểm GT và media. Ledger 10 hàng: [CSV thành phần/thao tác](./ytseg-rights-260929-component-operation-ledger.csv). Không mở thêm media hoặc rà kỹ thuật lại.

## Quyết định hiện thời

GT `target_ts` và full-file media vẫn `pass` kỹ thuật **10/10**. Bằng chứng giấy phép publisher cho nội dung thuộc phạm vi CC là tích cực, nhưng chưa có quyết định đầy đủ cho các thành phần và thao tác cụ thể. Vì vậy `pass` **quyền sử dụng toàn video cho protocol hiện tại = 0/10**, `hold = 10/10`, `exclude = 0/10`; số nhóm độc lập qua **toàn bộ** cổng hiện là **N=0, G=0**. Mười video trải trên bốn nhóm khóa/giảng viên tiềm năng; chưa được gán split final. `hold` ở đây là **chưa đủ căn cứ quyết định**, không phải kết luận toàn bộ MP4 bị cấm nghiên cứu. Không cộng quyền phát hành lại vào cổng quyền xử lý nội bộ.

[MIT OCW giải thích](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content) rằng nội dung bên thứ ba ghi “Courtesy of … Used with permission” có thể thuộc phạm vi CC kèm credit riêng, còn nội dung ghi “All rights reserved” không nằm trong giấy phép CC của OCW. [FAQ tái sử dụng](https://mitocw.zendesk.com/hc/en-us/articles/4414756158107-What-if-I-want-to-download-copy-modify-reuse-remix-or-redistribute-materials-that-include-all-rights-reserved-content) yêu cầu căn cứ riêng như phép của chủ quyền hoặc đánh giá ngoại lệ phù hợp bối cảnh; mục đích nghiên cứu không tự xác nhận quyền. [Điều khoản MIT hiện hành](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) cho phép AI training trên nội dung OCW **thuộc phạm vi** và có điều kiện attribution, phi thương mại, ShareAlike. MP4 MIT 16.687 có notice 3.0, còn trang MIT/Archive hiện hiển thị 4.0; cần publisher xác nhận cách áp dụng cho đúng file và ngày sử dụng.

## Thao tác đề nghị đánh giá

Thiết kế kỹ thuật đã nêu trong [protocol dự thảo](../260929-1659-rq1-ytseg-evaluation-protocol/rq1-ytseg-evaluation-protocol-draft.md): endpoint mốc bắt đầu chapter nội bộ; F1 ±3 giây primary; không chấm tiêu đề; không chạy official RQ1 trước D2. Yêu cầu quyền phải xét **từng thao tác** sau, trên file nguồn tải từ publisher và thành phần nêu trong ledger:

| Thao tác dự kiến | Dữ liệu tiếp xúc / bản sao sinh ra | Phạm vi đầu ra dự kiến | Câu hỏi quyền |
| --- | --- | --- | --- |
| Tải và lưu MP4 để nghiên cứu cục bộ | Bản sao đầy đủ trên máy/ổ nghiên cứu; đã có bản kiểm kỹ thuật | Không chia sẻ file | Căn cứ lưu và dùng bản sao chứa thành phần ngoài CC? |
| Giải mã tiếng nói, ASR | Audio và transcript có timestamp cục bộ | Chỉ đặc trưng/metric tổng hợp, không phát hành transcript đầy đủ | Phạm vi quyền audio/giọng nói, kể cả khi slide hình ảnh bị loại trừ? |
| Giải mã hình, trích frame/cảnh và OCR | Frame tạm, chữ OCR từ slide/webpage, có thể chứa tài sản bên thứ ba | Không phát hành frame, clip hoặc OCR nguyên văn | Thành phần cụ thể nào bị loại khỏi CC; sao chép tạm và OCR trên phần đó có căn cứ nào? |
| Tính embedding âm thanh/hình và huấn luyện/đánh giá trên split hợp lệ | Vector đặc trưng, checkpoint nội bộ, log/provenance | Chỉ ID, hash, protocol, metric tổng hợp; không phát hành checkpoint ở giai đoạn này | Quyền xử lý/huấn luyện đối với phần ngoài CC; nghĩa vụ attribution/ShareAlike và lưu giữ đặc trưng/checkpoint? |
| Công bố báo cáo | ID, URL, SHA-256 và số liệu tổng hợp | Không MP4, đoạn video, frame, SRT, transcript đầy đủ hoặc model | Có giới hạn nào đối với metadata/trích dẫn ngắn và bảng kết quả? |

Đây là **phạm vi đề xuất cho quyết định pháp lý**, không là khẳng định mọi thao tác đã được cho phép. Nếu sau này muốn phát hành checkpoint, embedding theo video, transcript hay media, phải có quyết định riêng và cập nhật protocol trước khi dùng.

## Ngoại lệ cần xem theo từng video

- `-dOX_4lI6HY`, `3sB64Au76h0`, `Th2N_rDfkDw`, `ksyY5wa5_50`, `kiCNa95DnnE`: PDF bài tương ứng loại trừ các hình/tài sản được gọi tên trong CSV. Receipt MP4 chỉ có các mẫu tại 10/50/90%; **chưa chứng minh hình bị loại trừ chính là frame đã quan sát**. Vị trí MP4 của phần bị loại trừ hiện `unknown`, cần publisher chỉ rõ hoặc pháp lý quyết định theo giới hạn bằng chứng; không gán ngoại lệ PDF cho toàn MP4.
- `alLh1Jdqwvg`: tại khoảng 50% thời lượng MP4 thấy ATIS excerpt và một URL YouTube. PDF loại trừ một số tài sản không rõ nguồn, gồm slide ví dụ/ATIS, nhưng chưa đối chiếu chính xác đối tượng trên frame. URL không chứng minh clip đã phát trong MP4.
- `xsO2Ip6eiaY`: **đã thấy trực tiếp** clip máy bay trong MP4 khoảng 240 s và ảnh/trang sản phẩm SeaRey khoảng 1260 s. PDF đánh dấu một số hình khác Public Domain; không tự áp cho clip và website. Đây là yêu cầu cụ thể nhất để hỏi MIT về nguồn, credit, permission và phạm vi reuse.
- `MoEaRpLNo9A`: PDF MIT 6.S897 loại trừ hình/logo AHA, Mayo và nguồn khác ở các trang ghi trong CSV; vị trí tương ứng trong MP4 **chưa biết**. Cần quyết định quyền với visual processing nếu các thành phần xuất hiện, không gọi mọi đoạn video là ngoài CC.
- `-7xg8pGcP6w`, `tCKk22kaZi4`: chưa xác định ngoại lệ thành phần cụ thể trong bằng chứng đã đọc. Giấy phép publisher có cơ sở cho nội dung nằm trong phạm vi; `hold` là thiếu diễn giải phạm vi exact MP4/hoạt động, không phải phát hiện hình bị cấm. Với MIT 14.01, license của DSpace ZIP không bao gồm A/V nên không phải xung đột license đã chứng minh cho MP4.

## Bản nháp gửi pháp lý của trường

**Tiêu đề:** Đánh giá căn cứ sử dụng 10 video bài giảng trong nghiên cứu phân chương đa phương thức

> Nhóm nghiên cứu xin ý kiến về 10 MP4 trong CSV đính kèm, mỗi file gắn publisher URL, khóa/giảng viên, bằng chứng giấy phép và ngoại lệ thành phần. Mục đích là nghiên cứu phi thương mại, lưu file cục bộ, ASR, OCR/frame, embedding, huấn luyện/đánh giá theo split; dự kiến chỉ công bố ID, hash, protocol và metric tổng hợp. Chúng tôi chưa định phát hành media, transcript hay checkpoint. GT và media đã đạt cổng kỹ thuật, nhưng quyền toàn video vẫn hold.
>
> Xin đánh giá riêng: (1) căn cứ cho thao tác audio-only so với visual/full-video; (2) từng thành phần `direct_MP4_sample` và `PDF_exclusion_unmapped` trong ledger, bao gồm liệu cần định vị thêm trong MP4 trước quyết định; (3) nếu CC không bao phủ, có căn cứ ngoại lệ theo bối cảnh/địa bàn nghiên cứu hoặc cần xin phép chủ quyền; (4) nghĩa vụ attribution, NC, ShareAlike, lưu giữ và checkpoint; (5) có thể ghi `pass` cho video nào, giới hạn modality nào, và bằng chứng quyết định cần lưu. Xin ghi kết luận theo từng `video_id` và thao tác, không kết luận gộp toàn khóa.

## Bản nháp câu hỏi publisher (chỉ dùng sau khi rà soát nội bộ)

**MIT OCW:** Với MP4 gốc của `MIT16.687IAP19` Lectures 7/10/12/13/16/19/21, `MIT6.S897S19` Lecture 10 và `MIT14.01F18` Lecture 2 (URLs và ID trong ledger): (1) các tài sản “Courtesy of … Used with permission” và “All rights reserved” trong PDF có xuất hiện ở chính MP4 không; nếu có, ở đoạn/slide nào và credit/phạm vi phép của chúng là gì; (2) clip khoảng 240 s và trang SeaRey khoảng 1260 s của Lecture 16 có nguồn và permission nào; (3) giấy phép nào điều chỉnh MP4 16.687 mang metadata 3.0 khi website/Archive hiện ghi 4.0; (4) phạm vi OCW có bao gồm tải/lưu cục bộ, ASR, trích frame/OCR, embedding và huấn luyện phi thương mại trên **những thành phần được bao phủ** không; với phần ngoài CC, MIT có thể cấp quyền tiếp hay chỉ chủ quyền gốc có thể? Chúng tôi không dự kiến phát hành lại media/transcript/model.

**Harvard CS50P:** Với Week 2 Lecture `-7xg8pGcP6w`, giấy phép course CC BY-NC-SA 4.0 có bao phủ chính MP4, audio/slide/credits cho các thao tác cục bộ nêu trên không; có thành phần bị loại trừ hoặc nghĩa vụ attribution riêng nào? Không suy sự vắng mặt của carve-out trên trang Week 2 là clearance toàn file.

Publisher có thể chỉ rõ nguồn/điều khoản; đánh giá ngoại lệ theo bối cảnh và quyết định nội bộ vẫn cần bộ phận pháp lý của trường. Bản nháp này **chưa được gửi**.

## Cách ghi quyết định sau phản hồi

Lưu ngày, người/cơ quan trả lời, văn bản/URL, đúng `video_id` và thao tác được chấp nhận; phân biệt `covered_CC`, `courtesy_permission_with_credit`, `all_rights_reserved_separate_basis`, `public_domain_verified`, `unmapped/unknown`. Chỉ nâng `pass` khi phạm vi đầy đủ của protocol hiện tại được giải quyết; nếu giới hạn chỉ audio thì vẫn `hold` cho RQ1 đa phương thức toàn file. Mẫu không giải quyết được giữ `hold`; chọn mẫu thay thế theo quy tắc đã chốt, rồi mới đếm N/G, nối nhóm chung khóa **hoặc** giảng viên, khóa split và xét D2. Không dùng phản hồi quyền để sửa GT/media.

## Câu hỏi chưa giải quyết

1. Pháp lý của trường chấp nhận căn cứ nào cho từng thao tác và từng thành phần đã thấy trực tiếp; mức bằng chứng nào đủ với các ngoại lệ PDF chưa map MP4?
2. MIT/Harvard xác nhận phạm vi giấy phép, permission bên thứ ba và notice 3.0/4.0 của đúng MP4 thế nào?
3. Sau quyết định quyền theo video, còn bao nhiêu N/G và có cần mở rộng VidChapters để đạt thiết kế đánh giá?
