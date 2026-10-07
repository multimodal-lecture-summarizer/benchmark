# RQ1 Open Yale: QA mẫu 9 khóa trên MOV 640×360

**Kiểm:** 2026-09-28, Asia/Bangkok. Tiếp nối [sàng lọc 226 bài](./rq1-yale-followup-260928-1937-hd-media-rights-gt-split-report.md). Official RQ1 giữ chapter GT có sẵn của Yale. Đây là QA chọn nguồn, không phải GT mới, D2 hay kết quả 04a/04b.

**Phạm vi sử dụng do người dùng chốt lúc 20:04:** xử lý video Yale **nội bộ**, chỉ công bố số liệu/biểu đồ; không phát hành lại video, frame, clip hoặc dữ liệu trích xuất. Quyền cần đánh giá theo phạm vi này và giả định nghiên cứu phi thương mại; nếu mục đích thay đổi, rà lại. Phạm vi hẹp hơn không tự cấp phép cho thành phần bên thứ ba.

## Kết luận ngắn

- **Media:** 9/9 MOV mẫu giải mã được audio tại một boundary; 18/18 khung hình tại hai thời điểm/bài giải mã ở 640×360. Tín hiệu bảng viết có ở một số khóa, nhưng chưa đo OCR và không có slide đọc được trong 18 frame.
- **GT:** một số boundary có câu chuyển chủ đề rất gần mốc Yale; vài mốc chỉ phù hợp chủ đề rộng trong clip 36 s. `tiny.en` và cửa sổ cục bộ không chứng minh sai số ±3 s; chưa có audit toàn timeline.
- **Quyền:** không bài nào trong 9 được xác nhận `rights_pass`. Ba bài văn học có dấu hiệu rõ cần giữ lại để kiểm quyền thành phần, một bài kinh tế cần kiểm nguồn biểu đồ, năm bài còn lại chưa rõ. Quét chỉ tìm câu thông báo trên trang đã bỏ sót rủi ro từ transcript/handout.
- **Đếm:** 177 bài từ báo cáo trước vẫn chỉ là tập ưu tiên sàng lọc. QA 9 bài không cho phép suy ra số đủ quyền, chất lượng GT hoặc split D2. **Official eligible = 0 confirmed.**

## Chọn mẫu và giới hạn

[Manifest 9 bài](./rq1-yale-260928-1952-nine-course-qa-sample.csv), SHA-256 `5A5963776FB754A01C7968492C3FD5712C70F1F185E1E8B26625EA012C63853D`: chọn một bài/khóa bằng SHA-256 nhỏ nhất của `rq1-yale-260928-1952|course_id:lecture_no` trong các dòng không có cờ của **ledger mobile cũ** và không có thông báo non-CC rõ trên trang. Tập đầu vào thực tế là **176**, không phải 177: PHYS 201 L25 vẫn mang cờ 404 trong ledger cũ dù đường media đã sửa trước đó. Nếu tính L25, nó sẽ thắng phép chọn hash cho PHYS 201; vì 9 ID đã được chốt và kiểm, giữ nguyên mẫu và ghi sai lệch này. Không dùng sample làm ước lượng ngẫu nhiên của 177 hoặc thay ID theo kết quả QA.

| Khóa | Bài | Boundary kiểm (s) | Kết quả quyền sơ bộ | Hình/GT cục bộ |
|---|---:|---:|---|---|
| ECON 159 | [L2](https://oyc.yale.edu/economics/econ-159/lecture-2) | 407 | chưa rõ | Giảng viên/bảng trống ở 2 frame; câu chuyển sang thành phần hình thức của trò chơi ~407,5 s. |
| ECON 251 | [L1](https://oyc.yale.edu/economics/econ-251/lecture-1) | 616 | kiểm nguồn biểu đồ | Frame chủ yếu giảng viên; audio chuyển sang lý thuyết tài chính quanh 616 s, chưa chỉ được onset phần “collateral”. |
| ECON 252 (2008) | [L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6) | 388 | chưa rõ | Một frame có công thức bảng bị cắt; audio khép bài trước rồi mở “efficient markets” sau ~390 s. |
| ENGL 220 | [L23](https://oyc.yale.edu/english/engl-220/lecture-23) | 117 | chưa rõ | Frame chủ yếu giảng viên; audio chuyển sang câu hỏi thời điểm viết *Samson Agonistes* sau ~117 s. |
| ENGL 291 | [L10](https://oyc.yale.edu/english/engl-291/lecture-10) | 505 | `rights_hold` | Frame chủ yếu giảng viên; clip còn nói về cách mở đoạn phân tích, chưa định được onset chủ đề thần học. |
| ENGL 300 | [L16](https://oyc.yale.edu/english/engl-300/lecture-16) | 572 | `rights_hold` | Phấn viết nhìn thấy nhưng nét nhỏ/nhạt; audio bắt đầu nói về hai tác giả và handout, phù hợp chủ đề rộng. |
| ENGL 310 | [L4](https://oyc.yale.edu/english/engl-310/lecture-4) | 388 | `rights_hold` | Frame chủ yếu giảng viên; audio tiếp tục Yeats, chưa định được onset riêng “King Goll”. |
| PHYS 200 | [L19](https://oyc.yale.edu/physics/phys-200/lecture-19) | 531 | chưa rõ | Công thức/sơ đồ lớn đọc được một phần; audio khép recap rồi chuyển câu hỏi mới ~532–547 s. |
| PHYS 201 | [L10](https://oyc.yale.edu/physics/phys-201/lecture-10) | 526 | chưa rõ | Công thức lớn thấy được, chữ nhỏ mờ/che; audio chuyển sang solenoid ~526–540 s. |

## Quyền: cảnh báo trên nội dung không hiện ở dòng Credits

Cả 9 trang bài trả HTTP 200 và không có mục Credits/ngoại lệ quyền riêng trong nội dung bài sau khi bỏ footer chung. Tuy nhiên [Yale Terms](https://oyc.yale.edu/terms) nói giấy phép CC BY-NC-SA áp dụng cho **phần lớn** nội dung, không tự bao gồm thành phần bên thứ ba; Yale có thể đã dùng phép riêng/fair use không chuyển cho người tái sử dụng. Do đó “không có Credits” không đồng nghĩa quyền video đã sạch.

- [ENGL 291 L10](https://oyc.yale.edu/english/engl-291/lecture-10): transcript đọc đoạn từ *Franny and Zooey*; giữ `rights_hold` cho tái sử dụng nguyên video đến khi kiểm thành phần/quyền.
- [ENGL 300 L16](https://oyc.yale.edu/english/engl-300/lecture-16): transcript đọc Bakhtin/Jauss và [handout Yale](https://oyc.yale.edu/sites/default/files/jaussbakhtin_0.pdf) chứa đoạn trích; `rights_hold`.
- [ENGL 310 L4](https://oyc.yale.edu/english/engl-310/lecture-4): transcript chỉ hình Yeats và thơ; [handout Yale](https://oyc.yale.edu/sites/default/files/handout4_0.pdf) nêu nguồn hình bên ngoài; `rights_hold`.
- [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1): transcript nói tới biểu đồ Dow Jones/Case-Shiller; `visual_source_review`, chưa xác định quyền hình thực tế.

Đây là **cờ kiểm quyền cho xử lý nội bộ**, không phải kết luận vi phạm hay mặc định loại vĩnh viễn. Năm bài còn lại không có bằng chứng cấp quyền riêng; trạng thái vẫn `rights_unknown`. Chưa xem trọn media, chưa kiểm mọi handout/khung hình. Phạm vi công bố số liệu không kèm media đã được chốt; hồ sơ quyền cần ghi điều kiện phi thương mại, ghi công và cơ sở xử lý nội bộ với thành phần bên thứ ba.

## Hình và GT: bằng chứng kiểm cục bộ

18 frame lấy bằng FFmpeg từ MOV Yale tại `first_internal_boundary + 2 s` và khoảng giữa video cho mỗi bài. PHYS 200/201 có sơ đồ và công thức lớn đọc được một phần; ENGL 300 có chữ phấn nhưng độ tương phản thấp; ECON 252 có công thức ở mép bảng. Các frame ECON 159/251 và ENGL 220/291/310 chủ yếu là talking head hoặc bảng trống. **Không frame nào chứng minh slide đọc được**; đây không phải OCR CER, không chứng minh toàn video thiếu tín hiệu visual.

Thời điểm hai frame theo thứ tự từng bài trong bảng trên: ECON 159 `409/2064`, ECON 251 `618/2228`, ECON 252 `390/2049`, ENGL 220 `119/1322`, ENGL 291 `507/1425`, ENGL 300 `574/1505`, ENGL 310 `390/1371`, PHYS 200 `532/2157`, PHYS 201 `528/2120` giây (frame PHYS 200 gần mốc yêu cầu 533 s). Frame là mẫu giải mã cục bộ, không được lưu như dataset chính thức.

[Ledger audio 9 bài](./rq1-yale-260928-1952-nine-course-boundary-audio-qa.csv), SHA-256 `B03B78DE1C9F8D54793EF535F80C8AAF36C3F1EBB39BA47931F27367A213ABD6`: trích 36 s quanh chapter start đầu tiên từ đúng MOV, FFmpeg 9/9 exit 0, chạy Faster-Whisper `tiny.en` offline và đối chiếu tiêu đề Chapter 2 trong transcript Yale. Ledger lưu trạng thái và nhận xét diễn đạt lại, **không lưu câu ASR nguyên văn** theo phạm vi công bố đã chốt. Các câu chuyển chủ đề nêu ở bảng là chỉ dấu cục bộ; ASR segment có thể trùm qua mốc. Đặc biệt ENGL 291/310 chưa cung cấp dấu đủ rõ để định onset trong cửa sổ này. Không tính F1@3s hoặc gán `gt_pass` cho bài nào từ phép kiểm này.

### Phụ đề nhúng: có nhưng chưa dùng làm GT thời gian

[Yale Help](https://oyc.yale.edu/help) nói bản QuickTime băng thông cao có phụ đề. [Ledger kiểm caption](./rq1-yale-260928-1952-nine-course-mov-caption-qa.csv), SHA-256 `74253A9A6A89A571B429DBCC9A99AD39F30CD77BEA3DEE4C0AC67A5A469EC5B6` (không lưu lời phụ đề): 4/9 video mẫu trích được SRT từ luồng `mov_text` (ECON 252, ENGL 291, PHYS 200/201); 5 video còn lại có luồng `subtitle` nhưng FFprobe báo codec `unknown`, nên FFmpeg hiện không chuyển ra SRT. Các timestamp sau `ffmpeg -ss` remote seek chưa được chuẩn hóa với PTS nguồn; không lấy sự lệch giữa SRT trích đoạn và ASR làm sai số GT. Cần xác định codec/PTS và thử đối chiếu audio trước khi dùng caption để kiểm chapter hoặc làm transcript input.

## Quyết định và bước tiếp

Tiếp tục Yale như nguồn candidate vì đường MOV và publisher GT có thật. Trước D2, ghi rõ việc dùng phi thương mại/ghi công theo phạm vi công bố chỉ số liệu; kiểm quyền thành phần trên một cohort chọn trước, ưu tiên các khóa ít cờ nguồn; lấy nhiều frame cố định mỗi bài, đo OCR với bản chép tham chiếu; kiểm các boundary ngẫu nhiên bằng giải mã trực tiếp cùng trường hợp đuôi dài; hash full file và khóa split theo khóa/giảng viên. Không suy rộng 9 bài thành tỷ lệ loại cho 226 và không thay đổi GT Yale để tăng điểm. [Master RQ1](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) vẫn cần amendment trước official D2 do nguồn gốc kế hoạch là YTSeg.

## Câu hỏi chưa giải quyết

1. Các đoạn trích và hình nêu trên hiện diện chính xác ở đâu trong MOV, và cơ sở quyền nào cho phép xử lý nội bộ các thành phần đó?
2. Tỷ lệ frame có chữ hữu ích và OCR CER trên MOV 640×360 ở từng khóa là bao nhiêu?
3. Phân bố sai số boundary Yale ở một mẫu đủ lớn và độc lập là gì, nhất là các mốc chỉ khớp chủ đề rộng?
4. Sau quyền, OCR, GT, full-file hash và loại trùng, còn bao nhiêu khóa/giảng viên đủ để freeze split D2?
