# Nghiên cứu quyền từng file, GT và split MITFLD

Kiểm tra: 2026-09-28 (Asia/Bangkok). Phạm vi: 10 ID MITFLD đã chọn trong [báo cáo đường MP4](./research-260928-1023-mitfld-direct-media-gt-split-report.md), toàn bộ manifest 538 ID và [course map](./mitfld-260928-1031-normalized-course-map.csv). Đây là kiểm tra quyền/metadata phục vụ quyết định nghiên cứu, không phải tư vấn pháp lý hoặc xác nhận GT đã hợp lệ. Không tải toàn bộ MP4; chỉ đọc HTML, metadata, JSON nhỏ và byte range chứa header MP4.

## Mục lục

- [Tóm tắt quyết định](#tóm-tắt-quyết-định)
- [Phương pháp và nguồn](#phương-pháp-và-nguồn)
- [Quyền và ngoại lệ của mười file](#quyền-và-ngoại-lệ-của-mười-file)
- [Mức khớp MP4 với `frags`](#mức-khớp-mp4-với-frags)
- [Nguồn gốc và giấy phép GT](#nguồn-gốc-và-giấy-phép-gt)
- [Số bài cho split theo khóa](#số-bài-cho-split-theo-khóa)
- [Bước tiếp theo](#bước-tiếp-theo)

## Tóm tắt quyết định

- Mười trang tài nguyên OCW công bố đúng file MP4. Hai file do OCW lưu; tám file trên bảy Archive items có metadata `creator=MIT OpenCourseWare`, `uploader=ocw-prod@mit.edu`, `collection=mit_ocw`, `licenseurl=CC BY-NC-SA 4.0`, file `source=original`, `format=MPEG4`. Không thấy thông báo ngoại lệ quyền riêng trong *text hiển thị* của mười trang; chưa xem nội dung video/slide để loại trừ tác phẩm bên thứ ba. Quyền của bản MP4 trên Hugging Face và quyền của `frags` vẫn chưa được công bố rõ.
- Cả mười cặp MP4 Hugging Face/OCW khác byte. Header `mvhd` cho thấy **9/10 cặp có thời lượng lệch không quá 0,062 giây**; cặp MAS.S62 lệch **1,249 giây**. Thời lượng gần bằng chưa chứng minh cùng nội dung, cùng điểm bắt đầu hoặc mốc `frags` căn đúng bản OCW.
- Kho MITFLD chứa đủ **538 `frags` JSON, 538 transcript JSON, 538 MP4** có stem khớp đúng 538 ID. Sau loại tạm 65 ID từ bốn khóa OCW gắn “Lecture Audio” và năm 6.006 “Problem Session”, còn **468 ID thuộc 21 khóa**. Đây là **trần ứng viên theo metadata**, không phải 468 bài đã đủ quyền/GT/split; số được xác nhận đủ mọi gate hiện là **0**.

## Phương pháp và nguồn

Đối chiếu [MIT OCW Terms cập nhật 2026-08-11](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), mười trang tài nguyên OCW trong [báo cáo trước](./research-260928-1023-mitfld-direct-media-gt-split-report.md), [Archive item metadata](https://archive.org/metadata/MIT8.962S20) (và sáu item tương ứng), [MITFLD dataset card](https://huggingface.co/datasets/robotwang/MITFLD), [repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation), [mô tả bài báo](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) và JSON `frags`. Đếm cây file ở revision MITFLD `f5a5047e040ecf0f80a3cb67d64e324407f323ec`; không suy diễn từ tên thư mục rằng file giải mã được.

Để so thời lượng, gửi HTTP `Range` nhỏ đọc các atom cấp cao MP4, sau đó đọc `mvhd` trong `moov` để lấy timescale/duration. Các server trả `206`. Lượt so chính dùng khoảng 95 range requests cho 20 MP4, tổng payload khoảng 11,5 KB; một cặp thăm dò trước đó có thêm hai khoảng 64 KiB. Đây là **thời lượng container**, chưa phải duration của decoded A/V stream hay sau edit list. Không tải trọn media, không trích frame/audio.

## Quyền và ngoại lệ của mười file

| MITFLD ID | Tài nguyên | File do trang OCW chỉ định | Bằng chứng quyền ở cấp trang/item | Ngoại lệ riêng trong text trang |
|---|---|---|---|---|
| `-Pg11JHzUTo` | 24.900 Lecture 9 | [OCW MP4](https://ocw.mit.edu/courses/24-900-introduction-to-linguistics-spring-2022/ocw_24900_lecture09_2022mar03_360p_16_9.mp4) | OCW-host, trang OCW và điều khoản chung | Không thấy |
| `6MssatXXAzc` | 8.962 Lecture 6 | [Archive MP4](https://archive.org/download/MIT8.962S20/MIT8_962S20_lec06_300k.mp4) | Item `MIT8.962S20`, OCW uploader, CC BY-NC-SA | Không thấy |
| `EXYw8_pnKr0` | 11.165J Lecture 8 | [OCW MP4](https://ocw.mit.edu/courses/11-165j-urban-energy-systems-and-policy-fall-2022/ocw_11165_lecture08_2022sep30_360p_16_9.mp4) | OCW-host, trang OCW và điều khoản chung | Không thấy |
| `LMSTMBX_2F4` | 3.091 Lecture 32 | [Archive MP4](https://archive.org/download/MIT3.091F18/MIT3_091F18_lec32_300k.mp4) | Item `MIT3.091F18`, OCW uploader, CC BY-NC-SA | Không thấy |
| `R2vL2wLqGYg` | 8.962 Lecture 16 | [Archive MP4](https://archive.org/download/MIT8.962S20/MIT8_962S20_lec16_300k.mp4) | Item `MIT8.962S20`, OCW uploader, CC BY-NC-SA | Không thấy |
| `Z2ScgFh81Dc` | 7.05 Lecture 21 | [Archive MP4](https://archive.org/download/MIT7.05S20/MIT7_05S20_lec21_300k.mp4) | Item `MIT7.05S20`, OCW uploader, CC BY-NC-SA | Không thấy |
| `g0bXSXuLVb0` | 6.006 Problem Session 3 | [Archive MP4](https://archive.org/download/MIT6.006S20/MIT6_006S20_02_21_Problem_Session_3_300k.mp4) | Item `MIT6.006S20`, OCW uploader, CC BY-NC-SA | Không thấy; **loại theo loại bài** |
| `mhQebe1Y4d0` | MAS.S62 Lecture 6 | [Archive MP4](https://archive.org/download/MITMAS.S62S18/MITMAS_S62S18_lec06_300k.mp4) | Item `MITMAS.S62S18`, OCW uploader, CC BY-NC-SA | Không thấy |
| `smHwRzk81b0` | 9.40 Lecture 10 | [Archive MP4](https://archive.org/download/MIT9.40S18/MIT9_40S18_lec10_300k.mp4) | Item `MIT9.40S18`, OCW uploader, CC BY-NC-SA | Không thấy |
| `z_xyx-z6arc` | 22.01 Lecture 11 | [Archive MP4](https://archive.org/download/MIT22.01F16/MIT22_01F16_Lec11_300k.mp4) | Item `MIT22.01F16`, OCW uploader, CC BY-NC-SA | Không thấy |

“Không thấy” chỉ nói về các marker ngoại lệ rõ trong text HTML, không phải kết luận không có tài liệu hay hình/âm thanh bên thứ ba. [Điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) cho phép chia sẻ/chuyển đổi OCW content theo CC BY-NC-SA 4.0, có yêu cầu ghi nguồn, phi thương mại, chia sẻ tương tự, và cảnh báo các quyền khác có thể giới hạn sử dụng. Từ 2026-08-11 điều khoản có mục **Permitted Use of AI Training**: dùng OCW content để train/develop/improve mô hình phải đáp ứng ghi nguồn, phi thương mại và ShareAlike đối với derivative models/systems. Phạm vi áp dụng của mục này cho **chỉ chạy inference/đánh giá benchmark** chưa được nguồn phân định rõ; phải phân loại cách dùng thực tế trước khi triển khai. Trang OCW cảnh báo đường dẫn ngoài có điều khoản riêng, nên Archive item metadata là bằng chứng bổ sung chứ không xóa mọi điều kiện của host.

Ưu tiên nguồn quyền: OCW-host file được trang OCW dẫn trực tiếp; sau đó Archive file được OCW dẫn và item do OCW upload; cuối cùng bản MP4 MITFLD trên HF vì [card](https://huggingface.co/datasets/robotwang/MITFLD) chỉ ghi nguồn OCW, không có `license` trong metadata hoặc file LICENSE riêng. Không áp giấy phép của OCW-host/Archive file tự động cho bản MP4 HF khác byte. Không công bố lại media/GT trên cơ sở audit này.

## Mức khớp MP4 với `frags`

| ID | `frags` raw cuối (s) | HF `mvhd` (s) | OCW `mvhd` (s) | OCW − HF (s) |
|---|---:|---:|---:|---:|
| `-Pg11JHzUTo` | 2532 | 4339.462 | 4339.400 | -0.062 |
| `6MssatXXAzc` | 4231 | 4805.254 | 4805.248 | -0.006 |
| `EXYw8_pnKr0` | 1099 | 2383.401 | 2383.367 | -0.034 |
| `LMSTMBX_2F4` | 2670 | 2849.553 | 2849.579 | +0.026 |
| `R2vL2wLqGYg` | 4411 | 5111.502 | 5111.488 | -0.014 |
| `Z2ScgFh81Dc` | 5040 | 5075.534 | 5075.520 | -0.014 |
| `g0bXSXuLVb0` | 3244 | 5188.290 | 5188.288 | -0.002 |
| `mhQebe1Y4d0` | 3249 | 4035.791 | 4037.040 | +1.249 |
| `smHwRzk81b0` | 4276 | 4732.134 | 4732.160 | +0.026 |
| `z_xyx-z6arc` | 3097 | 3250.817 | 3250.816 | -0.001 |

Cả 10 raw cuối `frags` đều nhỏ hơn duration: chúng là **mốc ranh giới nội bộ**, không phải mốc kết thúc. [Loader tác giả](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/base_dataset.py) có thể chèn 0 và duration. Cần giữ riêng JSON raw, duration nguồn và output chuẩn hóa. Mười transcript JSON đều chứa các đoạn `text`, `start`, `duration`; ở MAS.S62, thời điểm kết thúc transcript cuối là **4037,04 s**, bằng `mvhd` của OCW và hơn `mvhd` HF khoảng 1,249 s. Điều này gợi ý khác biệt encode/timebase, chưa chứng minh nguyên nhân. Chênh lệch nhỏ ở header không kiểm tra được edit list, offset mở đầu, thay đổi nội dung, timebase decoded stream hoặc transcript. Bước kế tiếp để gán GT sang bản OCW là so decoded stream ở đầu/giữa/cuối và các acoustic/visual landmarks gần vài `frags` theo quy tắc đóng băng trước test; cặp MAS.S62 phải được ưu tiên kiểm vì lệch 1,249 s.

## Nguồn gốc và giấy phép GT

[MITFLD card](https://huggingface.co/datasets/robotwang/MITFLD) gọi `frags/<id>.json` là ground truth fragment annotations. Cây kho có 538 JSON `frags` và 538 transcript khớp ID, nhưng card thiếu YAML license, không có LICENSE trong cây gốc; API dataset không ghi `cardData.license`. [Repo kpi](https://github.com/wjq1015-hku/lecture-fragmentation) cung cấp loader/metrics và yêu cầu trích dẫn bài báo, không công bố giấy phép GT trong phần kiểm được. [Abstract bài báo 2025](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) xác nhận tác giả giới thiệu MITFLD, nhưng không nêu annotator, hướng dẫn gán nhãn, mức đồng thuận hay giấy phép. Bản full text được lập chỉ mục nhưng truy cập trực tiếp trả 403 trong lượt kiểm; không suy đoán phương pháp từ abstract.

Vì vậy `frags` là **nhãn tác giả công bố** với cấu trúc ranh giới đã kiểm, **chưa phải expert chapter GT độc lập có provenance/rights xác minh** cho RQ1. Cần hỏi tác giả về nguồn GT, quy trình và giấy phép hoặc tạo GT độc lập theo protocol được duyệt. Không gửi liên hệ trong lượt này.

## Số bài cho split theo khóa

| Tầng lọc | Video | Khóa | Trạng thái |
|---|---:|---:|---|
| Manifest MITFLD: đúng 3 file loại cho mỗi ID | 538 | 25 | Chỉ tồn tại file theo cây HF |
| Loại tạm 4 nhóm “Lecture Audio” của OCW | 473 | 21 | Ứng viên visual/full theo loại khóa; cần kiểm từng video |
| Loại 5 “Problem Session” rõ trong tiêu đề 6.006 | 468 | 21 | Trần ứng viên lecture-like; group nhỏ nhất 6, lớn nhất 45 |
| File đủ quyền, decoded alignment, GT provenance và D2 | **0 được xác nhận** | **0 được xác nhận** | Chưa qua gate; không có official split |

Từ 21 khóa ứng viên có thể **thiết kế** chia theo khóa, nhưng chưa chọn hay đóng băng train/validation/final test. Các bài ôn tập/quiz vẫn còn trong 468 vì chưa thống nhất quy tắc loại; loại thêm phải được định nghĩa trước khi nhìn kết quả. `random_split` của [mã tác giả](https://github.com/wjq1015-hku/lecture-fragmentation/blob/main/kpi/datasets/base_dataset.py) chia video, không giữ khóa độc lập. Mọi đổi nguồn YTSeg sang MITFLD hoặc đổi GT/split phải sửa master protocol trước D2.

## Bước tiếp theo

1. Chọn pilot nhiều khóa từ 468 ứng viên; khóa quy tắc loại lecture/review và cách xử lý 65 bài “Lecture Audio”. Ghi ledger từng file gồm trang nguồn, item/file license, credit/exception, host và mục đích dùng.
2. Với MP4 OCW được chọn, kiểm decoded A/V và landmark quanh `frags` trên mẫu nhỏ trước khi gắn GT; đánh dấu `mismatch` nếu không thể căn ổn định. Không tự sửa mốc theo final-test labels.
3. Tìm full paper hoặc xin tác giả xác nhận người/quy trình gán nhãn, license `frags`/transcript/HF MP4, và bảng video→khóa. Trước khi có bằng chứng, giữ `blocked_gt` cho official RQ1.
4. Sau khi đủ video/khóa qua mọi gate, lập và đóng băng group-disjoint split cùng D2. Báo cáo attrition và failures theo khóa, không lấy 468 làm mẫu số kết quả official.

## Câu hỏi chưa giải quyết

- Có ngoại lệ tác phẩm bên thứ ba trong media/slide của từng file được chọn mà text trang không nêu không?
- Điều khoản AI training hiện hành áp vào cách dùng cụ thể của benchmark/model development đến mức nào?
- Bản MP4 OCW có cùng điểm bắt đầu, nội dung và mốc sự kiện với HF tại mọi `frags` không, đặc biệt MAS.S62?
- `frags` do ai tạo, theo rubric nào, có kiểm định chất lượng và quyền sử dụng/tái phân phối nào?
- Sau kiểm decoded media, quyền, GT và lọc loại bài, còn bao nhiêu video/khóa thật sự đủ cho split độc lập có ý nghĩa thống kê?
