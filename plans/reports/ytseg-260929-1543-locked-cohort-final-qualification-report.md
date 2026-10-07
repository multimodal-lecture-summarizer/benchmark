# YTSeg: quyết định qualification trên danh sách đã khóa

**Đính chính 2026-09-29:** Kết luận chuyển hẳn qualification sang VidChapters bên dưới là ảnh chụp quyết định cũ, đã được thay bằng [cập nhật YTSeg/VidChapters](./qualification-260929-1637-ytseg-vidchapters-gate-report.md) và [protocol đánh giá dự thảo](../260929-1659-rq1-ytseg-evaluation-protocol/rq1-ytseg-evaluation-protocol-draft.md). Kiểm trực tiếp 10 hàng cho phép đọc `target_ts` ghép sẵn; YTSeg vẫn là nguồn ưu tiên để giải quyết quyền 10 media đã kiểm. VidChapters chỉ phục vụ mở rộng nhóm nếu cần. [Receipt GT mới](./ytseg-gt-260929-1637-direct-representation-receipt.json). Manifest 15:43 được giữ nguyên như lịch sử, không phải trạng thái quyền hiện tại.

**Kết quả:** **Có 0 video thuộc 0 nhóm độc lập vượt toàn bộ cổng.** Mười video TRAIN thuộc **4 nhóm ứng viên** đã qua cổng media kỹ thuật; cả 10 vẫn `hold`, hai ID original validation/test `exclude`. Không có split train/validation/final_test hợp lệ để khóa. Không lập amendment, không đóng băng D2, không chọn mô hình hoặc chạy official RQ1. Chuyển qualification sang [VidChapters‑7M](./vidchapters-7m-260929-qualification-kickoff-report.md).

[Manifest `pass/hold/exclude`](./ytseg-260929-1543-resource-gate-manifest.csv) SHA‑256 `8df5d2a0fa6e0ce684acda795198aedcbe8b91914a415d146bc2d1ffe5e98d68`; [decision receipt](./ytseg-260929-1543-qualification-decision-receipt.json). [Danh sách trước media](./ytseg-260929-1543-pre-media-cohort-lock.csv) vẫn giữ SHA‑256 `4dedb0efacecf547f1bf2eac773a0b6ced3cea9ed1330875cf6e9b493e9f0719`. Sáu hàng `reserve` cùng MIT 16.687 cũng được kiểm full-file theo yêu cầu người dùng “áp dụng cho danh sách”; đây là mở rộng **phạm vi kiểm media** so với câu không tải reserve trong [protocol khóa trước media](./ytseg-260929-1543-pre-media-cohort-protocol.md), không đổi ID, vai trò, thứ tự hoặc số nhóm và không dựa trên điểm mô hình.

## 1. GT: ba dạng số đếm, năm mẫu dữ liệu, mã upstream chưa có

Đã đọc 16.404 hàng TRAIN của revision YTSeg `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`, so trực tiếp `raw_chapters` với hai trường derived. [Receipt quan hệ GT](./ytseg-260929-1543-gt-relationship-audit.json):

| Quan hệ tiêu đề − mốc | Cách biểu diễn thấy trong dữ liệu | Hàng |
|---|---|---:|
| 1 | Raw titles; raw starts bỏ mốc 0 đầu | 15.341 |
| 1 | Thêm `Intro` vào titles; giữ mọi raw starts | 472 |
| 2 | Thêm `Outro` vào titles; raw starts bỏ mốc 0 | 550 |
| 2 | Thêm cả `Intro` và `Outro`; giữ mọi raw starts | 6 |
| 0 | Raw titles; giữ mọi raw starts | 35 |

Cả mười video TRAIN đã khóa thuộc mẫu đầu; `chapter_titles` có một phần tử nhiều hơn `chapter_timestamps`. [Paper YTSeg §2.2](https://aclanthology.org/2024.eacl-long.25.pdf) mô tả việc thêm Intro/Outro; [cây release ghim](https://huggingface.co/datasets/retkowski/ytseg/tree/4ee1c1fccc5a9e118ff0918f3df1e61aadca8970) không có mã tạo đúng các trường derived. Năm quan hệ quan sát được giải thích **hình dạng dữ liệu**, chưa xác nhận phép chuyển đổi bằng mã upstream. Theo cổng người dùng yêu cầu, `hold_gt` cho cả 10; không zip tiêu đề–mốc theo cùng index, không tự thêm/sửa nhãn. GT original validation/test không được đọc. Riêng [bài CS50P](./ytseg-260929-1543-cs50-media-report.md) có `text_wt`/`text_wl` mang nội dung vector calculus không thuộc bài Loops; kiểm timeline chỉ dùng `text_ref`/`target_text_ts_ref` và SRT publisher, còn các trường ASR kia cần điều tra trước bất kỳ phép đánh giá nào.

## 2. Nguồn, quyền và nhóm độc lập

Danh sách chỉ lấy video TRAIN có course/lecturer xác minh được, ngoài Yale. `course_id`, tất cả `lecturer_ids`, trang publisher, đường media và trang quyền nằm trong manifest; đối chiếu từng trang MIT OCW, [MIT DSpace 14.01](https://dspace.mit.edu/entities/publication/dd0b94b3-283f-4fb9-b6b8-a66e52cdb2f1), [MIT Archive item 14.01](https://archive.org/details/MIT14.01F18), và [Harvard CS50P](https://cs50.harvard.edu/python/weeks/2/). Dataset license không tự chứng minh quyền của video.

| Nhóm ứng viên | Video TRAIN | Cơ sở gộp | Quyền resource |
|---|---:|---|---|
| MIT 16.687 IAP 2019 | 7 | Cùng khóa, Philip Greenspun/Tina Srivastava | `hold`: chưa kiểm đủ thành phần trong bảy file |
| MIT 6.S897 S19 | 1 | Peter Szolovits, David Sontag, Rahul Deo | `hold`: [slide chính thức](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/4714b64e996e834409e4abab3628ebd7_MIT6_S897S19_lec10.pdf) ghi nhiều thành phần bên thứ ba bị loại khỏi CC |
| Harvard CS50P 2022 | 1 | David J. Malan | `hold`: [giấy phép khóa](https://cs50.harvard.edu/python/license/) chưa xác minh toàn bộ thành phần trong file |
| MIT 14.01 F18 | 1 | Jonathan Gruber | `hold`: chưa kiểm toàn thành phần; nhãn giấy phép trên DSpace và Archive khác nhau |

Quy tắc nhóm dùng thành phần liên thông nếu **cùng khóa hoặc có bất kỳ giảng viên chung**, kể cả quan hệ bắc cầu. Hai video 16.687 thuộc YTSeg original validation/test được ghi `exclude` vì chung nhóm với TRAIN và nhãn của chúng không dùng cho qualification. Không có ID Yale trong danh sách. Mười TRAIN là 10 ID khác nhau, thuộc bốn thành phần; **0 thành phần có video `pass`**. [Receipt quyết định](./ytseg-260929-1543-qualification-decision-receipt.json) ghi đầy đủ thành viên nhóm và split rỗng. Ngưỡng N/G hoặc mục tiêu precision/CI chưa được định lượng trước; với N=0/G=0, không cần giả định một ngưỡng để kết luận nhánh YTSeg hiện không đủ.

## 3. Toàn file, timeline và trùng nội dung

**10/10 video TRAIN** tải đủ byte qua nguồn MIT OCW/Archive hoặc Harvard CS50, có SHA‑256 đối chiếu lại ở máy; tổng cộng **1.897.109.450 byte**. Cả 10 giải mã hết stream video/audio và có PTS frame/packet phù hợp; mỗi video được đối chiếu tại 10%, 50%, 90% và ít nhất ba ranh giới chapter nội bộ bằng phụ đề/transcript và, với phần lớn file, khung hình. Thời lượng gần bằng chỉ dùng kiểm sơ bộ. Receipt từng file giữ URL, byte count, hash, probe, số frame và điểm kiểm:

- MIT 16.687: [bài `-dOX_4lI6HY`](./ytseg-260929-1543-dox-media-report.md), [ba reserve A](./ytseg-260929-1543-reserve-a-media-report.md), [ba reserve B](./ytseg-260929-1543-reserve-b-media-report.md).
- MIT 6.S897: [bài `MoEaRpLNo9A`](./ytseg-260929-1543-moea-media-qualification-report.md).
- Harvard: [bài `-7xg8pGcP6w`](./ytseg-260929-1543-cs50-media-report.md).
- MIT 14.01: [bài `tCKk22kaZi4`](./ytseg-260929-1543-tck-media-report.md).

[Sàng lọc trùng transcript](./ytseg-260929-1543-content-duplicate-report.md) đọc đủ 10 `text_ref` YTSeg và 45 transcript MITFLD (35 selected, 10 pilot cũ): **450/450 cặp**, giao 5-gram tối đa **0,57%** theo containment của transcript ngắn hơn, **0 cụm 10 từ trùng**. [Kiểm 45 cặp nội bộ YTSeg](./ytseg-260929-1543-internal-duplicate-receipt.json): giao 5-gram tối đa **0,78%**, tối đa **2 cụm 10 từ trùng**. Không thấy tín hiệu hai bài là cùng nội dung lời nói dưới ID khác. So khớp hình/âm thanh từng cặp và bản đăng lại với transcript khác chưa được thực hiện; kết luận giới hạn ở text screen, không gọi đó là chứng minh tuyệt đối không trùng. Điều này không làm thay đổi trạng thái `hold_gt`/`hold_rights`.

## Quyết định

| Cổng | Kết quả |
|---|---|
| Chọn trước media, xác minh khóa/giảng viên | 10 TRAIN / 4 nhóm ứng viên; 2 nontrain exclude |
| Toàn file, SHA‑256, decode, nhiều vị trí timeline | 10/10 `pass_technical` |
| GT có mã upstream giải thích ba dạng | 0/10 `pass`; 10 `hold_gt` |
| Quyền theo thành phần từng video | 0/10 `pass`; 10 `hold_rights` |
| Trùng nội dung với pilot | 450 cặp transcript không có tín hiệu trùng; A/V fingerprint chưa có |
| Vượt **toàn bộ** cổng | **0 video / 0 nhóm** |
| Split, amendment, D2, official RQ1 | `no_selection`, chưa thực hiện |

Nhánh [VidChapters‑7M](./vidchapters-7m-260929-qualification-kickoff-report.md) đã bắt đầu bằng việc tải/hash annotation và ba split của tác giả, kiểm mã tạo nhãn và sàng lọc giao ID với YTSeg/pilot. Nó là ứng viên tiếp theo, **chưa có cohort đủ cổng**.

## Câu hỏi chưa giải quyết

1. Có mã tiền xử lý YTSeg upstream xác nhận chính xác năm mẫu trong ba dạng title–timestamp không?
2. Có bằng chứng quyền cho mọi thành phần của từng video theo phạm vi xử lý nội bộ/công bố aggregate không?
3. VidChapters‑7M còn bao nhiêu bài giảng đa khóa có GT, media, quyền và nhóm giảng viên đủ để lập split với precision/CI đã định trước?
