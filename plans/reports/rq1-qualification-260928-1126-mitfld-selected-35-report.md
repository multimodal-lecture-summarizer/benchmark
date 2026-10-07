# Kiểm tra quyền, căn chỉnh và GT cho 35 bài MITFLD đã chọn

**Kiểm tra:** 2026-09-28, 11:26–11:47 Asia/Bangkok. **Cohort:** [35 ID v2](./mitfld-rq1-35-260928-1120-selected.csv), SHA-256 `ed658ca8fe4fce47b780ef72195d2e0bdc58a60a141e622b1d9f73128fd1b49d`; revision MITFLD `f5a5047e040ecf0f80a3cb67d64e324407f323ec`. Chỉ đánh giá tập 35 bài, không áp kết luận cho 424 reserve hoặc toàn MITFLD. Split 19/8/8 bài, 11/5/5 khóa là **đề xuất**, chưa phải D2.

## Kết quả theo gate

| Gate | Đã xác minh | Chưa xác minh / quyết định |
|---|---|---|
| Nguồn MP4 | [Ledger OCW](./mitfld-rq1-35-260928-1135-ocw-source-rights-ledger.csv): 35/35 ID có trang OCW và link MP4 cụ thể, không trùng URL; 27 Archive, 8 OCW-host. [Metadata 27 Archive file](./mitfld-rq1-35-260928-1143-archive-item-metadata.csv): 27/27 đúng file `source=original` trong 16 item có `creator=MIT OpenCourseWare`, `uploader=ocw-prod@mit.edu`, `licenseurl=CC BY-NC-SA 4.0` (chấp nhận URL http/https). [OCW Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) công bố CC BY-NC-SA 4.0 cho OCW content. | Metadata item/trang không chứng minh quyền của từng thành phần slide, ảnh, nhạc, tiếng, người xuất hiện; 35/35 `embedded_exception_status=unverified`. Không tự chuyển quyền OCW sang bản MP4 HF. |
| YouTube metadata | Đối chiếu [ledger API xác thực ngày 2026-09-28](./mitfld-260928-1031-youtube-course-metadata-ledger.csv): 35/35 `youtube` standard license, public, embeddable; 0 Creative Commons trên YouTube. | Không dùng YouTube làm căn cứ tải hoặc tái sử dụng MP4. |
| Cấu trúc nhãn và media HF | [Ledger annotation](./mitfld-rq1-35-260928-1126-annotation-ledger.csv): 35/35 `frags` và transcript HTTP 200, parse hợp lệ, hash riêng; 479 mốc raw, 3–26 mốc/bài, tăng nghiêm ngặt; mốc cuối nằm trong khoảng transcript. [Ledger probe](./mitfld-rq1-35-260928-1135-hf-media-probe.csv): 35/35 HF MP4 có duration qua `ffprobe`; mốc `frags` cuối nhỏ hơn duration. | Đây là kiểm tra cấu trúc và giới hạn thời gian. Chưa chứng minh mỗi mốc là ranh giới ngữ nghĩa đúng hoặc khớp bản OCW. Hiệu `HF duration − transcript end` nằm từ −0,097 đến +24,717 s; cần xử lý timebase/đuôi theo từng bài nếu dùng làm GT. |
| HF↔OCW sau giải mã | [Ledger landmark](./mitfld-rq1-35-260928-1138-decoded-landmark-ledger.csv): 3/35 bài ở 3 khóa (`gnWKpHUj11w`, `7LyvAVjQUR8`, `muwNEvhy6Po`) khớp **cục bộ một mốc `frags`/bài**: 4 frame/bài Pearson 0,99946–0,99973; audio rho 0,984–0,994 sau lag 36,25 ms. Cặp duration lệch 0,041–0,052 s. | 32 bài chưa decoded HF↔OCW; ba bài đã thử vẫn chưa kiểm toàn timeline hoặc các mốc khác. HTTP seek không lưu MP4 đầy đủ, nhưng số byte truyền mạng chưa đo được. |
| Nguồn gốc và giấy phép GT | [Card MITFLD](https://huggingface.co/datasets/robotwang/MITFLD) gọi `frags` là “ground truth fragment annotations”; [bài báo tác giả](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) xác nhận MITFLD là dataset cho *lecture video fragmentation*. HF API của revision đã khóa trả `cardData.license=None`, không có file tên LICENSE trong repo tree. | Không có bằng chứng công khai đủ về người/rubric gán mốc, QC, quyền sử dụng/tái phân phối `frags` hoặc mức tương đương giữa *fragmentation/key-point* và chapter GT của RQ1. Chưa có xác nhận từ tác giả; 35/35 `gt_provenance_license=unverified`. |

**Kết luận định lượng:** 35/35 bài còn là **ứng viên đang chờ**, 0 bài đã xác nhận đồng thời đủ quyền nội dung + căn chỉnh trên MP4 OCW + GT phù hợp/có quyền. Không có bài nào bị loại chắc chắn chỉ từ kiểm tra này; `0 qualified` không có nghĩa `0 usable`. Không đóng băng D2, không chạy RQ1 official hoặc dùng split final test như held-out đã chứng nhận.

## Ngoại lệ cần xử lý theo đúng ID

- `9uqKU5ZDwfM`: [OCW mô tả Chernobyl trip report](https://ocw.mit.edu/courses/22-01-introduction-to-nuclear-engineering-and-ionizing-radiation-fall-2016/resources/chernobyl-trip-report-by-jake-hecla/) với nhiều ảnh; kiểm quyền ảnh và mức phù hợp loại bài.
- `neBeTYziSLo`: [OCW Selected Videos](https://ocw.mit.edu/courses/11-382-water-diplomacy-spring-2021/pages/selected-videos/) xác định bài trình bày sinh viên Flora Klise; kiểm nguồn ảnh/slide và quyền người trình bày.
- `2NMtS1ecb3o` là Course Review; `_S1CREXGfvE` là research intro 13:22; `gtQ046Tu2S4` là clip 7:17. Cần áp quy tắc phù hợp chaptering đã định trước, không loại tùy theo điểm mô hình.
- `Rlvwagd2BmY`, `vcsxCFSLyP8`: shortlink cũ chuyển sang trang khóa 18.225 năm 2023, nhưng các trang ấy dẫn đúng file Archive `MIT18.217F19`; giữ cờ course-renumbering và kiểm độc lập nhóm nguồn.
- `KAySmSEGc9U`, `7J1HD9rqEB4`: Archive item identifier bỏ hậu tố `J` của course 18.404J; cần giữ đối chiếu resource page. `XSUjp-cDyeY`, `J4gbaRyWpoM`: OCW có nhiều encode, ledger chọn đúng file link cụ thể.
- Ba frame OCW đã xem tại các mốc của `gnWKpHUj11w`, `7LyvAVjQUR8`, `muwNEvhy6Po` cho thấy giảng viên và bảng; frame `7LyvAVjQUR8` có một phần slide chiếu. Không thấy credit/copyright rõ trong **ba frame đó**; không suy ra cả video không có ngoại lệ.

## Phương pháp và mức tin cậy

- 35 ID được nối theo khóa `video_id` với selected CSV; các ledger annotation, MP4 HF và nguồn OCW đều 35 hàng, `id_diff=0`. Archive supplement có 27/27 hàng `ocw_uploaded_cc_by_nc_sa_original_file`; landmark có 3 hàng. Không tải trọn video về workspace.
- Script [kiểm annotation](../../multimodal-lecture-summarizer/experiments/scripts/audit_mitfld_selected_annotations.py) khóa SHA của selected list và revision, giới hạn JSON 2 MB/file, tính SHA-256, kiểm timing. Chạy hai lần cho cùng kết quả/ledger khóa; `python -m py_compile` đạt. Script [kiểm Archive metadata](../../multimodal-lecture-summarizer/experiments/scripts/audit_mitfld_archive_items.py) kiểm đúng tên MP4 và file `original` trên item API, không tải media. Bản 11:41 phân loại sai 2 hàng vì URL license dùng `http`; bản 11:43 sửa so domain/path, đạt 27/27 và là bằng chứng hiện dùng.
- `ffprobe` trên 35 HF MP4 chỉ xác nhận header/duration; ba cửa sổ FFmpeg dùng HTTP seek, 4 s, 4 frame xám 64×36 ở 1 fps và PCM mono 4 kHz. Tương quan cao là bằng chứng cục bộ, không phải chứng chỉ căn chỉnh toàn bài. Chưa đo network bytes.
- [OCW Terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) còn nêu điều kiện riêng cho AI training, và cảnh báo license có thể không bao trùm mọi quyền khác. Quyết định cho noncommercial evaluation, model development hoặc công bố media/GT cần phân loại mục đích sử dụng cụ thể; báo cáo không suy ra quyền tái phân phối từ metadata.

## Việc còn cần làm trước D2

1. Với chính 35 ID: rà credit/ngoại lệ hình và tiếng tại các đoạn/slide có nguy cơ, ghi mức bao phủ từng video; kiểm binary/status và thêm nhiều mốc decoded đầu–giữa–cuối trên OCW MP4 để chứng minh offset ổn định.
2. Lấy bằng chứng từ tác giả về quy trình, rubric, QC, phiên bản media/time origin và giấy phép `frags`/transcript/HF MP4; hoặc tạo GT độc lập có quy trình và quyền rõ ràng. Không coi file tồn tại là expert chapter GT.
3. Chỉ khi có thất bại xác định, ghi attrition và xét reserve tiếp theo **cùng khóa/split** theo thứ tự đã khóa. Sau khi biết số bài/khóa sống sót, sửa master protocol có ngày nếu chuyển nguồn primary từ YTSeg sang MITFLD, rồi mới xét D2.

## Câu hỏi chưa giải quyết

1. Từng video có thành phần bên thứ ba nào vượt ngoài quyền OCW/item hay yêu cầu credit riêng không?
2. `frags` được tạo và kiểm định thế nào, theo giấy phép nào, có tương đương chapter GT của RQ1 không?
3. Sau decoded alignment và quyền/GT cấp file, còn bao nhiêu bài trong 35 (hoặc reserve cùng khóa) đủ điều kiện và bao nhiêu khóa độc lập?
