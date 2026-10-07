# Script trình bày trước giáo viên phản biện

Đề tài: **Multimodal Lecture Video Summarization Using Artificial Intelligence Techniques**

Mục tiêu khi trình bày:

- Nói rõ bài toán: video bài giảng có thông tin ở cả lời nói và hình ảnh.
- Chứng minh hệ thống không chỉ gọi LLM, mà có pipeline AI nhiều bước.
- Tách rõ: phần đã triển khai, phần đã có dữ liệu, phần prototype, phần cần đánh giá thêm.
- Tránh overclaim các metric chưa có ground truth hoặc log tái lập rõ.

Thời lượng khuyến nghị: **12-15 phút**. Nếu bị giới hạn thời gian, dùng bản rút gọn ở cuối file.

## Câu mở đầu

Kính thưa thầy cô và hội đồng,

Nhóm em xin trình bày đề tài **Multimodal Lecture Video Summarization Using Artificial Intelligence Techniques**, tức là hệ thống tóm tắt video bài giảng bằng các kỹ thuật trí tuệ nhân tạo đa phương thức.

Điểm xuất phát của nhóm em là: với video bài giảng, nếu chỉ chuyển lời nói thành văn bản rồi tóm tắt, hệ thống sẽ bỏ sót nhiều thông tin quan trọng trên slide như công thức, bảng, biểu đồ, từ khóa và các hình minh họa. Vì vậy nhóm em xây dựng một pipeline kết hợp **audio, visual, OCR, temporal fusion và LLM** để tạo bản tóm tắt có cấu trúc, có chapter theo timestamp và có nền tảng mở rộng sang Q&A.

Trong phần trình bày, em sẽ đi theo 5 phần: lý do chọn đề tài, cơ sở lý thuyết, thiết kế hệ thống, thực nghiệm đánh giá, giao diện ứng dụng và hướng phát triển.

## Slide 1 - Cover

Kính thưa thầy cô, đề tài của nhóm em là **Multimodal Lecture Video Summarization**, tập trung vào bài toán tóm tắt video bài giảng bằng AI.

Khác với tóm tắt văn bản thông thường, đầu vào của hệ thống là video. Trong video, thông tin không chỉ nằm ở lời nói của giảng viên, mà còn nằm ở slide, biểu đồ, công thức và hình ảnh đang hiển thị. Vì vậy hệ thống cần xử lý đồng thời nhiều nguồn dữ liệu rồi hợp nhất chúng theo thời gian.

Thông điệp chính của slide này là: đây là bài toán **multimodal summarization**, không phải chỉ là speech-to-text.

## Slide 2 - Presentation Agenda

Bài trình bày gồm 5 phần.

Phần đầu tiên là introduction, nói về động lực, mục tiêu và phạm vi đề tài. Phần thứ hai là theoretical foundation, trình bày các hướng fusion và stack AI chính. Phần thứ ba là system design, mô tả pipeline từ video đầu vào đến output JSON. Phần thứ tư là experiments, gồm chọn mô hình, EDA và kết quả đánh giá. Cuối cùng là application interface, kết luận, hạn chế và hướng phát triển.

Em sẽ bắt đầu bằng câu hỏi: tại sao chỉ dùng transcript là chưa đủ cho video bài giảng?

## Slide 3 - Why Multimodal Summarization?

Video đang là định dạng rất phổ biến trong học trực tuyến, nhưng nó có một vấn đề lớn: người học phải xem tuyến tính từ đầu đến cuối. Khi cần ôn lại một ý nhỏ, tìm một công thức hoặc kiểm tra một khái niệm, việc tua video thủ công rất tốn thời gian.

Nếu chỉ dùng speech-only pipeline, tức là ASR rồi đưa transcript vào summarizer, hệ thống có thể bỏ qua các thông tin nằm trên màn hình. Ví dụ giảng viên nói: "như công thức ở đây" hoặc "nhìn vào biểu đồ này", nhưng bản thân công thức và biểu đồ lại không xuất hiện trong transcript.

Vì vậy hướng tiếp cận của nhóm em là kết hợp transcript từ ASR, keyframe từ video, text từ OCR và caption từ vision-language model. Các nguồn này được căn chỉnh theo timestamp trước khi đưa vào LLM để sinh tóm tắt.

Nếu thầy cô hỏi vì sao không dùng transcript thôi, câu trả lời là: transcript tốt cho lời nói, nhưng không đủ để biểu diễn slide, hình, bảng, công thức và các visual reference trong bài giảng.

## Slide 4 - Research Objectives

Đề tài có ba nhóm mục tiêu.

Thứ nhất là nghiên cứu các kỹ thuật nền: speech recognition, scene detection, keyframe selection, OCR, image captioning, temporal alignment và LLM prompting.

Thứ hai là thiết kế và triển khai pipeline end-to-end. Pipeline gồm: tách audio bằng FFmpeg, xử lý VAD, nhận dạng lời nói bằng Faster-Whisper, phát hiện cảnh bằng PySceneDetect, lọc keyframe bằng CLIP, trích xuất text bằng PaddleOCR, sinh caption bằng Florence-2 và hợp nhất theo timeline.

Thứ ba là tích hợp vào hệ thống web để người dùng có thể upload video hoặc nhập YouTube link, theo dõi tiến trình, xem summary, chapter, keyframe và lịch sử xử lý.

Điểm cần nhấn mạnh: nhóm em không đặt mục tiêu train một foundation model mới. Đóng góp chính là **thiết kế pipeline, tích hợp các mô hình pretrained, căn chỉnh đa phương thức và đánh giá theo từng module**.

## Slide 5 - Scope & Research Methodology

Phạm vi hiện tại của đề tài tập trung vào video bài giảng tiếng Anh, độ dài ngắn khoảng 5 phút, một người nói là chính, âm thanh tương đối rõ và có slide hoặc nội dung hiển thị trên màn hình.

Việc giới hạn phạm vi này là có chủ đích. Nếu mở ngay sang video dài, nhiều người nói, nhiều ngôn ngữ và hình ảnh phức tạp, hệ thống sẽ rất khó đánh giá công bằng trong thời gian đồ án. Nhóm chọn phạm vi hẹp hơn để có thể kiểm soát latency, RAM và chất lượng đầu ra.

Về phương pháp, nhóm đi theo chu trình: literature review, pipeline design, implementation, sau đó quantitative và qualitative evaluation. Hai dataset chính được dùng làm cơ sở là TED-LIUM cho ASR và TVSum cho phân tích keyframe/frame importance.

Nếu slide có nhắc SlideSpeech hoặc SSLectures, em sẽ nói cẩn trọng: đây là dữ liệu mở rộng hoặc hướng đánh giá bổ sung; kết quả chính thức phải đi kèm notebook, log, ground truth và lệnh tái lập.

## Slide 6 - Multimodal Fusion Strategies

Trong multimodal learning có ba cách fusion phổ biến.

Early fusion là trộn dữ liệu ngay từ đầu. Cách này khó áp dụng cho video vì audio, text và image có định dạng, tần suất và chiều dữ liệu rất khác nhau.

Intermediate fusion là kết hợp hidden representation sau các encoder. Cách này mạnh nhưng thường cần training hoặc fine-tuning phức tạp, chi phí cao.

Late fusion là để từng module xử lý độc lập trước, rồi hợp nhất kết quả ở tầng quyết định. Hệ thống của nhóm em đi theo hướng late fusion có temporal alignment: transcript, OCR và caption được căn theo timestamp để tạo context chunk trước khi đưa vào LLM.

Lý do chọn hướng này là phù hợp với MVP: dễ debug, dễ thay model, chi phí thấp hơn và vẫn giữ được liên kết thời gian giữa các modality.

## Slide 7 - Core AI Technology Stack

Stack AI của hệ thống gồm nhiều model, mỗi model xử lý một nhiệm vụ cụ thể.

Với audio, hệ thống dùng Faster-Whisper để chuyển speech sang text và tạo timestamp. VAD được dùng để loại bỏ khoảng lặng, giảm thời gian xử lý và giảm nguy cơ ASR sinh text ảo ở đoạn không có lời nói.

Với visual, PySceneDetect phát hiện scene hoặc slide-change. CLIP ViT-B/32 đo similarity theo ngữ nghĩa để lọc keyframe trùng lặp. Florence-2 sinh mô tả hình ảnh, còn PaddleOCR đọc text thật trên slide.

Ở tầng cuối, các kết quả này được hợp nhất theo timeline, rồi đưa vào LLM để sinh summary và chapter. RAG/ChromaDB là nền tảng để mở rộng sang hỏi đáp theo nội dung video.

Điểm nên nói rõ: các model này là pretrained model; nhóm tập trung vào tích hợp, tối ưu luồng và đánh giá.

## Slide 8 - Temporal Alignment: The Multimodal Chunk

Đây là ý tưởng cốt lõi của hệ thống.

Thay vì đưa transcript, OCR và caption vào LLM một cách rời rạc, hệ thống tạo **multimodal chunk**. Mỗi chunk tương ứng với một khoảng thời gian trong video, gồm start time, end time, transcript, OCR text, visual caption và metadata keyframe.

Nếu một utterance trong transcript nằm trong thời gian hiển thị của một slide, hoặc overlap đủ lớn với scene window, utterance đó được gán vào cùng context chunk với slide. Nhờ vậy, khi LLM tóm tắt, nó có cả lời giảng viên nói và nội dung hiển thị cùng thời điểm.

Nếu thầy cô hỏi alignment tính bằng gì, em trả lời: hiện tại căn theo start_time/end_time và temporal overlap; hướng đánh giá tốt hơn là đo slide sync MAE hoặc temporal IoU với ground truth timestamp.

## Slide 9 - End-to-End System Pipeline

Khi người dùng upload file MP4 hoặc nhập YouTube link, backend tiếp nhận request, lưu metadata và đẩy job vào Celery queue. Worker xử lý các stage AI nặng để API layer vẫn phản hồi được cho frontend.

Pipeline bắt đầu bằng FFmpeg để tách audio và video stream. Nhánh audio chạy VAD và Faster-Whisper để tạo timestamped transcript. Nhánh visual chạy scene detection, keyframe extraction, CLIP filtering, Florence-2 captioning và PaddleOCR.

Sau đó fusion layer hợp nhất transcript, OCR và caption theo timeline. LLM nhận context đã hợp nhất để sinh abstractive summary và chapter split. Kết quả cuối được chuẩn hóa thành JSON để frontend render video player, chapters, timestamps và keyframes.

Lưu ý khi nói về chữ "parallel processing" trên slide: em nên nói là **về kiến trúc, các tác vụ nặng được tách khỏi API và đưa vào queue; trong bản hiện tại, pipeline xử lý theo từng stage để kiểm soát RAM/VRAM và dễ debug**. Không nên khẳng định audio và visual đang chạy song song nếu chưa đúng với code hiện tại.

## Slide 10 - Audio Processing Branch

Nhánh audio gồm ba bước chính.

Bước một là signal preparation. FFmpeg chuyển audio về WAV mono 16 kHz, phù hợp với speech-band content và input của ASR model.

Bước hai là Voice Activity Detection. VAD loại bỏ silence và non-speech noise trước khi nhận dạng. Bước này quan trọng vì khoảng lặng có thể làm tăng thời gian xử lý và đôi khi khiến ASR sinh hallucination.

Bước ba là speech recognition. Faster-Whisper transcribe audio và trả về transcript có timestamp. Output này là nửa audio-side của multimodal chunk.

Benchmark ASR `01c` đã chạy đủ sáu candidate trên 507 đoạn validation và 1.155 đoạn native test. Qwen3-ASR 0.6B đứng đầu theo validation WER 3,91%; native-test WER 3,53% là diagnostic. Ứng dụng vẫn dùng Faster-Whisper `base.en`. Nguồn: [báo cáo ASR `01c`](../results/asr-architecture-evaluation-2026-10-05.md).

## Slide 11 - Visual Processing Branch

Nhánh visual bắt đầu bằng PySceneDetect để phát hiện scene boundary hoặc slide-change boundary dựa trên thay đổi nội dung hình ảnh qua các frame.

Sau đó hệ thống trích keyframe đại diện cho mỗi scene. Vì nhiều keyframe có thể gần giống nhau, CLIP được dùng để đo semantic similarity. Điểm mạnh của CLIP là so sánh theo ý nghĩa, không chỉ theo pixel.

Mỗi keyframe sau khi lọc được đưa vào Florence-2 để sinh caption và PaddleOCR để đọc chữ trên slide. Hai nguồn này bổ sung cho nhau: caption cung cấp ngữ cảnh hình ảnh, OCR cung cấp text cụ thể.

Nếu slide ghi "filtering out >90% near-duplicate keyframes", em nên nói mềm hơn: **CLIP giúp giảm nhiều keyframe trùng lặp; tỷ lệ cụ thể phụ thuộc threshold và từng video**. Tránh nói như một kết quả cố định nếu chưa có bảng đo chính thức.

## Slide 12 - Multimodal Fusion & Structured Output

Sau khi có transcript và visual evidence, fusion layer tạo context chunk theo từng cửa sổ thời gian. Mỗi chunk gồm transcript, OCR, caption và thông tin keyframe.

Context này được đưa vào LLM prompt để tạo title, chapter và summary. Output được chuẩn hóa thành JSON gồm title, chapters, start_time, end_time, transcript, OCR, caption và summary.

Việc chuẩn hóa JSON rất quan trọng vì nó tách AI pipeline khỏi frontend. Frontend không cần biết model nào chạy bên trong; nó chỉ cần đọc schema để hiển thị chapter, đồng bộ video player và show keyframe.

Điểm cần nhấn: output có cấu trúc giúp hệ thống hữu ích hơn một đoạn summary thuần văn bản.

## Slide 13 - Model Selection Rationale

Việc chọn model của nhóm dựa trên ba tiêu chí: chất lượng, tốc độ và khả năng chạy trong môi trường tài nguyên giới hạn.

Faster-Whisper `base.en` là mặc định hiện tại của worker. Benchmark `01c` chọn Qwen3-ASR 0.6B theo WER validation nhưng chưa đổi cấu hình ứng dụng; native test chỉ diagnostic. PySceneDetect được chọn để phát hiện scene hoặc slide boundary. CLIP so sánh keyframe theo ngữ nghĩa; Florence-2 và PaddleOCR cung cấp caption và text trên slide.

LLM được dùng ở cuối vì nhiệm vụ sinh summary và chapter cần khả năng tổng hợp ngôn ngữ từ nhiều nguồn.

Nếu bị hỏi có train model không, câu trả lời là: trong phạm vi đồ án, nhóm chủ yếu dùng pretrained models và tập trung vào orchestration, temporal fusion, evaluation và sản phẩm demo. Fine-tuning là hướng phát triển sau.

## Slide 14 - Exploratory Data Analysis: Dataset Overview

Trước khi tính metric, nhóm thực hiện EDA để hiểu đặc tính dữ liệu. Nếu không biết phân phối độ dài segment, tốc độ nói, điểm quan trọng của frame hoặc mức bổ sung giữa ASR và OCR, rất khó đặt threshold hợp lý cho VAD, keyframe selection và fusion.

TED-LIUM được dùng cho ASR vì có audio bài nói tiếng Anh và ground-truth transcript, nên có thể tính WER rõ ràng. TVSum được dùng cho phân tích keyframe vì có human importance score ở cấp frame/video segment.

Với các dataset mở rộng như SlideSpeech hoặc SSLectures, em nên nói: các dataset này phục vụ phân tích bổ sung hoặc hướng đánh giá tiếp theo. Metric chính thức chỉ nên claim khi có đủ dữ liệu, script, log và ground truth.

Câu nói an toàn: **Trong slide này em tách rõ EDA dataset và benchmark dataset. Không phải dataset nào xuất hiện trong EDA cũng đã được dùng để claim metric cuối cùng.**

## Slide 15 - EDA: TED-LIUM

Với TED-LIUM, nhóm phân tích 150 audio segments. Thời lượng trung bình khoảng 9.65 giây, median khoảng 9.84 giây. Tốc độ nói trung bình khoảng 3.08 words per second, tương đương khoảng 185 words per minute.

Insight quan trọng là speech có nhiều khoảng dừng ngắn và tốc độ nói thay đổi. Điều này ảnh hưởng trực tiếp đến ASR. Nếu cắt silence quá mạnh, hệ thống có thể mất ngữ cảnh. Nếu không cắt, ASR tốn tài nguyên và dễ sinh lỗi trên khoảng lặng.

Vì vậy nhóm kết hợp VAD với timestamp của Faster-Whisper. VAD giúp giảm noise, còn timestamp giúp fusion với visual chính xác hơn.

Nếu bị hỏi vì sao dùng TED-LIUM, em trả lời: vì TED-LIUM gần với dạng talk/lecture tiếng Anh, có transcript chuẩn, phù hợp để đánh giá WER.

## Slide 16 - EDA: TVSum

TVSum có 50 video với điểm importance do con người gán. Nhóm dùng nó để hiểu phân phối frame importance và cách chọn keyframe.

Kết quả quan trọng là nếu dùng ngưỡng tuyệt đối quá cứng, hệ thống có thể giữ quá ít hoặc quá nhiều frame tùy video. Vì vậy cách hợp lý hơn là dùng relative top-K theo từng video, ví dụ top 10-20%, thay vì áp một threshold cố định cho mọi video.

Cần nói rõ: TVSum không phải lecture-only dataset, nên không dùng nó để kết luận toàn bộ chất lượng của hệ thống bài giảng. Nó phù hợp hơn cho phân tích frame importance và keyframe selection.

## Slide 17 - EDA: SlideSpeech / Audio-Visual Complementarity

Slide này dùng để minh họa giả thuyết cốt lõi: transcript và on-slide text không trùng nhau hoàn toàn.

Trong bài giảng, giảng viên thường nói phần diễn giải, còn slide chứa keyword, bullet point, công thức hoặc label hình vẽ. Nếu overlap giữa ASR words và OCR words thấp, điều đó cho thấy hai nguồn thông tin mang tính bổ sung.

Vì vậy nhóm không xem OCR là bản sao của transcript. Thay vào đó, cả ASR và OCR được đưa vào multimodal chunk để LLM có context đầy đủ hơn.

Nói cẩn trọng: **Phần này là phân tích bổ sung để củng cố lý do cần fusion. Với kết quả chính thức, nhóm cần ghi rõ dataset, script và log tái lập.**

## Slide 18 - Evaluation Datasets & Key Results

Đây là slide dễ bị hỏi nhất, nên cần nói chậm và rõ.

Slide này tổng hợp hướng đánh giá theo từng module. Với ASR, báo cáo `01c` ghi đủ WER/CER/RTF của sáu candidate trên TED-LIUM; Qwen3-ASR 0.6B đứng đầu validation WER 3,91% và native test chỉ diagnostic. Với visual, TVSum hỗ trợ phân tích keyframe/frame importance. Với chapter và summary, cần có reference boundary hoặc reference summary thì mới tính F1/ROUGE-L một cách chính thức.

Cách nói an toàn nếu giữ các con số trên slide:

**Các con số ở đây là kết quả thực nghiệm nội bộ theo các evaluation scripts của nhóm. Điểm em muốn nhấn mạnh không phải là chúng đã bao phủ mọi trường hợp, mà là nhóm đã tách evaluation theo module: ASR dùng WER/RTF, scene dùng F1, chapter dùng boundary F1, summary dùng ROUGE-L. Trong báo cáo cuối, mỗi metric cần đi kèm dataset, ground truth, cấu hình model và lệnh tái lập.**

Nếu thầy cô hỏi vì sao multimodal ROUGE-L không cao hơn audio-only, trả lời:

ROUGE-L đo overlap với reference text. Nếu reference summary chủ yếu bám transcript, audio-only có thể đã rất mạnh. Lợi ích của multimodal có thể nằm ở coverage của slide, công thức, biểu đồ và giảm hallucination. Vì vậy ngoài ROUGE-L, cần thêm human rubric, factuality, coverage và citation grounding.

Nếu chưa chắc nguồn của Scene F1, Chapter F1 hoặc ROUGE-L, không nên nói đó là kết quả chính thức. Hãy gọi là **preliminary/internal experiment**.

## Slide 19 - Application Interface Overview

Phần này chứng minh hệ thống không chỉ là notebook nghiên cứu, mà đã được tích hợp thành workflow người dùng.

Với learner-facing UI, người dùng có thể đăng nhập, upload video hoặc nhập YouTube link, theo dõi tiến trình xử lý, xem lịch sử, xem video kèm chaptered summary, timestamp và keyframes.

Với administrator-facing UI, hệ thống có dashboard thống kê, quản lý người dùng, quản lý video, theo dõi background jobs, log lỗi và cấu hình giới hạn như thời lượng, dung lượng và định dạng file.

Với Q&A/RAG, nên nói đúng trạng thái hiện tại: **hệ thống đã có thiết kế và nền tảng RAG trên multimodal chunks; để claim chất lượng Q&A chính thức, nhóm cần bộ câu hỏi ground truth và metric như Hit@k hoặc citation accuracy**.

Điểm nhấn: UI biến pipeline AI thành sản phẩm demo mà người dùng có thể thao tác.

## Slide 20 - Conclusion & Future Directions

Tổng kết lại, nhóm đã xây dựng một hệ thống tóm tắt video bài giảng theo kiến trúc web gồm frontend, backend API và AI worker. Pipeline AI kết hợp audio, visual, OCR, temporal fusion và LLM để tạo output có cấu trúc.

Thành tựu chính của đồ án là:

- Có pipeline multimodal từ video đầu vào đến summary/chapter/keyframe.
- Có kiến trúc queue để xử lý tác vụ AI nặng.
- Có EDA và benchmark định hướng theo từng module.
- Có giao diện demo cho người học và quản trị.

Hạn chế hiện tại là speaker diarization chưa hoàn thiện, Q&A/RAG chưa có đánh giá chính thức, một số metric cần ground truth rõ hơn, và các stage nặng như Florence-2 phụ thuộc RAM/GPU.

Hướng phát triển tiếp theo là hoàn thiện diarization cho multi-speaker lecture, tách RAG indexing khỏi critical path, xây benchmark end-to-end, và đánh giá summary bằng cả metric tự động lẫn human rubric.

Em xin cảm ơn thầy cô và hội đồng đã lắng nghe. Nhóm em sẵn sàng trả lời câu hỏi.

## Bản rút gọn 5 phút

Kính thưa thầy cô, đề tài của nhóm em là hệ thống tóm tắt video bài giảng đa phương thức.

Vấn đề nhóm em giải quyết là: video bài giảng không chỉ chứa lời nói, mà còn chứa slide, biểu đồ, công thức và chữ trên màn hình. Nếu chỉ dùng ASR rồi tóm tắt transcript, hệ thống có thể bỏ sót những phần quan trọng mà giảng viên chỉ nói gián tiếp, ví dụ "nhìn vào biểu đồ này".

Vì vậy nhóm em thiết kế một pipeline multimodal. Đầu vào là file video hoặc YouTube link. FFmpeg tách audio, VAD loại silence, Faster-Whisper tạo transcript có timestamp. Nhánh visual dùng PySceneDetect để phát hiện scene, CLIP để lọc keyframe trùng lặp, Florence-2 để sinh caption và PaddleOCR để đọc text trên slide.

Sau đó hệ thống tạo multimodal chunks theo timeline. Mỗi chunk gồm transcript, OCR, caption và timestamp. Các chunk này được đưa vào LLM để sinh title, summary và chapter. Output được chuẩn hóa thành JSON để frontend hiển thị video player, chapter, timestamp và keyframe.

Về đánh giá, nhóm dùng TED-LIUM cho ASR vì có transcript ground truth và dùng TVSum để phân tích frame importance/keyframe. Một số metric khác như OCR accuracy, RAG Hit@k, summary factuality và chapter boundary F1 cần thêm ground truth để claim chính thức, nên nhóm xem đó là hướng đánh giá tiếp theo.

Kết quả hiện tại là một MVP có pipeline rõ, có hệ thống web demo, có cơ sở dữ liệu và có hướng mở rộng sang RAG Q&A, multi-speaker diarization và benchmark end-to-end.

## Câu hỏi phản biện và cách trả lời

### 1. Vì sao gọi là multimodal?

Vì hệ thống dùng nhiều nguồn thông tin: speech transcript từ ASR, visual/keyframe từ video, text trên slide từ OCR và caption từ vision-language model. Các nguồn này được căn theo timestamp trước khi đưa vào LLM.

### 2. Vì sao không chỉ dùng LLM đọc transcript?

Transcript chỉ chứa lời nói. Video bài giảng còn có công thức, bảng, biểu đồ, keyword và nội dung slide. Nếu bỏ visual/OCR, summary có thể thiếu ý hoặc hiểu sai các câu như "as shown here".

### 3. Đóng góp chính của nhóm là gì?

Đóng góp chính là thiết kế và tích hợp pipeline tóm tắt video bài giảng đa phương thức: audio ASR, visual keyframe/OCR/caption, temporal fusion, structured summary và nền tảng RAG/Q&A. Nhóm không claim train foundation model mới.

### 4. Có train model không?

Trong phạm vi đồ án, nhóm dùng pretrained models và tập trung vào orchestration, alignment, evaluation và sản phẩm demo. Fine-tuning là hướng phát triển sau nếu có thêm dữ liệu và tài nguyên.

### 5. Pipeline có chạy song song không?

Về kiến trúc, các tác vụ nặng được đưa vào Celery queue để API không bị block. Nhưng trong bản hiện tại, các stage AI chính chạy tuần tự để kiểm soát RAM/VRAM và tránh lỗi tài nguyên. Đây là lựa chọn phù hợp với môi trường demo.

### 6. Speaker diarization đã hoàn thiện chưa?

Chưa nên claim hoàn thiện. Phạm vi hiện tại ưu tiên video một người nói. Multi-speaker diarization là hướng phát triển tiếp theo.

### 7. Q&A/RAG đã đánh giá chưa?

Hệ thống có thiết kế và nền tảng RAG theo multimodal chunks. Để đánh giá chính thức cần bộ câu hỏi, đáp án chuẩn, chunk liên quan và metric như Hit@3, Hit@5 hoặc citation accuracy.

### 8. ROUGE-L có đủ đánh giá summary không?

Không đủ. ROUGE-L chỉ đo overlap với reference text. Với video multimodal, cần thêm factuality, coverage, coherence, citation grounding và đánh giá bởi người dùng.

### 9. Vì sao dùng TVSum trong khi đề tài là lecture?

TVSum không phải lecture-only dataset, nên nhóm không dùng nó để kết luận toàn bộ hệ thống bài giảng. Nhóm dùng TVSum chủ yếu vì nó có human importance score, phù hợp để phân tích keyframe/frame importance.

### 10. Hệ thống đã production-ready chưa?

Chưa. Hệ thống đang ở mức MVP/prototype phục vụ đồ án và demo nghiên cứu. Để production-ready cần thêm security hardening, scaling queue, monitoring, cost control, robust validation và benchmark end-to-end.

## Checklist trước khi trình bày

- Thống nhất một nguồn số liệu chính thức cho slide 18.
- Nếu chưa có evidence rõ, gọi Scene F1, Chapter F1, ROUGE-L là preliminary/internal.
- Không nói audio và visual đang chạy song song nếu code hiện tại chạy tuần tự.
- Nói Q&A/RAG là thiết kế/prototype nếu chưa có bộ câu hỏi đánh giá.
- Chuẩn bị demo video 3-5 phút, tiếng Anh, một người nói, có slide rõ.
- Mở sẵn code `ai_workers/tasks.py`, `docs/DATASET_EDA.md`, `docs/BENCHMARK.md`, `docs/current-system-architecture.md`.

## Unresolved Questions

- Số liệu chính thức trên slide 18 sẽ lấy từ notebook/log nào?
- SlideSpeech và SSLectures đã có artifact chạy thật chưa, hay chỉ là hướng đánh giá mở rộng?
- Demo cuối cùng có bật Q&A/RAG không, hay chỉ demo summary/chapter/keyframe?
- Có sửa Canva để đồng bộ lại chữ "Parallel processing" và trạng thái Q&A không?
