# RQ1 MITFLD: quyền nội dung, căn chỉnh OCW và GT cho 35 bài đã chọn

**Trạng thái nguồn RQ1 2026-09-29:** MITFLD 35 vẫn là pilot. Người dùng đã dừng Yale và chọn [SSLectures làm nhánh khảo sát tiếp theo](./rq1-sslectures-260929-1414-route-decision-report.md); mẫu SSLectures 9 bài hiện `gt_provenance_hold`, chưa có D2/official. Các kết quả trong báo cáo này không đổi.

**Ngày kiểm:** 2026-09-28 (Asia/Bangkok); bổ sung rà quyền, pha A/V và gate GT trong cùng ngày. **Phạm vi:** đúng [cohort v2 gồm 35 ID thuộc 21 khóa](./mitfld-rq1-35-260928-1120-selected.csv), split **đề xuất** 19/8/8 video và 11/5/5 khóa train/validation/final_test. Không thay ID sau khi xem kết quả mô hình; chưa đóng băng D2. Người dùng đã quyết định **bỏ kiểm chứng bằng email**, nên không liên hệ tác giả.

**Quyết định tiếp theo ngày 2026-09-28:** giữ quy tắc official GT có sẵn; cohort MITFLD 35 bài là **pilot/diagnostic only** để kiểm nguồn, quyền, media và khả năng áp dụng endpoint. `frags` hiện chỉ dùng cho kiểm cấu trúc/căn media, không làm đáp án tính chapter score. Split 19/8/8 là thiết kế thử, không phải split final_test chính thức. Không tạo GT chapter mới để mở official D2 từ cohort này và không đưa bất kỳ kết quả MITFLD pilot nào vào official RQ1 leaderboard. Official RQ1 tiếp tục theo [master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) và gate GT/quyền/D2 hiện hành.

## 1. Quyền của thành phần nằm trong video

[Ledger 35 ID](./mitfld-rq1-35-260928-1214-content-rights-ledger.csv) (`SHA-256 7e499e20fdc747ee44853cad55c081efd9a77a4773f31bde57db70a426b35a92`) ghi 35/35 trang tài nguyên OCW trả HTTP 200, quét text trang và 34 transcript PDF URL liên kết với 32 ID. Các phép quét này không phải xem hết 37,04 giờ video. Metadata item/file của 27 MP4 Archive-hosted và đường dẫn OCW của 8 MP4 còn lại đã được kiểm trong [báo cáo trước](./rq1-qualification-260928-1126-mitfld-selected-35-report.md); giấy phép chung không tự bao phủ thành phần bị loại riêng.

**Một ngoại lệ CC trong video được xác nhận:** `JuKKBf-uSDI` (15.S08, train) hiển thị slide “Libra vs. China DCEP” tại 900 s trong MP4 OCW. [Slide Class 7 trang 5](https://ocw.mit.edu/courses/15-s08-fintech-shaping-the-financial-world-spring-2020/bf6652b320e525192082e047279ed17d_MIT15-S08S20_class7.pdf) ghi rõ nguồn Tabul8tor bị loại khỏi giấy phép CC. Giữ ID này ở trạng thái **hold quyền**, không dùng câu công bố “toàn MP4 được CC cấp phép”. Những trang khác trong slide deck cũng có cảnh báo; chưa đối chiếu từng trang với timeline. [Báo cáo quyền và chứng cứ](./researcher-260928-1214-mitfld-35-embedded-rights-report.md) ghi phương pháp và giới hạn.

Hai ID cần rà thêm: `9uqKU5ZDwfM` có ảnh tư liệu, nhóm người và công trình trong ba khung OCW tại 516/1297/1679 s; `neBeTYziSLo` có slide của người trình bày cùng biểu trưng Liên Hợp Quốc tại 1600 s. [Addendum khung](./mitfld-rq1-35-260928-1238-targeted-frame-rights-addendum.md) ghi chính xác quan sát. Nguồn/giấy phép thành phần chưa xác nhận; sự hiện diện của ảnh hay biểu trưng **không tự chứng minh** ngoại lệ hoặc vi phạm. 32 ID còn lại không có ngoại lệ rõ trong text đã quét, nhưng chưa rà toàn bộ hình/tiếng. Theo [điều khoản OCW](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), cần xét các loại trừ riêng và quyền khác khi dùng nội dung.

[FAQ của MIT OCW về nội dung “All rights reserved”](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content) xác nhận phần này nằm ngoài giấy phép CC chung; [FAQ về tải/sao chép/tái sử dụng](https://mitocw.zendesk.com/hc/en-us/articles/4414756158107-What-if-I-want-to-download-copy-modify-reuse-remix-or-redistribute-materials-that-include-all-rights-reserved-content) yêu cầu xét quyền riêng hoặc đánh giá ngoại lệ phù hợp với cách dùng cụ thể. Metadata CC ở cấp item không giải được ngoại lệ Tabul8tor của `JuKKBf-uSDI`. Trang [Chernobyl Trip Report](https://ocw.mit.edu/courses/22-01-introduction-to-nuclear-engineering-and-ionizing-radiation-fall-2016/resources/chernobyl-trip-report-by-jake-hecla/) không ghi nguồn/giấy phép từng ảnh trong các khung đã thấy. [Danh sách Selected Videos](https://ocw.mit.edu/courses/11-382-water-diplomacy-spring-2021/pages/selected-videos/) xác nhận `neBeTYziSLo` là bài trình bày sinh viên; [transcript OCW](https://ocw.mit.edu/courses/11-382-water-diplomacy-spring-2021/251fc14721efe9beb28c27477788b9bc_neBeTYziSLo.pdf) không phải giấy phép của slide/ảnh/biểu trưng. Cả ba ID vẫn chờ kiểm quyền theo từng thành phần; không gửi email theo quyết định đã khóa.

## 2. Căn chỉnh OCW MP4 tại các mốc `frags`

Đã đối chiếu đúng 35 MP4 OCW với bản MITFLD được pin tại revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec`. [Ledger thời lượng đã kiểm](./mitfld-rq1-35-260928-1231-ocw-duration-verified.csv) (`SHA-256 4e6c717236efbd14d02c013a1936cf890506b6c1f5f0bfe7b363e030f6dcff78`) có **35/35** thời lượng OCW qua `ffprobe`; một URL timeout ở batch đầu đã thành công khi retry riêng. Chênh lệch thời lượng container OCW–HF có trị tuyệt đối tối đa **0,096531 s**; mọi mốc `frags` cuối nằm trước thời lượng OCW, biên nhỏ nhất **36,055 s**. Thời lượng tương đương không chứng minh đồng bộ hình/tiếng, nên đã kiểm giải mã tiếp.

[Script đối chiếu](../../multimodal-lecture-summarizer/experiments/scripts/audit_mitfld_ocw_landmarks.py) lấy mốc dương đầu, giữa, cuối từ `frags` đã kiểm SHA theo từng ID. Mỗi mốc dùng cửa sổ 3 s, ba khung xám 64×36 ở 1 fps và PCM mono 4 kHz của cả HF và OCW. Ngưỡng gắn `local_av_match`: Pearson hình tối thiểu 0,95 và tương quan tiếng tối thiểu 0,90 sau tìm lag ±150 ms. Đây là **kiểm cục bộ ở 105 cửa sổ**, không chứng minh mọi giây, đồng nhất byte hay chất lượng semantic GT.

| Bằng chứng | Kết quả |
|---|---:|
| Lượt đầu: `local_av_match` / review / lỗi đọc từ xa | 86 / 3 / 16 trên 105 mốc |
| Retry đúng 16 mốc lỗi với timeout dài hơn | 16/16 thành `local_av_match` ở lần retry đầu; không còn lỗi giải mã |
| [Ledger hợp nhất](./mitfld-rq1-35-260928-1300-three-landmark-final.csv) (`SHA-256 fc62970ccb45a05869bb5f4f1562eb22d9cbae0a3208e416294d71d0d32d9a5f`) | **102 match, 3 review / 105 mốc**; 35/35 video có ít nhất một match, **33/35** match cả ba mốc |

Ba mốc review đều thuộc khóa `3.091`, gồm `tKyaGnPni3U` mốc cuối 2702 s và `DvGNpuan4rw` mốc đầu 73 s, giữa 1755 s. Ở mốc gốc, tương quan hình tối thiểu 0,906/0,977/0,933; tương quan tiếng 0,944/0,893/0,925; lag đều −197 mẫu ở 4 kHz (độ lớn **49,25 ms**). [Sáu cửa sổ ±5 s](./mitfld-rq1-35-260928-1250-low-correlation-neighbors.csv) (`SHA-256 a202165a51207f42221cdd0ca6e1610f18a7a0799ec7184895a36d5b8aaf5113`) cho ba match và ba review theo cùng ngưỡng; từng cặp vẫn có ít nhất một thành phần hình hoặc tiếng tương quan cao và cùng lag. Điều này hỗ trợ gần khớp cục bộ nhưng **không xóa ba cờ review ở mốc gốc**. Phép kiểm độ phân giải cao hơn cho hai ID được ghi ngay dưới đây.

Ledger lượt đầu [giữ nguyên](./mitfld-rq1-35-260928-1214-three-landmark-ledger.csv). [Ledger retry thô](./mitfld-rq1-35-260928-1245-three-landmark-verified.csv) giữ thông báo timeout cũ trong cột `error`; ledger hợp nhất đã chuyển nó sang `first_pass_error`, xóa `error` khi retry thành công. `retry_attempts=1` đúng 16 hàng, bằng 0 ở 89 hàng còn lại.

### Kiểm lại ba mốc review ở độ phân giải cao hơn

[Script kiểm pha có thể chạy lại](../../multimodal-lecture-summarizer/experiments/scripts/audit_mitfld_ocw_review_phase.py) khóa SHA của ledger nguồn và ledger 105 mốc, đọc đúng ba hàng `review_low_correlation`, giải mã mỗi cặp HF/OCW trong cửa sổ 5 s `[mốc−1, mốc+4]` thành 100 khung xám 160×90 ở 20 fps và 80.000 mẫu PCM mono 16 kHz. So 80 cặp khung trung tâm ở các dịch chuyển −3…+3 khung; tìm lag tiếng trong ±0,5 s. Chạy từ repo lồng bằng `python -m experiments.scripts.audit_mitfld_ocw_review_phase`; `python -m py_compile` đã đạt.

| Mốc | Lag tiếng OCW−HF | Tương quan tiếng sau lag | Dịch khung OCW tốt nhất | Trung vị tương quan hình: dịch −1 / không dịch |
|---|---:|---:|---:|---:|
| `tKyaGnPni3U` cuối 2702 s | −49,3125 ms | 0,992032 | −50 ms | 0,999033 / 0,961448 |
| `DvGNpuan4rw` đầu 73 s | −49,3125 ms | 0,983768 | −50 ms | 0,999533 / 0,996533 |
| `DvGNpuan4rw` giữa 1755 s | −49,3125 ms | 0,985981 | −50 ms | 0,998980 / 0,959929 |

[CSV phép đo mới](./mitfld-rq1-35-260928-review-phase-verified.csv) (`SHA-256 d04e7c003cfe1c659e281000d4d4cceb70e021e1cbe3c3137f85c6ad7a38450a`) giữ cả thống kê theo bảy dịch chuyển, SHA-256 của output hình/tiếng đã giải mã ở từng cửa sổ và dòng phiên bản FFmpeg. Các hash cửa sổ giúp phát hiện thay đổi khi chạy lại; **không phải hash toàn MP4** và URL OCW còn có thể đổi nội dung. Dấu âm nghĩa là nội dung OCW xuất hiện sớm hơn HF khoảng 50 ms trong ba cửa sổ này. Ở mốc giữa của `DvGNpuan4rw`, tương quan hình tối thiểu của 80 cặp sau dịch vẫn là 0,945197 dù phân vị 10% đạt 0,998113; không xóa outlier này. Bằng chứng mới giải thích ba cờ review bằng lệch pha cục bộ nhất quán và hỗ trợ **khớp A/V cục bộ sau bù pha**. Ledger gốc vẫn là **102/105 match theo phép so chưa bù**; không đổi thành 105/105 theo ngưỡng cũ, không suy ra đồng bộ toàn video hoặc nguyên nhân encode của lệch pha.

## 3. Nguồn gốc và quyền GT

[Báo cáo provenance](./gt-provenance-260928-1214-mitfld-35-report.md) xác nhận `frags` của 35 ID parse được, tổng **479 mốc thô**, nhưng [dataset card MITFLD](https://huggingface.co/datasets/robotwang/MITFLD), [repo tác giả](https://github.com/wjq1015-hku/lecture-fragmentation) và [abstract công bố](https://scholars.hkmu.edu.hk/en/publications/towards-key-point-identification-kpi-for-lecture-videos-approache/) trong phần truy cập được không xác nhận người gán, rubric, QC, `frags` tương đương chapter RQ1, hoặc giấy phép nhãn. Toàn văn ACM bị 403 trong phiên nghiên cứu; kết luận là **chưa có đủ bằng chứng**, không phải khẳng định tác giả không có quyền. `frags` chỉ được dùng để kiểm cấu trúc/căn media; **không dùng làm official chapter GT**.

Theo lựa chọn bỏ email, trước đó đã lập [quy trình GT chapter độc lập](./gt-independent-260928-1224-mitfld-35-protocol.md) và [CSV template trống](./mitfld-rq1-35-260928-1224-independent-gt-template.csv). Dự toán cũ **128–177 giờ người** cho ~37,04 giờ video; chưa có người gán, chấp thuận quyền nhãn hay một hàng GT mới. Sau quyết định pilot-only, đây là **phương án lưu để tham khảo, không triển khai cho official RQ1**.

**Gate protocol đã được quyết định:** [master plan RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) ghi `YTSeg official split plus frozen downloadable multimodal subset`; [kế hoạch pipeline, mục Frozen research decisions](../260921-1943-scientific-benchmark-pipeline/plan.md) khóa “Official/pre-existing labeled data only. No project-created GT ... in official evaluation.” Giữ nguyên cả hai. Official RQ1 chỉ dùng nhãn có sẵn đã kiểm nguồn gốc, quyền, chất lượng và media/split/D2; nếu không có tập phù hợp thì báo `not_eligible`, không nâng MITFLD pilot hoặc nhãn tự tạo thành GT chính thức.

## Quyết định hiện tại

| Trạng thái trên đúng 35 bài đã chọn | Số bài |
|---|---:|
| Hold quyền vì ngoại lệ CC đã thấy trong MP4 (`JuKKBf-uSDI`) | **1** |
| Còn pending quyền thành phần, đồng bộ toàn timeline và GT phù hợp | **34** |
| Đủ **toàn bộ** quyền + căn chỉnh + GT và thuộc nhánh official D2 | **0** |

**Không có bài nào bị thay/loại khỏi mẫu số 35** trong lượt kiểm này. “Pending” không có nghĩa đủ quyền. Nếu pilot cần thay bài đang hold, xét reserve kế tiếp **cùng khóa 15.S08/train** theo thứ tự đã khóa, rồi kiểm chính file thay thế; không chọn theo điểm mô hình. Không đóng băng split/D2 và không chạy official 04a/04b trên 35 ID này.

[Reserve đầu tiên cùng khóa/split](./mitfld-rq1-35-260928-1120-reserve-order.csv) là `uHUA6M1OEwk` (Class 9: Trading & Capital Markets). [Trang OCW](https://ocw.mit.edu/courses/15-s08-fintech-shaping-the-financial-world-spring-2020/pages/class-9-trading-capital-markets/) dẫn [MP4 cụ thể](https://archive.org/download/MIT15.S08S20/MIT15_S08S20_Class09_300k.mp4), nhưng [slide Class 9](https://ocw.mit.edu/courses/15-s08-fintech-shaping-the-financial-world-spring-2020/bb56a58d58d880fabe9cd5c46700096a_MIT15-S08S20_class9.pdf) cũng ghi nhiều thành phần bị loại khỏi CC (trang 6, 8, 11–14). Chưa đối chiếu các trang đó với MP4, chưa kiểm căn chỉnh hoặc GT cho reserve; **không tự động thay** `JuKKBf-uSDI` bằng ID này. Với [slide Class 7](https://ocw.mit.edu/courses/15-s08-fintech-shaping-the-financial-world-spring-2020/bf6652b320e525192082e047279ed17d_MIT15-S08S20_class7.pdf), ngoài trang 5 đã thấy ở 900 s còn có ngoại lệ ghi ở trang 8, 10, 12, 13, 15, 19–21, 24–25; số trang PDF không xác định mốc video, cần đối chiếu trực tiếp trước quyết định quyền.

**Công việc tiếp theo:** với MITFLD, chỉ tiếp tục kiểm quyền/credit và căn media ở phạm vi pilot cần thiết, giữ riêng artifact diagnostic, không chọn reserve theo điểm mô hình. Với official RQ1, tiếp tục xác minh nguồn GT chapter **có sẵn** theo master plan, quyền media/nhãn, chất lượng ranh giới, split độc lập và receipt D2; nếu không đạt thì báo `not_eligible`. Không tuyển annotator hoặc mở workflow GT độc lập cho official RQ1 theo quyết định này.

[Lượt rà nguồn GT có sẵn ngày 28-09](./rq1-preexisting-gt-260928-1843-source-rights-d2-qualification-report.md) đã đối chiếu một video Yale với mốc publisher, kiểm metadata quyền của YTSeg CC BY và kiểm toàn bộ CSV chapter SSLectures (1.378 bài/69 khóa, MD5 khớp bản phát hành, có lỗi nhãn và chênh timebase cần giải thích). Chưa nguồn nào vượt đồng thời các gate GT, quyền/media và split/D2; **official eligible vẫn bằng 0**. Báo cáo liên kết giữ bằng chứng theo từng nguồn và các bước kiểm tiếp, không thay đổi trạng thái pilot của 35 bài MITFLD.

## Câu hỏi chưa giải quyết

1. Phạm vi quyền của các thành phần bị loại/không rõ trong `JuKKBf-uSDI`, `9uqKU5ZDwfM`, `neBeTYziSLo` và những thành phần chưa thấy ở 32 video còn lại có đáp ứng cách dùng benchmark dự định không?
2. Ba mốc review khóa 3.091 đã khớp cục bộ sau bù pha ~50 ms; độ lệch này có ổn định trên toàn bộ hai video và các đoạn còn lại của 33 video khác không? Chưa có chứng cứ đồng bộ toàn timeline để gọi là đã căn chỉnh đủ cho freeze.
3. Nguồn nào trong phạm vi master plan có GT chapter có sẵn, đủ quyền và chất lượng cho official RQ1 sau khi kiểm D2?
