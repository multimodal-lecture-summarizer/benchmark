# VidChapters‑7M: phạm vi quyền và provenance trước tải media

**Kiểm ngày:** 2026‑09‑29 (Asia/Bangkok). **Trạng thái:** nghiên cứu nguồn chính thức; chưa có ID VidChapters mới được xác nhận theo từng resource. Không tải media trong lượt này.

## Kết luận ưu tiên

1. **Ưu tiên nguồn bài giảng có publisher gốc và điều khoản riêng cho resource**, trước tiên MIT OCW được lưu trên OCW, tiếp đến CS50 gắn trang khóa và video chính thức. Đây là đường kiểm quyền tốt hơn danh sách YouTube ID thuần, nhưng **chưa coi video VidChapters nào là pass** cho tới khi chứng minh ID ↔ media ↔ annotation và phạm vi quyền cụ thể.
2. **Giữ riêng hai cột quyền:** `research_processing_right` (tải/lưu/xử lý cho nghiên cứu, gồm AI nếu có) và `redistribution_right` (phát hành lại video, transcript, frame hoặc derived artifact). Thiếu bằng chứng phát hành lại chỉ làm `hold_redistribution`; thiếu bằng chứng nghiên cứu làm `hold_research`. Mức `pass` chung của RQ1 phụ thuộc protocol chọn rõ những quyền nào là cổng bắt buộc.
3. **Không suy quyền từ VidChapters:** trang tác giả phát hành annotations/ASR/ID; README gắn MIT cho *code* và dẫn “dataset license” về cùng LICENSE. Điều đó không chứng minh quyền của YouTube video, annotation, hay mọi thành phần hình/âm thanh. [Trang tác giả](https://antoyang.github.io/vidchapters.html), [README](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/README.md), [LICENSE](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/LICENSE).

## Nguồn và độ tin cậy

| Nguồn | Điều chứng minh được | Giới hạn |
|---|---|---|
| Tác giả VidChapters: [project](https://antoyang.github.io/vidchapters.html), [README](https://github.com/antoyang/VidChapters/blob/fa3900c6508d53ea9d490a07f079703b163c78ea/README.md) | Annotation từ user chapter của YouTube; nguồn phát hành annotation, ASR, ID; mã thu thập dùng mô tả video | Không cấp quyền từng video; không chứng minh annotation có license riêng rõ ràng |
| [YouTube loại license](https://support.google.com/youtube/answer/2797468), [hướng dẫn tải](https://support.google.com/youtube/answer/56100) | Standard license là mặc định, CC BY là tùy chọn; YouTube nói không tải video của người khác qua chức năng tải cá nhân | Không xác định license của ID riêng; không thay thế điều khoản publisher gốc |
| [MIT OCW điều khoản](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) (cập nhật 2026‑08‑11) | Nội dung OCW thuộc phạm vi cho phép dùng AI training với attribution, noncommercial, ShareAlike; CC BY‑NC‑SA 4.0 cho nội dung thuộc license | Phải kiểm ngoại lệ từng video/thành phần; điều khoản AI có thể kéo theo nghĩa vụ cho mô hình phái sinh |
| [MIT OCW ví dụ ngoại lệ](https://ocw.mit.edu/courses/2-787j-tissue-engineering-and-organ-regeneration-fall-2024/pages/lecture-videos/) | OCW ghi rõ toàn bộ link video bên ngoài tại khóa này **ngoài** license OCW | Cảnh báo không áp dụng máy móc cho mọi khóa; cần đọc trang resource tương ứng |
| [CS50 Python license](https://cs50.harvard.edu/python/license/) | Khóa được ghi CC BY‑NC‑SA 4.0, cho share/adapt phi thương mại kèm attribution/ShareAlike | Chưa tự xác minh từng video/ảnh/nhạc bên thứ ba; phải nối ID, trang bài và bản file |

Ba nhà phát hành độc lập ở đây là tác giả dataset, publisher học liệu và nền tảng video; đối chiếu theo phạm vi quyền, không lấy sự đồng thuận số đông làm giấy phép.

## Ma trận nguồn ứng viên

| Hạng | Nguồn bài giảng | Phù hợp kiến trúc | Lợi | Rủi ro/cổng hold trước tải | Chi phí kiểm |
|---|---|---|---|---|---|
| 1 | MIT OCW video lưu trong OCW; chọn **nhiều khóa và giảng viên**, ngoài Yale | Publisher gốc, khóa/giảng viên và video thường định danh được | Điều khoản OCW có AI training phi thương mại | ID VidChapters ↔ resource chưa đối chiếu; từng hình/slide/nhạc có thể bị loại; các link video ngoài OCW không thừa hưởng license | Trung bình: trang khóa + từng video + GT |
| 2 | Harvard CS50/CS50P video trên publisher | Trang khóa và transcript chính thức; chủ đề bài giảng rõ | Điều khoản CC BY‑NC‑SA công khai | Nhiều video cùng lecturer/các khóa liên thông thành **một nhóm**; phần bên thứ ba và ID match phải kiểm | Trung bình |
| 3 | YouTube ID chỉ có trong VidChapters, không có publisher resource/license | Dễ lọc annotation nhưng provenance yếu | Nhiều ID | Standard license mặc định; chưa rõ quyền nghiên cứu/tải/lưu và tái phát hành | Cao; `hold_rights` trước bulk media |

**Không đưa Yale vào cohort.** Không tính nhiều video chung khóa/giảng viên thành các nhóm độc lập. Không loại ID trùng YTSeg chỉ vì trùng tập dữ liệu: lưu `usage_history`, tách đã dùng train/tune với chỉ kiểm khả dụng, rồi chống đếm hai lần và test contamination.

## Năm ID MIT OCW xuất hiện trong phép quét GT VidChapters

Đây là **ứng viên theo ID, chưa pass**. Ánh xạ OCW cấp resource chỉ chắc khi publisher page/iframe hoặc transcript PDF chính thức nối tới đúng ID. Điều khoản [OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) cho phép dùng AI với điều kiện, nhưng chưa cấp phép mọi thành phần nằm trong từng video. Quyền phát hành lại video/derived artifact vẫn phải kiểm theo phạm vi thành phần và loại artifact.

| VidChapters ID | Publisher page, khóa, giảng viên | Bằng chứng ID ↔ resource | Quyền nghiên cứu / phát hành lại, lý do hold |
|---|---|---|---|
| `EH6vE97qIP4` | [15.S12 Session 1: Introduction](https://ocw.mit.edu/courses/15-s12-blockchain-and-money-fall-2018/resources/session-1-introduction/); Gary Gensler; [download course](https://ocw.mit.edu/courses/15-s12-blockchain-and-money-fall-2018/download/) có media | Page ghi session và iframe YouTube; ID được dẫn trong [nguồn ngoài](https://video.ploud.fr/w/hD5THRyp86RshZW7xrQ762) tới transcript OCW, nhưng iframe hiện không trả URL cho công cụ; **chưa xác nhận ID trực tiếp từ publisher** | `hold_identity`; khi nối ID xong, nghiên cứu phi thương mại có cơ sở ở OCW terms, nhưng slide/hình trích dẫn và phân phối lại vẫn `hold_component_rights` |
| `3MOahpLxj6A` | [6.041 Fall 2010, Lecture 5](https://ocw.mit.edu/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/resources/lecture-5-discrete-variables-probability-expectations/); John Tsitsiklis | **Trực tiếp:** link iframe của trang OCW trỏ `youtube.com/embed/3MOahpLxj6A`; trang cũng có link tải video Archive | OCW terms hỗ trợ xử lý nghiên cứu phi thương mại **nếu video thuộc phạm vi OCW**; `hold_component_rights` cho slide/hình/nhạc và phát hành lại asset, chưa có audit từng frame |
| `U_C7xW_gCfI` | [8.03SC Lecture 9](https://ocw.mit.edu/courses/8-03sc-physics-iii-vibrations-and-waves-fall-2016/resources/lecture-9-video/); Yen‑Jie Lee | Page đúng tên và iframe YouTube nhưng URL iframe không trả được; **chưa xác nhận ID trực tiếp** | `hold_identity` và `hold_component_rights`; OCW page nhắc nhiều demo và nguồn video ngoài, phải tách chúng khỏi video chính |
| `AW3a2ECNFlE` | [14.772 Lecture 5: Measurement in Development](https://ocw.mit.edu/courses/14-772-development-economics-macroeconomics-spring-2013/resources/lecture-5-february-21-2013/); Robert M. Townsend | [Transcript PDF chính thức](https://ocw.mit.edu/courses/14-772-development-economics-macroeconomics-spring-2013/6483568a465b9c5fcd63ef3b29f64cc6_AW3a2ECNFlE.pdf) có ID trong tên file và đúng bài; [download page](https://ocw.mit.edu/courses/14-772-development-economics-macroeconomics-spring-2013/download/) có video Lecture 5 | Nghiên cứu theo OCW terms có cơ sở cho nội dung OCW; `hold_component_rights` cho slide trích nguồn/hình và phát hành lại file |
| `LFOsw1Vccac` | [21L.011 Lecture 1: Introduction (2007)](https://ocw.mit.edu/courses/21l-011-the-film-experience-fall-2013/resources/lecture-1-introduction-2007/); David Thorburn | [Transcript PDF chính thức](https://ocw.mit.edu/courses/21l-011-the-film-experience-fall-2013/f3d33cfe6a9f83ba53dcd36542aafe22_LFOsw1Vccac.pdf) có ID và lời mở bài khớp; [publisher page](https://ocw.mit.edu/courses/21l-011-the-film-experience-fall-2013/resources/lecture-videos/) có lecture | **Rủi ro cao**: nội dung thảo luận/trình chiếu phim; trang bài nêu ví dụ *Fred Ott’s Sneeze*, *Great Train Robbery*. `hold_component_rights`; không suy quyền của trích đoạn phim từ license OCW. Cần xem credit/ngoại lệ theo timeline trước bất kỳ tái phát hành nào |

Các ID này thuộc **5 khóa/5 giảng viên** theo metadata publisher; đó mới là 5 nhóm tiềm năng. Không gọi là 5 nhóm `pass` trước GT, ID mapping đầy đủ, quyền thành phần và media alignment. Ưu tiên thẩm định `3MOahpLxj6A` và `AW3a2ECNFlE` vì có đường ID chính thức rõ; `LFOsw1Vccac` xếp sau do rủi ro bản quyền phim. `EH6vE97qIP4` và `U_C7xW_gCfI` cần chứng minh embed ID từ publisher trước.

## Cổng quyền theo từng resource

| Trường | Giá trị phải ghi | `hold` khi |
|---|---|---|
| `video_id`, `publisher_url`, `media_url`, `course_id`, `lecturer_ids` | URL gốc + ánh xạ ID và danh tính mọi giảng viên | Chỉ có ID YouTube hoặc tên khóa suy đoán |
| `research_processing_right` | Điều khoản/cho phép cụ thể cho lưu bản sao, trích frame, ASR, đánh giá hoặc training phù hợp protocol | Chỉ có license code/dataset, hoặc chỉ thấy “publicly viewable” |
| `redistribution_right` | Quyền phát hành lại **đúng loại** asset dự định công bố | Chưa thấy điều khoản cho video/transcript/frame; có thể vẫn tiếp tục kiểm research nếu quyền nghiên cứu đã rõ |
| `component_exceptions` | Ghi notices ngoại lệ trên trang video, slide, credit và nội dung nhúng | Có bên thứ ba chưa xác định phạm vi |
| `license_obligations` | Attribution, NC, SA, tác động tới model/artifact | Protocol định phát hành artefact nhưng chưa quyết cách tuân thủ |

**Nhánh quyết định:** chỉ tải thử số ít sau khi GT và `research_processing_right` đạt hoặc được xác định rõ trong protocol; chưa tải hàng loạt. `redistribution_right` được kiểm riêng, không gộp với research. Nếu protocol đòi phát hành lại media và không có quyền đó thì `hold_redistribution`, không ghi sai thành “cấm nghiên cứu”. Chưa có quyền nghiên cứu rõ thì `hold_research`, không suy ra từ việc công khai trên web. Không tự áp dụng ngoại lệ bản quyền như fair use làm quyền chung cho toàn cohort. [YouTube về quyền nội dung](https://support.google.com/youtube/answer/2797468), [MIT điều khoản](https://ocw.mit.edu/pages/privacy-and-terms-of-use/).

## Phạm vi chưa làm và câu hỏi chưa giải quyết

1. Năm ID từ phép quét GT đã có trang khóa phù hợp; còn phải chứng minh embed publisher cho `EH6vE97qIP4` và `U_C7xW_gCfI`, cùng kiểm GT từng hàng.
2. Protocol RQ1 yêu cầu công bố gì: chỉ ID/hash/metric, transcript/frame trích dẫn, mô hình, hay video? Quyền tái phát hành cần chấm theo đúng đầu ra.
3. Với mỗi ID ứng viên, publisher có notice bên thứ ba hoặc điều khoản video riêng khác trang khóa không?
