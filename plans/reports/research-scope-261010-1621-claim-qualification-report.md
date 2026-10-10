# Qualification theo câu hỏi nghiên cứu và phạm vi kết luận

Ngày: 2026-10-10. Điều chỉnh cách dùng kết quả qualification: đánh giá một tuple **dataset revision × cohort × input × annotation target × comparison × claim**, thay cho nhãn READY/HOLD chung cho cả dataset. Báo cáo này xác định phạm vi có thể nghiên cứu; không xác nhận có điểm benchmark mới hoặc cohort đã freeze.

## Đóng góp chính của đồ án

**RQ2:** Với cùng generator và giới hạn phân bổ output trung gian/cuối, đo token thực dùng riêng, phân đoạn theo cấu trúc dự đoán từ nguồn có cải thiện độ đồng thuận với abstract của tác giả so với fixed chunks hay không, và thay đổi chi phí xử lý thế nào?

TIB hiện có đầu vào văn bản, abstract phát hành, EDA thực thi và audit quan hệ xuyên split. Đây là tuyến phù hợp nhất để trả lời RQ2 hiện tại. Không cần video gốc để trả lời câu hỏi text-only này. Thiếu reference factuality không chặn phép đo abstract agreement; nó giới hạn cách diễn giải. Kết quả âm hoặc không phân biệt được vẫn là kết quả nghiên cứu.

OCR và detection là bằng chứng hỗ trợ lựa chọn thành phần. Chúng chỉ trở thành đóng góp phương pháp độc lập nếu có giả thuyết/phương pháp mới và ablation thích hợp. Một bảng xếp hạng mô hình có sẵn tự nó chưa chứng minh tính mới của toàn đồ án. Không cộng các điểm ASR/OCR/detection thành bằng chứng hệ thống đầu-cuối tốt hơn.

## Ma trận dataset → câu hỏi → phép đo → kết luận

| Dataset | Câu hỏi có thể trả lời | Phạm vi bằng chứng hiện có | Phép đo phù hợp | Điều kiện tối thiểu còn lại | Kết luận được phép / chưa được phép |
|---|---|---|---|---|---|
| **TIB — RQ2 chính** | S3 có cải thiện creator-abstract agreement so với S1 với cùng generator và giới hạn phân bổ output? | 8.769 ứng viên văn bản; EDA và audit cross-split đã có. Chưa phải 8.769 lần đánh giá mô hình. | Paired ROUGE-L F1 chính; BERTScore phụ; chi phí/token thực tế. Source similarity chỉ là chỉ báo riêng. | Khóa ID/cohort và protocol; thực thi paired generation; lưu failure/coverage; phân tích độ nhạy nhóm transcript/series đã phát hiện. | So sánh abstract agreement trên cohort đã khai báo. Không suy ra factuality, chất lượng tóm tắt video, lợi ích hình ảnh/âm thanh hoặc unseen generalization. |
| **IIIT-CVID — OCR recognition hỗ trợ** | Ứng viên OCR nào nhận dạng tốt hơn trên crop bài giảng phát hành? | 15.379 crop validation đã được đọc trong EDA trước; không cần khôi phục video để chấm recognition trên crop. | Corpus CER chính; word accuracy phụ nếu chuẩn hóa cố định; latency cùng profile. | Khóa crop-ID/label pairing, normalizer và ứng viên; xử lý/nêu phạm vi crop có nhãn mâu thuẫn đã được gắn cờ; scorer/failure policy trước khi xem điểm mới. | Agreement với transcription phát hành trên crop cố định. Không suy ra text detection/spotting hoặc chất lượng OCR toàn video. Lỗi box frame không tự động chặn recognition của crop độc lập. |
| **IIIT-CVID — frame spotting mở rộng** | Pipeline nào phát hiện và nhận dạng text tốt hơn trên frame hợp lệ? | 5.455 frame qua geometry/nonblank-label checks; 120 dimension override dẫn xuất; 20 frame geometry HOLD. | Spotting Hmean với matching, IoU và text normalization khóa trước. | Chốt cohort hợp lệ theo ID, dùng metadata dẫn xuất có hash, công bố nhãn phát hành và reference exposure. Chỉ cần review source/leakage tương ứng nếu dùng train/test hay claim generalization. | Hiệu năng trên frame/cohort đã chọn. Không gọi test là unseen; không suy ra source-independent generalization khi chưa xác minh nguồn. |
| **LVVO — detection trên ảnh phát hành** | Detector cố định nào đạt độ chính xác tốt hơn trên 4 lớp của 1.000 ảnh LVVO? | 1.000 ảnh/label đã decode, 1.580 box; author release license đã kiểm tra. Source-video mapping không phải đầu vào bắt buộc của phép chấm ảnh. | COCO mAP@[.50:.95] chính, AP theo lớp; latency trên cùng thiết bị. | Khóa taxonomy/conversion/ID/scorer và ứng viên; không fine-tune/tune threshold trên evaluation labels. Giữ 21 ảnh không có box nếu đó là released negatives hợp lệ. Báo cáo phụ thuộc/near-duplicate và giới hạn CI. | So sánh agreement với box phát hành trên tập ảnh này. Không cần tuyên bố 139 nguồn độc lập. Quyền/phân tích video gốc là gate riêng của video endpoint. |
| **TED-LIUM — ASR diagnostic đã có** | Các kiến trúc khác nhau thế nào trên cohort đã đánh giá? | Kết quả diagnostic lịch sử và 42/50 reference mẫu hợp lệ. | WER/CER theo protocol của lần chạy; không đổi denominator của kết quả cũ bằng sample mới. | Dẫn đúng run/cohort/receipt và giới hạn; không lên lịch rerun ASR. | Bằng chứng hỗ trợ lựa chọn thành phần, giới hạn cohort đã đo. Missing Arrow không xóa bằng chứng lịch sử hợp lệ; 42 mẫu không đại diện full corpus. |
| **AccessMath — released annotations** | Annotation/keyframe và phân bố nội dung phát hành có đặc tính gì? | 12 video metadata, 129 XML keyframe/130 PNG; một PNG orphan. | Thống kê annotation/coverage, không giả tạo metric lựa chọn keyframe từ video. | Phân xử orphan theo đúng endpoint. Muốn so sánh keyframe extraction cần media/timebase và mục tiêu GT khớp nhãn tác giả. | Phân tích dataset/annotation hiện có. Chưa đủ cho kết luận thuật toán chọn keyframe hay required-board-state tốt hơn. |
| **LectureMath — released keyframes** | Nhãn summary/keyframe phát hành hỗ trợ tác vụ nào và phụ thuộc nguồn ra sao? | 34 video metadata, 330 PNG, thời gian milliseconds đã xác minh. | Thống kê keyframe/summary; metric thuật toán chỉ sau khi khớp nhãn và input. | Media/edited timeline cho extraction; source-group review nếu huấn luyện và kiểm tra. Không đòi required-state GT nếu câu hỏi được đổi sang đúng target summary tác giả và có protocol tương ứng. | Phân tích annotation và semantics đã xác minh. Chưa chứng minh required-state coverage hoặc chất lượng extraction từ video. |
| **MLPDataset — slide transition** | Detector nào tìm đúng chuyển slide theo annotation phát hành? | 333 source rows và 9.021 mốc; 315 video structurally valid. Chưa có frame/media alignment. | One-to-one boundary F1 với collar đã khóa; counts theo video. | Media đúng video/timebase và review anomaly chỉ trên cohort được chọn; không cần khôi phục mọi video trong release. | Hiện có thể kết luận về annotation statistics; benchmark transition còn chặn bởi input cần thiết. Không thay slide transition bằng generic scene cut. |
| **EduVidQA — QA, tách retrieval** | Với source context và reader cố định, pipeline nào tạo answer đồng thuận hơn với đáp án phát hành? | 5.234 QA và 296 video groups; context chưa khôi phục. | Answer token F1/EM đã chuẩn hóa, paired theo video; không dùng chúng làm retrieval relevance metric. | Khôi phục transcript/source context cho cohort đã chọn. Câu hỏi QA text-only không bắt buộc timestamp/video nếu protocol dùng full transcript; phải tránh answer/reference leakage. | QA answer agreement sau khi có context. Không cần evidence-span GT cho answer-only claim; vẫn cần GT độc lập để kết luận retrieval/evidence quality. |

Các số lượng structurally valid là **pool có thể chọn**, chưa phải quyết định chốt cohort. Không đổi ledger HOLD của một endpoint thành READY cho endpoint khác mà thiếu protocol của endpoint mới.

## Leakage và reference exposure theo loại claim

1. **Fixed-cohort comparison, không training/adaptation:** duplicate/source overlap ảnh hưởng trọng số mẫu và mức tổng quát hóa. Chúng không tự động làm vô hiệu mọi phép đo trên ảnh/crop phát hành. Công bố sample dependence; dùng source-group hoặc dependency-component sensitivity khi đã xác minh nhóm. Nếu chưa đủ nhóm đáng tin cậy, báo cáo điểm descriptive và paired differences, không dùng item-level CI để khẳng định population superiority.
2. **Fine-tuning hoặc lựa chọn hyperparameter:** train/dev/eval phải tách theo nguồn được xác minh; candidate selection không dùng eval labels. Claim này vẫn HOLD cho LVVO/OCR nếu các gate tương ứng chưa đạt.
3. **Unseen/external generalization:** cần holdout chưa dùng trong quá trình lựa chọn và đúng quyền truy cập theo protocol. Reference đã quan sát trong EDA phải được công bố; không tự biến lại thành unseen bằng cách đổi tên split.

## Thứ tự thực hiện và ngân sách

1. **Ưu tiên RQ2/TIB** như đóng góp chính; RQ4 đo chi phí ngay trên cùng paired run thay vì chờ tất cả visual datasets. Chỉ kết luận trade-off giữa abstract agreement và chi phí text pipeline; không tuyên bố Pareto của toàn bộ hệ thống multimodal.
2. **Ưu tiên phụ: OCR recognition trên crop**, vì input/nhãn sẵn có và không phụ thuộc video recovery. Dùng candidate registry hiện tại; không mở thêm tìm mô hình.
3. **LVVO ảnh tĩnh** là extension có thể lập protocol hẹp, không phải chờ mọi source video READY. Chưa lên lịch training/group-generalization benchmark.
4. MLP/board-video và EduVidQA cần input thiếu cho câu hỏi tương ứng. Chỉ phục hồi một cohort đáp ứng nghiên cứu đã chọn; không đặt mục tiêu tất cả media của mọi dataset trước khi có kết quả RQ2.

Mục tiêu dưới 12 giờ là **ngân sách chạy cần đo**, không phải thời gian đã được chứng minh. Trước khi khóa scope chạy Colab, đo throughput trên cùng cấu hình bằng một preflight giới hạn và giữ receipt. Ước lượng cả hai arm, long-input strata, scoring, load/download và retry; giữ dự phòng. Nếu dự báo vượt ngân sách, thiết kế lại cohort/cấu hình trước khi xem outcome; không tự chọn các mẫu đã có điểm đẹp hoặc bỏ các mẫu chậm/lỗi khỏi denominator. Không có benchmark nào được khởi động bởi báo cáo này.

## Trạng thái mới

- **EVIDENCE_AVAILABLE_FOR_SCOPED_PROTOCOL:** TIB abstract agreement; OCR crop recognition; LVVO released-image detection. Cần khóa protocol/cohort tương ứng trước khi chạy, không phải READY toàn diện.
- **HISTORICAL_DIAGNOSTIC_AVAILABLE:** TED-LIUM ASR; không rerun.
- **INPUT_BLOCKED_FOR_PROPOSED_COMPARISON:** MLP transition, board-video extraction, EduVidQA answer comparison khi thiếu source context.
- **ANNOTATION_ANALYSIS_AVAILABLE:** cả bảy dataset, với mẫu số và giới hạn đã ghi nhận.

## Câu hỏi chưa giải quyết

- Throughput Colab thực tế và cohort/cấu hình RQ2 nào đáp ứng ngân sách dưới 12 giờ?
- Scope phụ nào nên thực thi sau RQ2: OCR crop recognition hay LVVO image detection? Đây chưa phải quyết định chạy thêm benchmark.
- Với board tasks, target nào của đồ án thực sự trùng annotation summary/keyframe của tác giả?
