# Kiểm tra mẫu MITFLD và giấy phép YTSeg qua API

Ngày kiểm tra: 2026-09-28 (Asia/Bangkok). Phạm vi: 10 ID MITFLD đã chọn trước từ danh sách 538 MP4 và 14 ID YTSeg CC BY đã chọn trước, mỗi kênh một ID. Không tải hay giải mã MP4. Đây là hồ sơ bằng chứng cho quyết định nghiên cứu, không phải ý kiến pháp lý.

## Kết luận

**MITFLD:** 10/10 ID đối chiếu được với trang tài nguyên MIT OpenCourseWare chứa đúng YouTube ID; thuộc **9 khóa học**, vì hai ID cùng khóa 8.962. Một mục thuộc khóa 6.006 là **Problem Session**, cần loại nếu tiêu chí chỉ nhận lecture. Cả 10 MP4 và transcript phản hồi `HEAD 200`, tệp `frags` phản hồi `GET 200` với danh sách mốc tăng nghiêm ngặt. Điều này xác nhận **ánh xạ nguồn và khả năng tiếp cận tệp ở mức HTTP**, chưa xác nhận giải mã, căn chỉnh GT với media hay quyền sử dụng bản MP4/GT trong kho MITFLD.

**YTSeg:** Sau khi người dùng cấu hình `YOUTUBE_API_KEY`, một yêu cầu `videos.list` có xác thực trả HTTP 200 và **14/14 ID đã chọn**. Cả 14 đều có `status.license=creativeCommon`, `privacyStatus=public`, `embeddable=true`; `snippet.channelId` khớp kênh trong metadata YTSeg. Cổng `blocked_auth` ban đầu đã được giải quyết cho **mẫu 14 ID**. Đây là bằng chứng metadata hiện hành, chưa chứng minh người đăng sở hữu mọi thành phần trong video, quyền tải MP4 qua một phương thức cụ thể, hoặc tình trạng của toàn bộ 276 ID trong subset.

## Phương pháp và snapshot

- MITFLD: [dataset card và repo](https://huggingface.co/datasets/robotwang/MITFLD), revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec`. Lấy 10 ID ở các vị trí 0, 59, 119, 179, 239, 299, 359, 419, 479, 537 của danh sách 538 tên MP4 sắp xếp tăng; giữ nguyên mẫu đã công bố trước khi ánh xạ khóa. Đọc `frags/<id>.json` nhỏ và `HEAD` MP4/transcript; không tải media. Truy tìm trang tài nguyên OCW có **chuỗi YouTube ID chính xác** trong HTML, không dựa vào title tương tự.
- YTSeg: đã định 14 ID, một ID nhỏ nhất theo thứ tự từ điển của mỗi kênh trong subset CC BY. Lúc kiểm tra đầu tiên chưa có key. Sau khi người dùng cấu hình `.env`, chỉ đọc giá trị `YOUTUBE_API_KEY` trong tiến trình, gửi một yêu cầu `videos.list` có xác thực cho đúng 14 ID với `part=status,snippet,contentDetails` và field mask. Không in/lưu key hay URL chứa key; không tải media.
- [Tài liệu Google](https://developers.google.com/youtube/v3/getting-started) yêu cầu dự án/khoá API để gửi yêu cầu; [`videos.list`](https://developers.google.com/youtube/v3/docs/videos/list) cho phép lấy `status`, `snippet`, `contentDetails`, và [schema video](https://developers.google.com/youtube/v3/docs/videos) định nghĩa `status.license` (`creativeCommon` hoặc `youtube`), `privacyStatus` và `embeddable`.

## Mẫu YTSeg: phản hồi API hiện hành

Các ID kiểm tra: `-KLa_lDkji0`, `2gU4F6ePhcM`, `-_31PoDRu28`, `0GRLhpMao3I`, `14iLLtnGsnE`, `64tsAc2ncJQ`, `Hed8nytXCOw`, `5Dlk1UgQSfQ`, `5L3Ao5KuCC4`, `DJYPdy0ITbo`, `g-JgA1hvJzA`, `Tu7G4btt4WU`, `wOI8RuhW7q0`, `7aURiz5J32A`.

| Trường kiểm tra | Kết quả cho 14/14 ID |
|---|---|
| Phản hồi `videos.list` | HTTP 200; 14 item, không thiếu ID |
| `status.license` | `creativeCommon` |
| `status.privacyStatus` | `public` |
| `status.embeddable` | `true` |
| `snippet.channelId` | Khớp channel ID đã ghi trong YTSeg |

[YouTube Help](https://support.google.com/youtube/answer/2797468?hl=en) mô tả tùy chọn Creative Commons của YouTube là CC BY. Trạng thái API là ảnh chụp tại ngày kiểm tra và có thể đổi. Nó không xác nhận quyền đối với mọi yếu tố bên thứ ba trong video. [Điều khoản YouTube](https://www.youtube.com/t/terms) cũng chi phối cách truy cập/sử dụng dịch vụ; `embeddable=true` không tự cấp quyền tải hay lưu MP4. Cần tách giấy phép metadata, kiểm tra ngoại lệ quyền, và đường lấy media hợp lệ trước khi đưa bất kỳ video nào vào D2.

## Mẫu MITFLD: ánh xạ khóa học trực tiếp

| Video ID | Khóa OCW / loại mục | Trang nguồn OCW chứa đúng ID | Mốc `frags` | HTTP MP4 / transcript / GT |
|---|---|---|---:|---|
| `-Pg11JHzUTo` | 24.900, lecture | [Lecture 9: Phonology, Part 2](https://ocw.mit.edu/courses/24-900-introduction-to-linguistics-spring-2022/resources/ocw_24900_lecture09_2022mar03/) | 12 | 200 / 200 / 200 |
| `6MssatXXAzc` | 8.962, lecture | [Lecture 6: Principle of Equivalence](https://ocw.mit.edu/courses/8-962-general-relativity-spring-2020/resources/lecture-6-the-principle-of-equivalence/) | 10 | 200 / 200 / 200 |
| `EXYw8_pnKr0` | 11.165J, lecture | [Lecture 8: Buildings and Energy Efficiency](https://ocw.mit.edu/courses/11-165j-urban-energy-systems-and-policy-fall-2022/resources/ocw_11165_lecture08_2022sep30_mp4/) | 5 | 200 / 200 / 200 |
| `LMSTMBX_2F4` | 3.091, lecture | [Lecture 32: Polymers I](https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/resources/lecture-32/) | 14 | 200 / 200 / 200 |
| `R2vL2wLqGYg` | 8.962, lecture | [Lecture 16: Gravitational Radiation I](https://ocw.mit.edu/courses/8-962-general-relativity-spring-2020/resources/lecture-16-gravitational-radiation-i/) | 10 | 200 / 200 / 200 |
| `Z2ScgFh81Dc` | 7.05, lecture | [Lecture 21: Glycolysis II](https://ocw.mit.edu/courses/7-05-general-biochemistry-spring-2020/resources/lecture-21-glycolysis-ii-regulation/) | 24 | 200 / 200 / 200 |
| `g0bXSXuLVb0` | 6.006, **Problem Session** | [Problem Session 3](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/resources/problem-session-3/) | 15 | 200 / 200 / 200 |
| `mhQebe1Y4d0` | MAS.S62, lecture | [Lecture 6: SPV and Wallet Types](https://ocw.mit.edu/courses/mas-s62-cryptocurrency-engineering-and-design-spring-2018/resources/lec6-spv-and-wallet-types/) | 17 | 200 / 200 / 200 |
| `smHwRzk81b0` | 9.40, lecture | [Lecture 10: Time Series](https://ocw.mit.edu/courses/9-40-introduction-to-neural-computation-spring-2018/resources/10/) | 34 | 200 / 200 / 200 |
| `z_xyx-z6arc` | 22.01, lecture | [Radioactivity and Series Radioactive Decays](https://ocw.mit.edu/courses/22-01-introduction-to-nuclear-engineering-and-ionizing-radiation-fall-2016/resources/radioactivity-and-series-radioactive-decays/) | 9 | 200 / 200 / 200 |

Các mã khóa khác nhau trong **9 bài lecture-like còn lại** là **8**, không phải 9; hai lecture của 8.962 phải đi cùng một phía của mọi split. `Problem Session` 6.006 chỉ có thể dùng nếu protocol chấp nhận loại bài này. Danh sách 10 là mẫu phân bố theo tên file, **không đại diện thống kê** cho đủ 538 video.

## Quyền và GT: đã xác minh đến đâu

- [Điều khoản MIT OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) cập nhật 2026-08-11 ghi CC BY-NC-SA 4.0, yêu cầu ghi công, phi thương mại và chia sẻ tương tự cho nội dung thuộc giấy phép. Nếu dùng OCW để **huấn luyện/phát triển/cải thiện AI**, trang này nêu thêm điều kiện về ghi công, sử dụng phi thương mại và ShareAlike với mô hình/hệ thống phái sinh. Đánh giá bằng inference cũng phải tuân thủ điều kiện CC áp dụng; không tự gọi mọi cách dùng là AI training.
- [MIT giải thích ngoại lệ “all rights reserved”](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content): nội dung như vậy không được CC của OCW tự động cấp quyền sao chép/tái phân phối. Trong **văn bản hiển thị** của 10 trang nguồn, không thấy thông báo quyền/credits riêng cho từng mục; đó chỉ là **không thấy notice trong phần đã kiểm**, không phải chứng minh không có yếu tố bên thứ ba trong hình/âm thanh. Chưa kiểm tra từng khung hình hoặc audio.
- [README MITFLD tại revision đã kiểm](https://huggingface.co/datasets/robotwang/MITFLD/blob/f5a5047e040ecf0f80a3cb67d64e324407f323ec/README.md) ghi nguồn MIT OCW và cấu trúc 538 bộ MP4/fragment/transcript. Repo không có tệp LICENSE hoặc tag license trong metadata; README không ghi quyền riêng của MP4 và GT hay provenance tạo mốc. Việc OCW có giấy phép CC cho vật liệu thuộc quyền MIT **không tự xác nhận** bản phát hành lại và nhãn `frags` của MITFLD đã qua kiểm toán quyền.
- Các dãy `frags` mẫu đều tăng nghiêm ngặt, song một số không bắt đầu ở 0. Chưa biết quy ước mốc là đầu đoạn, ranh giới nội bộ hay nhãn khác; chưa đối chiếu với thời lượng decoded video hoặc nguồn tạo GT. Không đưa vào D2 từ kiểm tra HTTP này.

## Trạng thái cổng và việc tiếp theo

| Cổng | MITFLD mẫu | YTSeg mẫu |
|---|---|---|
| Source/course identity | **Đã ánh xạ 10/10** tới trang OCW; 9 course IDs, 1 Problem Session | 14/14 `channelId` khớp; dataset không có `course_id` |
| Media access | 10/10 MP4 `HEAD 200`; chưa tải/giải mã | 14/14 public và embeddable qua API; chưa xác minh đường lấy MP4 được phép |
| GT | 10/10 file mốc hiện diện và tăng; ngữ nghĩa/căn chỉnh/quyền GT chưa rõ | Creator/editorial timestamps có trong metadata; chưa audit trên media |
| Rights | OCW terms đã nhận diện; ngoại lệ trong media và quyền kho thứ cấp/GT **pending** | 14/14 `creativeCommon` qua API; quyền thành phần và phương thức truy cập media **pending** |
| Independent split | 8 mã khóa ở 9 lecture-like mẫu; khả năng toàn bộ 538 chưa xác định | Chưa có course map, 14 kênh CC BY rất lệch |

Với YTSeg, bước tiếp theo là rà quyền thành phần và xác định phương thức truy cập media được YouTube cho phép cho các ID dự kiến sử dụng; sau đó kiểm tra mọi ID trong cohort được đề xuất, không suy rộng từ 14/276. `creativeCommon` chỉ giải quyết một trường metadata của cổng quyền, chưa hoàn thành Phase 2.

Với MITFLD, bước có giá trị nhất là đối chiếu nguồn/credits và quyền thành phần cho 9 lecture-like mục, hỏi tác giả về giấy phép và cách tạo GT nếu README không có, rồi làm pilot decode/căn chỉnh nhỏ trên media được phép. Chỉ sau đó mới mở rộng course map và thử thiết kế split. Không đổi master-plan RQ1/D2 trên cơ sở mẫu 10 tệp.

## Câu hỏi chưa giải quyết

- Có video YTSeg nào trong 14 ID này đạt cả quyền đối với mọi thành phần tác phẩm lẫn đường lấy media được phép? Nếu mở rộng cohort, các ID còn lại trong 276 có còn public/CC/embeddable không?
- Quyền dùng và tái phân phối MP4, transcript, `frags` của MITFLD cụ thể ra sao; mốc GT do ai tạo và có khớp video được giải mã không?
- Trong đủ 538 MITFLD video, sau loại Problem Session, ngoại lệ quyền và GT không đạt, còn bao nhiêu khóa học độc lập để lập split và ước lượng kết quả đáng tin cậy?
