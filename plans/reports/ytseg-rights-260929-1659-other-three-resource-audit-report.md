# YTSeg: quyền của ba resource ngoài MIT 16.687

Kiểm ngày 2026-09-29 (Asia/Bangkok). Phạm vi: `MoEaRpLNo9A`, `-7xg8pGcP6w`, `tCKk22kaZi4`; đúng file đã tải và kiểm kỹ thuật trong các receipt [MIT 6.S897](./ytseg-260929-1543-moea-media-receipt.json), [CS50P](./ytseg-260929-1543-cs50-media-receipt.json), [MIT 14.01](./ytseg-260929-1543-tck-media-receipt.json). Không thay manifest, split, GT hoặc D2. Đây là đánh giá bằng chứng quyền theo phạm vi dự kiến, không phải ý kiến pháp lý.

## Kết luận và ưu tiên

| Ưu tiên | ID; nguồn | Xử lý nghiên cứu tại chỗ | Phát hành lại file/đoạn/frame | Lý do cổng còn `hold` |
| --- | --- | --- | --- | --- |
| 1 | `-7xg8pGcP6w`; Harvard CS50P | **Có cơ sở cấp phép trực tiếp** cho sử dụng phi thương mại kèm attribution và ShareAlike; đề xuất `pass_rights_research_conditional` sau khi protocol xác nhận phạm vi nghiên cứu phi thương mại | Chưa nâng `pass`: phải kiểm ngoại lệ/credits của chính file và hình, âm thanh trích ngoài | Chưa kiểm xuyên suốt thành phần media; giấy phép khóa không chứng minh tác giả sở hữu từng yếu tố bên thứ ba |
| 2 | `tCKk22kaZi4`; MIT 14.01 | **Có cơ sở cấp phép trực tiếp hơn đánh giá cũ**: Archive item do MIT-OCW tải lên ghi CC BY-NC-SA 4.0 và liệt kê đúng Lecture 2; áp dụng quy tắc OCW cho nội dung nằm trong phạm vi | `hold` với bản sao video, frame, clip; chưa kiểm ngoại lệ từng thành phần | Chưa audit toàn file theo quyền thành phần; trang OCW 2018 không còn mở trực tiếp; xác minh chain of custody dựa transcript OCW + Archive item và hash receipt |
| 3 | `MoEaRpLNo9A`; MIT 6.S897 | MIT OCW có giấy phép chung và điều khoản AI cho phần nội dung **thuộc** OCW, nhưng slide chính thức loại nhiều ảnh/logo bên thứ ba khỏi CC. `hold_component_scope` cho xử lý visual/full video | `hold` rõ ràng đối với bản sao/clip chứa các hình bị loại | Cần đối chiếu vị trí các thành phần loại trừ trong MP4 và phạm vi xử lý dự kiến; không suy giấy phép của slide sang mọi pixel video |

**Không gộp quyền phát hành lại với quyền xử lý nghiên cứu.** Cả ba có đường tải hợp pháp từ chính trang publisher hoặc uploader publisher, nhưng khả năng tải không tự nó xác nhận mọi quyền downstream. Theo [điều khoản MIT OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), nội dung trong phạm vi giấy phép CC BY-NC-SA 4.0 được chia sẻ/chuyển thể phi thương mại với attribution và ShareAlike; mục AI training cho phép train/develop/improve nếu không có ngoại lệ và giữ các nghĩa vụ. Điều khoản cũng nói có thể còn quyền khác. Đây là bằng chứng cấp phép tốt cho **phần nội dung MIT kiểm soát**, chưa giải quyết thành phần bên thứ ba. [Trang MIT về fair use](https://ocw.mit.edu/help/faq-fair-use/) được chính slide liên kết; sự hiện diện của nội dung được phép MIT trưng bày theo ngoại lệ không tương đương cấp license downstream cho người nghiên cứu.

## Đối chiếu từng resource

### Harvard CS50P Week 2 — `-7xg8pGcP6w`

[Trang Week 2 chính thức](https://cs50.harvard.edu/python/weeks/2/) có link tải 360p, phụ đề, transcript và YouTube; receipt đã kiểm file 963,059,289 byte và mốc lời nói. [Trang license chính thức](https://cs50.harvard.edu/python/license/) ghi **course** CC BY-NC-SA 4.0, cho copy/share/adapt nếu attribution, phi thương mại, ShareAlike. Trong trang bài và license đã đọc, không thấy ngoại lệ riêng cho lecture 2; đây là *không thấy*, không phải bằng chứng không có ngoại lệ trong MP4. Chưa rà toàn file hoặc credits cuối bài để phân loại hình/âm thanh ngoài CS50. Chỉ có thể đề xuất `pass_rights_research_conditional` khi protocol chốt nghiên cứu không thương mại và nghĩa vụ attribution/SA; giữ `hold_redistribution_component_audit` cho media/clip/frame. Không cần liên hệ tác giả để kết luận mức bằng chứng hiện có.

### MIT 14.01 Lecture 2 — `tCKk22kaZi4`

[Archive item](https://archive.org/details/MIT14.01F18) có uploader `MIT-OCW`, trường Usage **CC BY-NC-SA 4.0**, danh sách file ghi **Lecture 2: Preferences and Utility Functions** và transcript/SRT. [Transcript OCW gắn đúng ID](https://ocw.mit.edu/courses/14-01-principles-of-microeconomics-fall-2018/fe938934133a619ebb6b08ad366fd63c_tCKk22kaZi4.pdf) cùng SHA/SRT và timeline trong receipt củng cố ánh xạ file. [DSpace course record](https://dspace.mit.edu/entities/publication/dd0b94b3-283f-4fb9-b6b8-a66e52cdb2f1) ghi BY-NC 3.0 US nhưng **mô tả ZIP nói rõ gói này không gồm audio/video**. Do đó không còn cơ sở gọi hai label ấy là xung đột giấy phép của *video*. Label Archive là bằng chứng gần video hơn; terms OCW hiện hành bổ sung điều kiện AI cho nội dung OCW. Vì chưa audit đầy đủ visual/credits trong MP4, giữ `hold_component_scope` với quyền phát hành lại; xử lý nghiên cứu nội bộ có cơ sở phi thương mại nhưng chưa kết luận mọi thành phần qua cổng.

### MIT 6.S897 Lecture 10 — `MoEaRpLNo9A`

[Trang lecture chính thức](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/resources/lecture-10-application-of-machine-learning-to-cardiac-imaging/) nêu Rahul Deo và link tải video Archive. [Slide PDF chính thức](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/4714b64e996e834409e4abab3628ebd7_MIT6_S897S19_lec10.pdf) ghi rõ ảnh/logo của American Heart Association, Mayo Foundation và nhiều nguồn khác “all rights reserved”, bị loại khỏi CC; ví dụ trang 1, 4–8, 10, 12 theo thứ tự trang PDF 1-based. Video có bài giảng trên slide nhưng chưa lập map frame→slide và chưa kiểm xem từng hình bị loại có hiện trong file; vì vậy không tuyên bố mọi frame chứa chúng. Cổng xử lý toàn video/visual vẫn `hold_component_scope`; có thể xem xét nhánh audio/transcript-only riêng nếu protocol chấp nhận và xác minh quyền tiếng nói/phụ đề, song không tự chuyển resource hiện tại thành `pass`.

## Cách xử lý ít rủi ro nhất

1. Chốt protocol là đánh giá nghiên cứu phi thương mại, lưu nội bộ, attribution theo từng publisher; cấm đưa raw media, clip, frame hoặc SRT publisher vào gói phát hành khi chưa có rights receipt riêng. Đây là điều kiện sử dụng, không phải cổng dataset mới.
2. Với CS50P và MIT 14.01, kiểm credits/notice và sample khung hình ở các chapter liên quan đến phép đánh giá visual; nếu phát hiện hình ngoài giấy phép, giữ hold hoặc giới hạn modality được protocol cho phép. Với MIT 6.S897, đối chiếu các slide có notice loại trừ với timeline video trước khi xét tiếp.
3. Ghi vào ledger riêng `research_processing_right`, `redistribution_right`, `component_exception` và nguồn citation; chỉ nâng manifest sau khi scope của protocol khớp bằng chứng. Không cần đổi dataset hoặc tải thêm media để làm bước này.

## Nguồn và độ tin cậy

Ưu tiên tài liệu publisher trực tiếp: [MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) (cập nhật 2026-08-11), [MIT lecture page](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/resources/lecture-10-application-of-machine-learning-to-cardiac-imaging/) và [PDF loại trừ](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/4714b64e996e834409e4abab3628ebd7_MIT6_S897S19_lec10.pdf), [CS50 license](https://cs50.harvard.edu/python/license/) và [Week 2](https://cs50.harvard.edu/python/weeks/2/), [Archive MIT-OCW item](https://archive.org/details/MIT14.01F18), [DSpace course record](https://dspace.mit.edu/entities/publication/dd0b94b3-283f-4fb9-b6b8-a66e52cdb2f1). DSpace license yếu hơn Archive cho **video** vì DSpace ZIP loại audio/video. Không dùng metadata YTSeg hay license của code VidChapters để suy quyền media.

## Câu hỏi chưa giải quyết

1. Protocol đánh giá dùng full video, audio-only, transcript-only hay trích frame? Phạm vi đó quyết định ảnh/logo ngoại lệ có nằm trong dữ liệu xử lý hay không.
2. CS50P Lecture 2 và MIT 14.01 Lecture 2 có notice/credits bên thứ ba nào trong chính MP4 mà các trang publisher không nêu?
3. Với MIT 6.S897, các hình bị loại trên slide xuất hiện ở những khung thời gian nào trong MP4, và điều đó ảnh hưởng modality dự kiến ra sao?
