# Cac bang danh gia can bo sung cho pipeline AI

Pham vi: chi tap trung vao cac mo hinh va thuat toan trong pipeline xu ly video. Khong danh gia fallback, CPU/GPU/RAM, UI, auth, admin hay deployment.

## Bang 1. Danh gia sau kien truc ASR tren TED-LIUM

Muc dich: trinh bay ket qua `01c` da hoan tat, tach khoi model mac dinh cua ung dung.

| Dataset | Model | WER (%) | CER (%) | RTF | Nhan xet |
| --- | --- | ---: | ---: | ---: | --- |
| TED-LIUM validation (507 unit) | Qwen3-ASR 0.6B | 3,91 | 2,27 | ~0,185 | Duoc chon duy nhat tren validation. |
| TED-LIUM native test (1.155 unit) | Qwen3-ASR 0.6B | 3,53 | 1,85 | ~0,190 | Diagnostic do lich su tiep xuc test. |

Ca sau candidate da hoan tat 3.042/3.042 validation va 6.930/6.930 native-test pair. Xem [bao cao `01c`](../results/asr-architecture-evaluation-2026-10-05.md) de lay bang day du va gioi han. Ung dung van mac dinh Faster-Whisper `base.en`; ket qua `01c` chua du dieu kien ket luan tren holdout doc lap.

## Bang 2. Danh gia VAD va loc khoang lang

Muc dich: chung minh buoc loc khoang lang giup transcript gon hon nhung khong cat nham loi noi.

| Video | Tong thoi luong | Thoi luong speech thuc te | Speech detect | Precision | Recall | Loi chinh |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Dung 5 video bai giang co khoang lang/chuyen slide.
- Tu annotate cac khoang co loi noi.
- Metric: speech precision, speech recall, ty le cat nham.

## Bang 3. Danh gia Scene Detection bang PySceneDetect

Muc dich: chung minh PySceneDetect bat duoc cac lan doi slide/canh quan trong.

| Video | Scene that | Scene phat hien | Precision | Recall | F1 | Loi chinh |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- TVSum hoac SumMe neu can benchmark cong khai.
- Tot nhat cho bao cao: 5 video lecture co slide, tu annotate thoi diem doi slide.
- Cho phep sai lech timestamp +/- 1-2 giay khi so voi ground truth.

## Bang 4. Danh gia Keyframe va CLIP Filtering

Muc dich: chung minh CLIP/filtering giu lai frame co y nghia, khong loai nham slide quan trong.

| Video | Keyframe ban dau | Keyframe sau loc | Keyframe dung | Keyframe thua | Keyframe bi loai nham | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- TVSum/SumMe: dung importance score lam ground truth cho frame quan trong.
- Video lecture tu annotate: danh dau cac slide/keyframe can giu.
- Metric: precision, recall, F1, ty le nen frame.

## Bang 5. Danh gia OCR PaddleOCR

Muc dich: chung minh OCR doc duoc noi dung chu tren slide.

| Anh slide | So dong chu that | So dong OCR dung | CER (%) | Word accuracy (%) | Loi thuong gap |
| --- | ---: | ---: | ---: | ---: | --- |
| Slide 1 | TBD | TBD | TBD | TBD | TBD |
| Slide 2 | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Lay keyframe slide that tu pipeline.
- Tu go ground truth text tren slide.
- Metric: CER, word accuracy, ty le dong OCR rong/sai.

## Bang 6. Danh gia Caption Florence-2

Muc dich: chung minh caption giup mo ta noi dung hinh anh va khong bia thong tin.

| Keyframe | Caption sinh ra | Dung noi dung? | Hallucination? | Diem huu ich 1-5 | Ghi chu |
| --- | --- | --- | --- | ---: | --- |
| Keyframe 1 | TBD | TBD | TBD | TBD | TBD |
| Keyframe 2 | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Dung keyframe that tu video lecture.
- Cham thu cong theo rubric 1-5.
- Tieu chi: dung noi dung, khong bia, huu ich cho summary.

## Bang 7. Danh gia Timeline Alignment

Muc dich: chung minh transcript duoc gan dung voi slide/keyframe theo thoi gian va noi dung.

| Video | Segment transcript | Slide/keyframe dung | Slide/keyframe du doan | Alignment dung? | Timestamp error (s) | Ghi chu |
| --- | --- | --- | --- | --- | ---: | --- |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Tu annotate mapping giua cau noi va slide dung tren 3-5 video.
- Metric: alignment accuracy, timestamp MAE.

## Bang 8. Danh gia Chapter Segmentation

Muc dich: chung minh thuat toan chia chuong tao boundary hop ly.

| Video | So chapter chuan | So chapter sinh ra | Boundary Precision | Boundary Recall | Boundary F1 | Sai lech TB (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Tu chia chapter chuan bang tay.
- Chap nhan boundary dung neu nam trong khoang +/- 15s hoac +/- 30s.
- Metric: boundary precision, recall, F1, mean absolute error.

## Bang 9. Danh gia Summary LLM

Muc dich: chung minh tom tat dung noi dung, du y chinh va de doc.

| Video | Input su dung | ROUGE-L | BERTScore | Factuality 1-5 | Coverage 1-5 | Coherence 1-5 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Video 1 | Transcript + OCR + caption | TBD | TBD | TBD | TBD | TBD |
| Video 2 | Transcript + OCR + caption | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Tu viet reference summary cho 5-10 video lecture.
- Neu khong co thoi gian, dung human evaluation 1-5.
- Metric: ROUGE-L, BERTScore, factuality, coverage, coherence.

## Bang 10. Danh gia RAG/Q&A

Muc dich: chung minh Q&A truy hoi dung doan noi dung va citation dung timestamp.

| Video | Cau hoi | Ground truth answer | Timestamp dung | Hit@3 | Hit@5 | Citation dung? | Answer faithful? |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| Video 1 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Video 2 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Dataset/phuong phap nen dung:
- Tu tao 5-10 cau hoi moi video dua tren transcript va slide.
- Ground truth gom cau tra loi ngan va timestamp dung.
- Metric: Hit@3, Hit@5, citation accuracy, answer faithfulness.

## Bang 11. Ablation: dong gop cua tung modality

Muc dich: chung minh pipeline la multimodal that su, khong chi dung transcript.

| Cau hinh | Input | Summary score | RAG Hit@5 | Citation accuracy | Nhan xet |
| --- | --- | ---: | ---: | ---: | --- |
| Audio only | Transcript | TBD | TBD | TBD | Baseline. |
| Visual only | OCR + caption | TBD | TBD | TBD | Kiem tra dong gop slide. |
| Audio + Visual | Transcript + OCR + caption | TBD | TBD | TBD | Cau hinh day du. |

Dataset/phuong phap nen dung:
- Dung cung mot bo video lecture.
- Chay 3 cau hinh dau vao va so sanh diem summary/RAG.
- Day la bang rat nen co khi bao ve tinh da phuong thuc.

## Bang 12. Tong hop metric theo stage

Muc dich: dat cuoi chuong thuc nghiem de tom tat toan bo pipeline.

| Stage | Model/thuat toan | Dataset/phuong phap | Metric chinh | Ket qua |
| --- | --- | --- | --- | --- |
| ASR | Sau kien truc `01c`; ung dung dung Faster-Whisper `base.en` | TED-LIUM validation/native test | WER, CER, RTF | Qwen3-ASR 0.6B: WER 3,91% validation, 3,53% native test diagnostic; [nguon](../results/asr-architecture-evaluation-2026-10-05.md) |
| VAD | Voice Activity Detection | Video lecture annotate | Precision, recall | TBD |
| Scene | PySceneDetect | TVSum/video lecture annotate | Precision, recall, F1 | TBD |
| Keyframe | CLIP filtering | TVSum/SumMe/video lecture | Precision, recall, F1 | TBD |
| OCR | PaddleOCR | Keyframe slide + ground truth text | CER, word accuracy | TBD |
| Caption | Florence-2 | Keyframe slide + human rubric | Accuracy, hallucination rate | TBD |
| Timeline | TF-IDF + temporal proximity | Manual alignment | Accuracy, MAE | TBD |
| Chapter | Slide/topic boundary | Manual chapter annotation | Boundary F1, MAE | TBD |
| Summary | LLM | Reference summary/human rubric | ROUGE-L, BERTScore, factuality | TBD |
| RAG/Q&A | ChromaDB retrieval + LLM | Manual QA set | Hit@3, Hit@5, citation accuracy | TBD |

## Thu tu uu tien neu khong du thoi gian

1. Dung ket qua ASR `01c` da co; khong can lap lai `01a`/`01b`.
2. Scene/keyframe: precision, recall, F1.
3. OCR/Caption: CER, human score, hallucination rate.
4. Timeline/chapter: timestamp MAE, boundary F1.
5. Summary: factuality, coverage, ROUGE-L/BERTScore neu co reference.
6. RAG/Q&A: Hit@3, Hit@5, citation accuracy.

## Goi y chon bo du lieu

| Muc can danh gia | Nen dung | Ly do |
| --- | --- | --- |
| ASR | TED-LIUM | Co audio bai noi tieng Anh va transcript tham chieu. |
| ASR gan demo | 5-10 video lecture tu chon | Sat voi pipeline bai giang cua he thong. |
| Scene/keyframe | TVSum hoac SumMe | Co frame/segment importance score cho video summarization. |
| OCR/Caption | Keyframe slide tu pipeline | Sat nhat voi bai toan doc slide cua he thong. |
| Timeline/chapter | Video lecture tu annotate | Can ground truth theo cau noi va slide, dataset chung kho khop. |
| Summary | Reference summary tu viet | De cham ROUGE-L/BERTScore va human factuality. |
| RAG/Q&A | Cau hoi tu tao theo video | De co ground truth answer va timestamp dung. |

## Ghi chu khi dua vao bao cao

- Khong nen dien so lieu neu chua chay that. Dung `TBD` hoac `N/A`.
- Nen uu tien bo video ngan 3-10 phut, tieng Anh, mot nguoi noi chinh, co slide.
- Moi bang nen co mot cau ket luan ngan sau bang: ket qua cho thay stage nao dang on, stage nao can cai thien.
- Neu chi kip lam it mau, hay noi ro day la pilot evaluation, chua phai benchmark quy mo lon.
