# Script Trinh Bay Bao Ve Do An Multimodal Lecture Video Summarization

## Tong Quan

Tai lieu nay dung de thuyet trinh theo deck Canva 20 slide: **Multimodal Lecture Video Summarization Using Artificial Intelligence Techniques**.

Muc tieu khi noi:

- Giai thich bai toan ro rang: video bai giang dai, nguoi hoc can tom tat, tim kiem va hoi dap nhanh.
- Chung minh he thong khong chi la "goi AI", ma la pipeline da phuong thuc gom audio, visual, OCR, fusion, LLM va RAG.
- Tach bach giua phan da trien khai, phan da co so lieu, phan prototype va phan can danh gia them.
- Khi gap cau hoi phan bien, uu tien tra loi trung thuc: metric nao co ground truth thi noi, metric nao chua co thi ghi la preliminary/planned.

Thoi luong khuyen nghi: **12-15 phut**, moi slide khoang 30-45 giay. Slide 9, 14, 18 nen noi cham hon vi day la phan hoi dong hay hoi.

## Can Chinh Nhe Truoc Khi Noi

Neu co the sua Canva, nen sua cac diem sau:

| Slide | Noi dung hien tai | Nen sua / cach noi an toan |
|---|---|---|
| 9 | "Parallel processing" | Doi thanh "Queued staged processing" hoac noi: "cac stage duoc day vao Celery queue, hien tai pipeline xu ly theo tung buoc". |
| 11 | "filtering out >90% near-duplicate keyframes" | Noi mem: "CLIP giam nhieu keyframe trung lap; ty le phu thuoc threshold va video". |
| 14, 18 | SlideSpeech, SSLectures | Chi noi neu co log/notebook nguon. Neu khong, noi la bo du lieu mo rong cho evaluation, khong phai evidence chinh. |
| 18 | Bang diem ASR, scene, chapter va summary cu | Chi giu ket qua ASR `01c`: Qwen3-ASR 0.6B validation WER 3,91%, native-test WER 3,53% diagnostic. Bo diem chapter va summary khoi slide cho den khi chay lai danh gia. |
| 19, 20 | Slide 19 noi co Q&A, slide 20 noi chua co free-form Q&A | Chon mot trang thai. Cach an toan: "RAG/Q&A co thiet ke va prototype, nhung can danh gia Hit@k/citation accuracy them". |

Luu y cho slide 18: ket qua chia chuong va tom tat cu da duoc rut de phan tich lai. Khong dua diem cu vao slide; xem [BENCHMARK.md](../BENCHMARK.md) de biet trang thai hien hanh.

## Loi Mo Dau

Kinh thua thay/co va hoi dong,

Nhom em xin trinh bay do an **Multimodal Lecture Video Summarization Using Artificial Intelligence Techniques**. Muc tieu cua he thong la xu ly video bai giang tieng Anh, trich xuat transcript, noi dung slide, khung hinh chinh, sau do hop nhat chung theo timeline de tao tom tat co cau truc, chapter co timestamp va co the mo rong sang hoi dap theo noi dung video.

Trong phan trinh bay, em se di theo 5 phan: ly do chon de tai, co so ly thuyet, thiet ke he thong, thuc nghiem danh gia va ket luan huong phat trien.

## Slide 1 - Cover

**Muc tieu slide:** Gioi thieu ten de tai, nhom, giang vien huong dan.

**Loi noi:**

Kinh thua thay/co, de tai cua nhom em la **Multimodal Lecture Video Summarization**, tam dich la he thong tom tat video bai giang da phuong thuc bang cac ky thuat tri tue nhan tao.

Khac voi tom tat van ban thong thuong, du lieu dau vao cua chung em la video, nen thong tin nam o nhieu kenh: loi noi cua giang vien, slide hien thi, bieu do, cong thuc va cac khung hinh quan trong. Vi vay he thong can ket hop xu ly am thanh, thi giac may tinh, OCR va mo hinh ngon ngu lon.

**Diem nhan:** Day la bai toan multimodal, khong phai speech-to-text don thuan.

## Slide 2 - Presentation Agenda

**Muc tieu slide:** Dat ky vong ve cau truc bai noi.

**Loi noi:**

Bai trinh bay gom 5 phan. Dau tien la phan introduction, neu boi canh, dong luc va pham vi nghien cuu. Tiep theo la theoretical foundation, noi ve cac chien luoc fusion va cac model AI duoc dung. Phan thu ba la system design, mo ta pipeline end-to-end tu video dau vao den JSON dau ra. Phan thu tu la experiments, gom ly do chon model, EDA va ket qua danh gia. Cuoi cung la application interface, ket qua dat duoc, han che va huong phat trien.

**Chuyen y:** "Em bat dau voi ly do vi sao speech-only summarization la chua du cho video bai giang."

## Slide 3 - Why Multimodal Summarization?

**Muc tieu slide:** Lam ro van de can giai quyet.

**Loi noi:**

Video dang la dinh dang pho bien trong giao duc truc tuyen, nhung no co mot han che lon: nguoi hoc phai xem tuyen tinh tu dau den cuoi. Khi can on lai mot y nho, tim mot cong thuc, hoac tra loi mot cau hoi cu the, viec tua video thu cong rat ton thoi gian.

Neu chi dung pipeline speech-only, tuc la ASR roi dua transcript vao NLP summarizer, he thong se bo qua nhieu thong tin quan trong tren man hinh. Vi du, giang vien co the noi "nhu cong thuc o day" hoac "nhin vao bieu do nay", nhung noi dung cong thuc va bieu do lai nam tren slide, khong nam trong loi noi.

Vi vay, huong tiep can cua nhom em la multimodal summarization: ket hop ASR, vision-language model va OCR. Muc tieu la bat chuoc cach nguoi hoc thuc su hieu bai: vua nghe, vua nhin slide, roi tong hop thanh noi dung co y nghia.

**Neu bi hoi "vi sao khong chi dung transcript":**

Transcript tot cho noi dung loi noi, nhung khong dam bao bat duoc diagram, table, cong thuc, keyword tren slide va cac reference kieu "this figure", "as shown here".

## Slide 4 - Research Objectives

**Muc tieu slide:** Neu muc tieu nghien cuu va muc tieu ky thuat.

**Loi noi:**

De tai co ba nhom muc tieu.

Thu nhat la nghien cuu ly thuyet va thuat toan. Nhom tim hieu ASR cho speech recognition, computer vision cho scene/keyframe, OCR va image captioning cho noi dung slide, cung voi LLM prompting de sinh tom tat.

Thu hai la thiet ke va trien khai mot pipeline end-to-end. Pipeline gom cac buoc: tach audio bang FFmpeg, tien xu ly va VAD, nhan dang giong noi bang Faster-Whisper, phat hien scene bang PySceneDetect, loc keyframe bang CLIP, trich xuat text bang PaddleOCR, sinh caption bang Florence-2 va hop nhat theo timeline.

Thu ba la tich hop va danh gia. He thong can dong bo audio va visual theo timestamp, sinh chapter co logic, va co kien truc backend/frontend on dinh de nguoi dung co the upload video, xem tien trinh va xem ket qua.

**Diem nhan:** Muc tieu khong phai train model tu dau, ma la thiet ke pipeline AI co the chay duoc va co danh gia theo tung module.

## Slide 5 - Scope & Research Methodology

**Muc tieu slide:** Khoanh pham vi de hoi dong khong ky vong qua rong.

**Loi noi:**

Pham vi hien tai cua de tai tap trung vao video bai giang tieng Anh, dau vao la file video hoac public YouTube link. Nhom gioi han video ngan, trung binh khoang 5 phut, de kiem soat latency va bo nho trong moi truong demo.

Domain chinh la academic lectures, seminars va slide-based presentations. Nghia la he thong toi uu cho video co loi noi ro, co slide hoac noi dung hien thi tren man hinh.

Ve phuong phap nghien cuu, nhom di theo chu trinh: literature review, pipeline design, implementation, sau do quantitative va qualitative evaluation. Hai dataset chinh duoc dung de lam co so la TED-LIUM cho ASR va TVSum cho phan tich keyframe/frame importance.

**Noi an toan:** Neu co nhac SlideSpeech/SSLectures, hay noi: "Day la bo du lieu mo rong cho huong danh gia sau; evidence chinh hien tai cua nhom tap trung vao TED-LIUM va TVSum."

## Slide 6 - Multimodal Fusion Strategies

**Muc tieu slide:** Giai thich vi tri khoa hoc cua cach fusion.

**Loi noi:**

Trong multimodal learning co ba huong fusion pho bien.

Early fusion tron du lieu ngay tu dau, truoc khi trich xuat dac trung. Cach nay don gian nhung kho ap dung voi video vi audio, text va image co dinh dang va tan so lay mau khac nhau.

Intermediate fusion ket hop cac hidden representation sau khi qua encoder rieng. Cach nay manh ve mat mo hinh hoc sau, nhung chi phi tinh toan cao va thuong can training/fine-tuning phuc tap.

Late fusion ket hop ket qua sau khi tung module da suy luan doc lap. He thong cua nhom em chu yeu di theo late fusion, nhung co temporal alignment nghiem ngat: transcript, OCR text va caption duoc can theo timestamp truoc khi dua vao LLM/RAG.

**Diem nhan:** Ly do chon late fusion la phu hop MVP: de debug, de thay module, chi phi thap, van giu duoc can chinh theo timeline.

## Slide 7 - Core AI Technology Stack

**Muc tieu slide:** Liet ke cong nghe AI va vai tro tung cong nghe.

**Loi noi:**

Stack AI cua he thong gom nhieu model phu trach tung tac vu cu the.

Voi audio, he thong dung Faster-Whisper de chuyen speech sang text va tao timestamp. VAD duoc dung de loai silence va giam ASR hallucination tren doan khong co loi noi.

Voi visual, PySceneDetect phat hien scene hoac slide change. Sau do CLIP ViT-B/32 duoc dung de do similarity ngữ nghia giua cac frame, giup loc keyframe trung lap. Florence-2 sinh mo ta visual cho keyframe, con PaddleOCR trich xuat text that tren slide.

Cuoi cung, cac ket qua nay duoc hop nhat va dua vao LLM de sinh summary, chapter va lam co so cho RAG.

**Ghi chu khi noi:** Khong can noi qua sau Transformer neu thoi gian ngan. Chi can noi cac model nay deu la backbone da pretrained, nhom tap trung vao tich hop va danh gia.

## Slide 8 - Temporal Alignment: The Multimodal Chunk

**Muc tieu slide:** Giai thich linh hon cua he thong: multimodal chunk.

**Loi noi:**

Diem cot loi cua he thong la khong dua tung modality rieng le vao LLM. Thay vao do, he thong tao ra **multimodal chunk**.

Moi chunk tuong ung voi mot khoang thoi gian trong video. Trong khoang do, he thong gom transcript tu Faster-Whisper, OCR text tu PaddleOCR va caption tu Florence-2. Neu utterance cua transcript nam trong cua so hien thi cua slide, hoac co temporal overlap du lon, no se duoc gan vao cung context chunk.

Nho cach nay, khi LLM sinh tom tat, no khong chi thay loi giang vien noi, ma con thay text tren slide va mo ta visual cung thoi diem. Dieu nay giup tom tat co ngu canh day du hon va giam viec bịa noi dung ngoai video.

**Neu bi hoi "alignment tinh bang gi":**

Tra loi ngan: "Can theo start_time/end_time; voi mot so thuc nghiem co the dung temporal overlap/IoU. Trong implementation hien tai, y tuong chinh la merge utterance va visual evidence theo cua so thoi gian."

## Slide 9 - End-to-End System Pipeline

**Muc tieu slide:** Mo ta luong xu ly tong the.

**Loi noi:**

Khi nguoi dung upload file MP4 hoac nhap YouTube link, backend tiep nhan request va day job vao Celery queue. Worker se xu ly cac stage AI nang, de API layer van phan hoi duoc cho frontend.

Pipeline bat dau bang FFmpeg de tach audio va video stream. Nhanh audio chay VAD va Faster-Whisper de tao transcript co timestamp. Nhanh visual chay scene detection, keyframe extraction, CLIP filtering, Florence-2 caption va PaddleOCR.

Sau do fusion layer hop nhat transcript, OCR va caption theo timeline. LLM nhan context da hop nhat de sinh abstractive summary va chapter split. Ket qua cuoi cung duoc chuan hoa thanh JSON de React frontend render video player, chapters, timestamps va keyframes.

**Noi an toan ve "parallel":**

Neu slide hien chu "Parallel processing", khi thuyet trinh nen noi: "Ve mat kien truc, cac tac vu nang duoc tach khoi API va dua vao queue. Trong ban hien tai, pipeline chay theo tung stage de de kiem soat va debug; cac stage co the tach song song hon trong huong phat trien."

## Slide 10 - Audio Processing Branch

**Muc tieu slide:** Giai thich ASR pipeline va vi sao chon Faster-Whisper.

**Loi noi:**

Nhanh audio gom ba buoc chinh.

Dau tien, FFmpeg chuyen audio ve WAV mono 16 kHz, phu hop voi speech-band content va input cua ASR model.

Tiep theo, VAD loai cac doan silence va non-speech noise. Buoc nay quan trong vi neu dua khoang lang vao ASR, model co the sinh text ao hoac lam tang thoi gian xu ly.

Cuoi cung, ung dung mac dinh Faster-Whisper base.en de transcribe audio va tra ve timestamp. Ket qua dau ra la timestamped transcript, day la mot nua audio-side cua multimodal chunk.

**So lieu co the noi neu can:**

Benchmark `01c` da danh gia du sau kien truc ASR tren 507 doan validation va 1.155 doan native test. Qwen3-ASR 0.6B dung dau validation WER 3,91%; native-test WER 3,53% la diagnostic. Nguon: [bao cao ASR `01c`](../results/asr-architecture-evaluation-2026-10-05.md). Ung dung van dung Faster-Whisper base.en; Qwen chua duoc trien khai vao ung dung.

## Slide 11 - Visual Processing Branch

**Muc tieu slide:** Giai thich visual pipeline.

**Loi noi:**

Nhanh visual bat dau voi PySceneDetect. Thu vien nay so sanh su thay doi noi dung hinh anh qua cac frame de phat hien scene boundary hoac slide-change boundary.

Sau khi co scene, he thong trich mot frame dai dien tu moi scene. Tuy nhien, nhieu frame co the gan nhu trung nhau, nen CLIP duoc dung de do semantic similarity. Khac voi so sanh pixel, CLIP giup biet hai frame co giong nhau ve y nghia hay khong.

Moi keyframe sau khi loc duoc dua vao Florence-2 de sinh caption va PaddleOCR de doc text tren slide. Hai nguon nay bo sung cho nhau: caption cho ngu canh visual, OCR cho text cu the.

**Noi an toan ve ti le loc:**

Khong nen khang dinh mot con so co dinh nhu ">90%" neu chua co bang ket qua. Noi: "Ty le giam phu thuoc threshold va loai video; muc tieu la loai keyframe trung lap nhung van giu frame dai dien."

## Slide 12 - Multimodal Fusion & Structured Output

**Muc tieu slide:** Giai thich output contract giua AI worker va frontend.

**Loi noi:**

Sau khi co transcript va visual evidence, fusion layer tao context chunk theo tung cua so thoi gian. Moi chunk gom start_time, end_time, transcript, OCR, caption va metadata ve keyframe.

Context nay duoc dua vao LLM prompt de tao chapter va summary. Output duoc chuan hoa thanh JSON gom title, chapters, start_time, end_time, transcript, OCR, caption va summary.

Viec chuan hoa JSON rat quan trong vi no tach AI pipeline khoi frontend. Frontend khong can biet chi tiet model nao chay ben trong; no chi can doc schema de hien thi chapter, dong bo player va show keyframes.

**Diem nhan:** Output co cau truc giup demo thuyet phuc hon mot doan text summary thuong.

## Slide 13 - Model Selection Rationale

**Muc tieu slide:** Giai thich vi sao chon tung model.

**Loi noi:**

Model selection cua nhom dua tren ba tieu chi: chat luong, toc do va kha nang chay trong moi truong tai nguyen gioi han.

Faster-Whisper base.en la cau hinh mac dinh hien tai cua ung dung. Thuc nghiem `01c` chon Qwen3-ASR 0.6B theo validation WER; ket qua nay chua thay doi cau hinh ung dung va khong phai ket luan tren holdout doc lap.

PySceneDetect duoc chon vi nhanh, on dinh va phu hop scene/slide boundary. CLIP duoc chon vi similarity theo ngu nghia tot hon pixel similarity. Florence-2 va PaddleOCR duoc ket hop de vua co mo ta visual, vua co text that tren slide.

LLM duoc dung o phan cuoi vi nhiem vu sinh tom tat va chia chapter can kha nang tong hop ngon ngu tu nhieu nguon.

**Neu bi hoi "co train model khong":**

Tra loi: "Trong pham vi do an, nhom chu yeu su dung pretrained models va tap trung vao orchestration, fusion, evaluation. Fine-tuning la huong phat trien sau."

## Slide 14 - Exploratory Data Analysis: Dataset Overview

**Muc tieu slide:** Cho thay nhom co nghien cuu du lieu, khong chi demo UI.

**Loi noi:**

Truoc khi tinh metric, nhom thuc hien EDA de hieu dac tinh du lieu. Ly do la neu khong biet do dai segment, speaking rate, frame importance distribution hay muc bo sung giua ASR va OCR, ta rat kho dat threshold hop ly cho VAD, keyframe selection va fusion.

TED-LIUM duoc dung cho ASR vi co audio bai noi tieng Anh va ground-truth transcript. TVSum duoc dung cho phan tich video summarization/keyframe vi co frame importance score do con nguoi gan nhan.

Voi cac dataset mo rong nhu SlideSpeech, neu hoi dong hoi, nen giai thich day la huong bo sung de kiem tra audio-visual complementarity tren slide thuc te. Tuy nhien, khi bao cao ket qua chinh thuc, nhom chi claim nhung dataset da co log va notebook ro rang.

**Cau noi de tranh bi bat loi:**

"Trong slide nay em tach ro EDA dataset va benchmark dataset. Khong phai dataset nao trong EDA cung da duoc dung de claim metric cuoi cung."

## Slide 15 - EDA: TED-LIUM

**Muc tieu slide:** Giai thich insight tu du lieu audio.

**Loi noi:**

Voi TED-LIUM, nhom phan tich 150 audio segments. Mean duration khoang 9.65 giay, median khoang 9.84 giay, speaking rate trung binh khoang 3.08 words per second, tuong duong khoang 185 words per minute.

Insight quan trong la du lieu speech co nhieu khoang dung ngan va toc do noi bien thien. Dieu nay anh huong truc tiep den ASR. Neu cat silence qua manh, co the mat ngu canh. Neu khong cat, ASR ton tai nguyen va co the hallucinate trong khoang lang.

Vi vay, nhom ket hop VAD voi word-level timestamps. VAD giup giam noise va timestamp giup fusion voi visual chinh xac hon.

**Neu bi hoi "tai sao TED-LIUM":**

TED-LIUM phu hop vi cung la dang speech/talk tieng Anh, co transcript chuan, co the tinh WER ro rang.

## Slide 16 - EDA: TVSum

**Muc tieu slide:** Giai thich insight tu frame importance.

**Loi noi:**

Voi TVSum, moi video co diem importance cho frame/segment do con nguoi gan. Nhom dung no de hieu phan phoi frame quan trong va cach chon threshold cho keyframe.

Ket qua cho thay neu dung absolute threshold qua cao, so frame giu lai rat it. Vi du nguong >= 3.0 chi giu mot ty le nho, con nguong >= 4.0 gan nhu qua chat. Dieu nay co nghia la mot hard threshold co the lam mat thong tin quan trong o nhung video co phan phoi diem thap.

Vì vay, cach hop ly hon la dung relative top-K% theo tung video, chang han top 10-20%, thay vi ap mot nguong co dinh cho moi video.

**Noi an toan:** TVSum khong phai lecture-only dataset. No tot cho frame importance/keyframe research, nhung khong du de ket luan toan bo visual pipeline cho video bai giang.

## Slide 17 - EDA: SlideSpeech / Audio-Visual Complementarity

**Muc tieu slide:** Neu y tuong transcript va slide text bo sung nhau.

**Loi noi:**

Slide nay minh muon chung minh mot gia thuyet quan trong: transcript va on-slide text khong trung nhau hoan toan. Trong bai giang, giang vien thuong noi giai thich, con slide chua keyword, cong thuc, bullet point hoac label hinh ve.

Neu Jaccard overlap giua ASR words va OCR words thap, dieu do cho thay hai nguon nay mang thong tin bo sung. Khi do, viec fusion ca ASR va OCR la co y nghia, thay vi chi chon mot nguon.

**Can noi rat than trong:**

"Day la phan phan tich bo sung/huong danh gia. Voi ket qua chinh thuc, nhom van can ghi ro du lieu, script va log de dam bao reproducibility."

Neu khong chac SlideSpeech co evidence trong repo, co the noi ngan hon:

"Phan nay minh dung de minh hoa ly do can fusion audio-visual. Ket qua chinh thuc trong bao cao can doi chieu voi artifact thuc nghiem."

## Slide 18 - Evaluation Datasets & Key Results

**Muc tieu slide:** Trinh bay ket qua, nhung khong overclaim.

**Loi noi khuyen nghi:**

Slide nay tong hop cac dataset va ket qua danh gia theo tung module. Voi ASR, TED-LIUM la benchmark chinh vi co transcript ground truth va co the tinh WER/RTF. Voi visual, TVSum ho tro phan tich frame importance va keyframe. Voi chapter/summary, can co reference boundary hoac reference summary thi moi tinh F1/ROUGE-L mot cach chinh thuc.

Ket qua ASR co the trinh bay la `01c`: sau candidate hoan tat tren TED-LIUM, Qwen3-ASR 0.6B dung dau validation WER 3,91%. Native test chi diagnostic va model ung dung van la Faster-Whisper base.en. Chapter va summary cho phan tich lai, chua trinh bay diem so.

**Cach noi an toan neu giu cac so tren slide:**

"Hien chi trinh bay ket qua ASR co bao cao va notebook doi chieu. Chapter va summary se duoc danh gia lai sau khi chot dataset, ground truth va giao thuc cung thang do."

**Neu bi hoi ve ROUGE-L ablation:**

Tra loi: "Audio-only cao hon visual-only la hop ly vi transcript chua noi dung tuyen tinh day du hon. Visual-only yeu vi slide/OCR thieu dien giai. Full multimodal khong nhat thiet tang manh tren ROUGE-L neu reference summary chu yeu bam transcript; loi ich multimodal can danh gia them bang factuality, coverage va citation grounding."

**Neu khong co evidence ro:** Nen sua slide thanh:

| Metric | Trang thai |
|---|---|
| ASR WER/RTF | `01c` hoan tat tren TED-LIUM; native test diagnostic; [bao cao](../results/asr-architecture-evaluation-2026-10-05.md) |
| TVSum EDA/keyframe | Da co phan tich du lieu |
| OCR CER | TBD |
| Caption faithfulness | TBD |
| RAG Hit@k | TBD |
| Summary factuality | TBD / can human rubric |

## Slide 19 - Application Interface Overview

**Muc tieu slide:** Chung minh he thong co san pham demo, khong chi pipeline nghien cuu.

**Loi noi:**

Ve phia nguoi hoc, he thong co cac man hinh chinh: landing page, dang nhap/dang ky, upload video hoac YouTube link, theo doi tien trinh xu ly, xem lich su va xem ket qua. Trang ket qua gom video player, chaptered summary, timestamp va keyframes.

Ve phia admin, he thong co dashboard thong ke, quan ly thanh vien, quan ly video, theo doi background jobs va cau hinh gioi han nhu dung luong file, dinh dang va thoi luong video.

Voi Q&A/RAG, nen noi theo trang thai that cua demo. Cach an toan la: "He thong da co thiet ke va prototype cho RAG/Q&A tren multimodal chunks; de claim chat luong chinh thuc, nhom can bo cau hoi ground truth va metric Hit@k/citation accuracy."

**Diem nhan:** UI giup bien pipeline AI thanh workflow nguoi dung co the dung.

## Slide 20 - Conclusion & Future Directions

**Muc tieu slide:** Ket lai bang thanh tuu, han che, huong phat trien.

**Loi noi:**

Tong ket lai, nhom da xay dung duoc kien truc microservice gom frontend, backend API va AI worker. Pipeline AI da ket hop duoc audio, visual, OCR, temporal fusion va LLM summarization de tao output co cau truc cho video bai giang.

Thanh tuu chinh cua do an la thiet ke duoc pipeline multimodal co kha nang mo rong, co co so dataset va co evaluation theo tung module. Dac biet, ASR da co benchmark ro hon voi TED-LIUM; visual/keyframe co EDA voi TVSum; cac module fusion va summary da co output schema de ket noi frontend.

Han che hien tai la speaker diarization chua hoan thien, mot so metric nhu OCR CER, caption faithfulness, RAG Hit@k va summary factuality can ground truth va annotation ro hon. Ngoai ra, mot so stage nang nhu Florence-2 phu thuoc RAM/GPU nen can toi uu them.

Huong phat trien tiep theo la hoan thien speaker diarization cho multi-speaker lecture, tach RAG indexing khoi critical path, xay bo benchmark end-to-end, va danh gia chat luong tom tat bang ca metric tu dong lan human rubric.

Em xin cam on thay/co va hoi dong da lang nghe. Nhom em san sang tra loi cau hoi.

## Cau Hoi Phan Bien Va Cach Tra Loi

### 1. Tai sao goi la multimodal?

Vi he thong khong chi dung transcript. He thong xu ly it nhat ba nguon thong tin: speech transcript tu ASR, visual/keyframe tu video, va text tren slide tu OCR. Cac nguon nay duoc hop nhat theo timestamp thanh multimodal chunk truoc khi dua vao LLM.

### 2. Tai sao khong dung moi LLM doc transcript?

LLM doc transcript chi nam duoc loi noi. Video bai giang co nhieu thong tin nam tren slide: keyword, cong thuc, bang, bieu do. Neu bo qua visual/OCR, summary co the thieu cac y ma giang vien chi tro bang hinh anh.

### 3. Tai sao chon Faster-Whisper?

Ung dung hien mac dinh Faster-Whisper base.en trong worker. Benchmark `01c` chon Qwen3-ASR 0.6B theo validation WER 3,91%, nhung chua doi model ung dung; native test cua `01c` chi diagnostic.

### 4. Tai sao dung TVSum trong khi de tai la lecture?

TVSum khong phai lecture-only dataset, nen khong dung de ket luan toan bo he thong bai giang. Nhom dung TVSum chu yeu de phan tich frame importance/keyframe vi dataset co human importance score. Voi lecture-specific evaluation, can them bo du lieu slide lecture co annotation rieng.

### 5. Speaker diarization da chay chua?

Trang thai an toan: phan speaker diarization chua nen claim la hoan thien. Scope hien tai uu tien video mot nguoi noi. Multi-speaker diarization la huong phat trien tiep theo.

### 6. RAG/Q&A da danh gia chua?

He thong co thiet ke/prototype RAG theo multimodal chunks. De danh gia chinh thuc, can bo cau hoi, dap an, chunk lien quan va metric nhu Hit@3, Hit@5, citation accuracy. Neu chua co bo nay thi khong nen claim RAG quality chinh thuc.

### 7. ROUGE-L co du de danh gia summary khong?

Khong du. ROUGE-L chi do overlap voi reference summary. Voi multimodal video, can them factuality, coverage, coherence va citation grounding, vi mot summary dung ve mat y nghia co the khong trung tu voi reference.

### 8. Neu full multimodal ROUGE-L khong cao hon audio-only thi sao?

Co the do reference summary chu yeu dua tren transcript, nen audio-only da rat manh theo ROUGE-L. Loi ich cua multimodal co the nam o coverage cua slide, cong thuc, bieu do va giam hallucination. Vi vay can danh gia them bang human rubric va grounded evidence, khong chi ROUGE-L.

### 9. He thong co production-ready khong?

Nen tra loi: "He thong o muc prototype/MVP phuc vu do an va demo nghien cuu. De production-ready can them security hardening, queue scaling, storage policy, monitoring, robust validation, cost control va benchmark end-to-end."

### 10. Dong gop chinh cua nhom la gi?

Dong gop chinh la thiet ke va tich hop pipeline tom tat video bai giang da phuong thuc: audio ASR, visual keyframe/OCR/caption, temporal fusion, structured summary va huong RAG/Q&A. Ngoai ra nhom co phan EDA va evaluation theo tung module de giai thich lua chon model.

## Ban Noi Rut Gon 3 Phut

Neu chi co thoi gian ngan:

Do an cua nhom em giai quyet bai toan tom tat video bai giang. Neu chi dung ASR va tom tat transcript, he thong se bo qua thong tin tren slide nhu cong thuc, bang, bieu do va keyword. Vi vay, nhom thiet ke huong multimodal: ket hop speech transcript, keyframe, OCR va image caption.

Pipeline bat dau bang upload video hoac YouTube link. FFmpeg tach audio, VAD loai silence, Faster-Whisper tao transcript co timestamp. Nhanh visual dung PySceneDetect de cat scene, CLIP de loc keyframe trung lap, Florence-2 de sinh caption va PaddleOCR de doc text tren slide. Sau do fusion layer can cac nguon nay theo timestamp thanh multimodal chunks. LLM dung cac chunks nay de sinh chaptered summary va output JSON cho frontend.

Ve thuc nghiem, nhom dung TED-LIUM cho ASR va TVSum cho phan tich frame importance/keyframe. Benchmark ASR `01c` da hoan tat sau candidate; Qwen3-ASR 0.6B dung dau theo validation WER, con native test chi diagnostic. Mot so metric nhu OCR CER, caption faithfulness, RAG Hit@k va summary factuality can bo ground truth rieng.

Ket qua hien tai la mot MVP co kien truc ro, co pipeline AI da phuong thuc, co giao dien upload/xem ket qua va co co so de mo rong sang RAG Q&A, multi-speaker diarization va benchmark end-to-end.

## Checklist Truoc Khi Bao Ve

- Dung [bao cao ASR `01c`](../results/asr-architecture-evaluation-2026-10-05.md) lam nguon WER/CER; sua slide 18 neu van ghi WER cu.
- Neu giu SlideSpeech/SSLectures, chuan bi duong dan dataset, script, log, output.
- Neu chua co evidence cho scene F1/chapter F1/ROUGE-L ablation, doi thanh preliminary hoac dua vao backup slide.
- Chuan bi demo video ngan 3-5 phut, audio ro, co slide de OCR/keyframe co y nghia.
- Chuan bi cau tra loi ve han che: speaker diarization, RAG evaluation, OCR ground truth, Florence-2 RAM.
- Khi demo loi hoac model fallback, noi ro day la fallback/prototype, khong goi la production.

## Tai Lieu / Evidence Nen Mo San

- [Báo cáo ASR `01c`](../results/asr-architecture-evaluation-2026-10-05.md)
- [Notebook ASR `01c`](../../experiments/notebooks/asr_architecture_colab_t4.ipynb)
- [Giao thức benchmark](../BENCHMARK.md) và [EDA dữ liệu](../DATASET_EDA.md)
- [Kiến trúc ứng dụng](../../../multimodal-lecture-summarizer/docs/current-system-architecture.md)
- [Worker ASR đang dùng](../../../multimodal-lecture-summarizer/ai_workers/modules/audio_v2/transcriber.py)

## Unresolved Questions

- SlideSpeech va SSLectures co phai dataset da chay that trong repo hien tai khong, hay chi la huong evaluation mo rong?
- Trang thai Q&A/RAG trong demo cuoi cung la "da co prototype" hay "planned"?
- Co can sua Canva de dong bo lai cac claim ve parallel processing, CLIP filtering va Q&A khong?
