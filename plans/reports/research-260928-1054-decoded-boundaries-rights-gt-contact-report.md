# Kiểm chứng giải mã mốc MITFLD, ngoại lệ quyền và GT

Kiểm tra ngày 2026-09-28 (Asia/Bangkok). Phạm vi: mười file MITFLD/OCW mẫu từ [báo cáo trước](./research-260928-1043-mitfld-file-rights-gt-alignment-split-report.md), giải mã mẫu ba bài thuộc ba khóa, rà tài liệu đi kèm và kênh xác nhận GT. Không tải trọn MP4. Đây là pilot kiểm chứng, chưa phải freeze D2 hay kết quả RQ1 official.

## Mục lục

- [Kết luận](#kết-luận)
- [Đối chiếu hình và tiếng đã giải mã](#đối-chiếu-hình-và-tiếng-đã-giải-mã)
- [Ngoại lệ quyền trong nội dung](#ngoại-lệ-quyền-trong-nội-dung)
- [Nguồn gốc và giấy phép GT](#nguồn-gốc-và-giấy-phép-gt)
- [Số bài còn lại](#số-bài-còn-lại)
- [Thư hỏi tác giả đã chuẩn bị](#thư-hỏi-tác-giả-đã-chuẩn-bị)
- [Bước tiếp theo](#bước-tiếp-theo)

## Kết luận

Ba cặp MP4 Hugging Face–OCW được giải mã quanh mốc `frags` từ **24.900, 8.962 và MAS.S62** có khung hình gần trùng và âm thanh tương quan cao tại các cửa sổ đã lấy mẫu. Riêng MAS.S62 được kiểm thêm đầu/cuối bài: cửa sổ gần cuối vẫn căn tốt dù header container hai bản lệch 1,249 giây. Đây là bằng chứng **cục bộ** về cùng nội dung/time alignment, không chứng minh mọi ranh giới `frags` hoặc toàn bộ 468 ứng viên.

Rà text trang và tài liệu đi kèm chưa thấy ngoại lệ riêng cho mười bài mẫu. Sáu khung hình OCW ở đầu/cuối ba bài cũng không hiện thông báo ngoại lệ, nhưng không phải rà toàn bộ video hoặc mọi slide. `frags` vẫn thiếu hồ sơ công khai về người gán nhãn và giấy phép. **Số bài xác nhận đủ mọi gate official hiện là 0**; 468/21 là trần ứng viên sau lọc metadata, ba bài chỉ đạt spot-check giải mã.

## Đối chiếu hình và tiếng đã giải mã

Dùng FFmpeg HTTP seek trực tiếp tới MP4 HF và MP4 do OCW công bố, trích mỗi cửa sổ 5 giây: năm khung xám 160×90 tại 1 fps và âm thanh mono 4 kHz. So Pearson/MAE khung hình và tương quan âm thanh sau dịch lag tối ưu. Không tạo bản sao MP4 cục bộ; các cửa sổ HTTP có thể truyền nhiều byte hơn đoạn decoded, **không có số byte mạng đo được hoặc bảo đảm hard cap**. Kết quả cho đúng thời điểm và phiên bản nguồn đã kiểm ngày này.

| ID / khóa | Cửa sổ (giây) | Hình HF↔OCW | Tiếng HF↔OCW | Mức kết luận |
|---|---:|---|---|---|
| `-Pg11JHzUTo` / 24.900 | raw `frag=295`, 5 s | Pearson xấp xỉ 1,000 trên 5 frame; MAE 1,6–1,9/255 | lag OCW so HF −0,0362 s; rho 0,9935 | Khớp cục bộ tại một mốc |
| `6MssatXXAzc` / 8.962 | raw `frag=318`, 5 s | Pearson xấp xỉ 1,000; MAE 1,6–1,8/255 | lag −0,0362 s; rho 0,9853 | Khớp cục bộ tại một mốc |
| `mhQebe1Y4d0` / MAS.S62 | raw `frag=3249`, 5 s | Pearson xấp xỉ 1,000; MAE 0,1–1,3/255 | lag −0,0362 s; rho 0,9920 | Khớp cục bộ tại một mốc |
| `mhQebe1Y4d0` / MAS.S62 | 30 và 4029, mỗi cửa sổ 5 s | Pearson 1,000 và 0,9998–0,9999 | lag −0,0362 s; rho 0,9928 tại cả hai | Căn tốt ở đầu/cuối mẫu; nguyên nhân duration lệch chưa rõ |

Tổng cộng năm cửa sổ, 25 giây decoded từ **mỗi nguồn** (50 khung hình cả hai nguồn, 50 giây PCM cả hai nguồn). [Báo cáo header](./research-260928-1043-mitfld-file-rights-gt-alignment-split-report.md) ghi MAS.S62 `mvhd` HF 4035,791 s, OCW 4037,040 s; transcript MITFLD kết thúc 4037,040 s. Kiểm tra ở 4029 s vẫn giống mạnh, nhưng không kết luận 1,249 s chênh lệch chỉ ở đuôi. Không xác minh decoded duration toàn bài, edit list, offset của mọi `frags`, hoặc nội dung giữa những cửa sổ. Cần protocol lấy mẫu nhiều boundary hơn, gồm mốc gần đầu/giữa/cuối và trường hợp lệch, **trước** khi gắn GT sang bản OCW để chấm điểm.

## Ngoại lệ quyền trong nội dung

Rà 10/10 trang tài nguyên OCW gồm JSON-LD: mỗi trang khai `WebPage` với [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), không có credit/exception riêng trong text trang. Rà 9 PDF transcript được liên kết từ 8 trang và PDF slide 48 trang của MAS.S62 Lecture 6: không thấy marker rõ về tác phẩm bên thứ ba/giấy phép ngoại lệ; một số chỉ có lời dẫn CC chung. Bảy Archive item cũng không nêu ngoại lệ riêng trong mô tả metadata. Đây là **negative search trên text được chọn**, không phải xác nhận nội dung MP4 được cấp phép toàn bộ.

Sáu frame OCW được xem trực tiếp tại 24.900 (15, 4320 s), 8.962 (15, 4790 s), MAS.S62 (30, 4029 s) cho thấy lớp học/bảng/slides; frame MAS.S62 ở 30 s có title card ghi bài, ngày và T. Dryja. Không frame nào trong sáu frame hiện thông báo ngoại lệ, nhưng việc lấy vài frame không thể rà toàn bộ hình, tiếng, slide hoặc privacy/publicity rights. [OCW Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) cũng nói giấy phép có thể không cấp đủ mọi quyền cần thiết. Một [tài liệu OCW khác](https://ocw.mit.edu/courses/2-43-advanced-thermodynamics-spring-2024/mit2_43_s24_lec01.pdf) ghi rõ hình bên thứ ba bị loại khỏi CC; đây là ví dụ chứng minh rằng chỉ nhìn footer CC của khóa không đủ kết luận cho từng thành phần.

Trạng thái hợp lý cho cả mười file là `published_by_ocw_or_ocw_archive; third_party_content_unverified`. Không ghi `no_exceptions` hoặc `rights_cleared`. Với mục đích train/develop/improve AI, [điều khoản OCW cập nhật 2026-08-11](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) đặt điều kiện ghi nguồn, phi thương mại và ShareAlike. Chưa có giải thích chính thức liệu chỉ chạy inference/evaluation thuộc phạm vi điều này; phải xác định use case cụ thể trước khi áp dụng.

## Nguồn gốc và giấy phép GT

[MITFLD card](https://huggingface.co/datasets/robotwang/MITFLD) chỉ gọi `frags` là ground truth; metadata không có license, cây kho không có LICENSE. [Repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation) cũng không công bố giấy phép GT. [Bản ghi bài báo tại HKMU](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) có abstract, không có mô tả annotator/rubric/QC/licensing trong phần đọc được. PDF ACM DOI `10.1145/3746640` trả 403 trong môi trường kiểm tra. Không suy ra “expert GT” hay quyền tái phân phối từ nhãn “ground truth”.

Metadata tác giả trên bản ghi HKMU xác nhận địa chỉ của đồng tác giả Ricky Y.K. Kwok là `kwok@hkmu.edu.hk`. Kênh dự phòng là [GitHub Issues repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation/issues). Chưa nhận xác nhận GT từ tác giả.

## Số bài còn lại

| Mốc lọc | Video | Khóa | Bằng chứng |
|---|---:|---:|---|
| Manifest MITFLD có `frags`/transcript/MP4 cùng stem | 538 | 25 | Cây file HF ở revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec` |
| Loại tạm 4 khóa OCW gắn Lecture Audio | 473 | 21 | Loại theo khóa; còn phải xét nội dung từng file |
| Loại 5 Problem Sessions rõ trong tiêu đề | 468 | 21 | Trần metadata của bài lecture-like |
| Trong 10 bài mẫu: loại 1 Problem Session | 9 | 8 | Có trang OCW/Archive cấp file, chưa rà hết nội dung/GT |
| Có decoded A/V spot-check tốt tại mốc mẫu | 3 | 3 | 3/3 cặp được thử, không suy rộng sang 465 bài chưa thử |
| Xác nhận đủ rights + GT provenance/license + decoded alignment toàn bài + D2 | **0** | **0** | Chưa có official split; đây là số **được xác nhận**, không phải số thật sự không thể dùng |

Lượt thử đọc đồng loạt 538 JSON `frags` riêng lẻ bị dừng vì tốc độ truy cập không phù hợp; **không có thống kê validity của toàn bộ 538 JSON** trong báo cáo này. Cây file chứng minh tồn tại/tên khớp, không chứng minh nội dung JSON hợp lệ hoặc nhãn chất lượng. Ba bài spot-check chỉ có một hoặc vài cửa sổ, chưa thể chuyển vào hàng cuối. Quyết định split course-disjoint cần đợi quyền/GT, ranh giới tuyển chọn và D2; không lấy 468 làm số mẫu thực nghiệm official.

## Thư hỏi tác giả đã chuẩn bị

Tự động xét quyền truy cập đã **từ chối mở Gmail** vì yêu cầu hiện tại được diễn giải là chưa cho phép truy cập hộp thư riêng tư/gửi thư. Không thử kênh gửi khác để lách chặn. Sau khi người dùng chấp thuận rõ việc mở Gmail và gửi câu hỏi tới tác giả, có thể dùng nội dung sau:

> **To:** kwok@hkmu.edu.hk  
> **Subject:** Questions about MITFLD annotation provenance, timing and reuse permissions
>
> Dear Professor Kwok,
>
> I am assessing MITFLD for a course-disjoint lecture fragmentation research benchmark. Could you clarify:
>
> 1. How were `frags` boundaries created: manual annotators, OCW chapter marks, or an algorithm? What rubric, time origin and quality checks were used?
> 2. Which MP4 version do the timestamps reference? In one sample (`mhQebe1Y4d0`), the Hugging Face and OCW MP4 container durations differ by about 1.25 seconds, while the transcript ends at the OCW duration. Is there a known re-encode or offset?
> 3. What license or permission applies separately to `frags`, transcripts and bundled MP4s for local noncommercial evaluation, aggregate publication and any redistribution of annotations? Are there known third-party exclusions?
> 4. Is there an authoritative `video_id` to course mapping or a recommended course-disjoint split?
>
> Thank you for your work and guidance.

## Bước tiếp theo

1. Sau khi được phép liên hệ, gửi thư trên và lưu phản hồi có nguồn. Không tự suy đoán câu trả lời hoặc đóng băng GT trước đó.
2. Với các khóa mẫu, rà thêm credit trong video/slides ở nhiều mốc và tài liệu gốc; đánh dấu từng thành phần ngoại lệ tìm được. Không biến “không thấy trong mẫu” thành “không có”.
3. Đóng băng quy tắc kiểm media/GT rồi mở rộng spot-check theo khóa, bao gồm offset, nội dung gần boundary, duration decoded và tỷ lệ thất bại. Chỉ sau đó tính denominator thực sự và chia train/validation/final test theo khóa.

## Câu hỏi chưa giải quyết

- Có tác phẩm bên thứ ba trong các đoạn chưa xem của mười file mẫu và trong 459 ứng viên lecture-like chưa rà quyền cấp trang không?
- Các `frags` khác trong mỗi bài và toàn bộ 468 ứng viên có căn với bản MP4 OCW sau giải mã không?
- Tác giả xác nhận nguồn gốc, rubric, QC, phiên bản MP4 và giấy phép GT như thế nào?
- Cách dùng benchmark cụ thể có kích hoạt điều khoản AI training của OCW không?
- Sau mọi gate còn đủ khóa/đơn vị độc lập cho split và khoảng tin cậy cấp khóa không?
