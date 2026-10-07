# Diem yeu cua pipeline xu ly AI hien tai

Ngay lap: 03/08/2026

Pham vi: chi danh gia pipeline AI trong `multimodal-lecture-summarizer/ai_workers` va phan ket noi ket qua ve backend. Khong danh gia UI, auth, admin, CORS, password reset hay quyen truy cap he thong.

Pipeline hien tai trong `ai_workers/tasks.py`:

`download/input -> audio ASR -> speaker diarization -> scene/keyframe -> semantic slide analysis -> timeline alignment -> LLM summarization -> RAG index -> return result`

## 1. Pipeline chay tuan tu, chua tan dung song song hoa nhu thiet ke

Trong `ai_workers/tasks.py`, cac stage duoc goi lan luot: `AudioTranscriber`, `SpeakerDiarizer`, `SceneDetector`, `SemanticAnalyzer`, `TimelineBuilder`, `Summarizer`.

Diem yeu:
- Kien truc tai lieu noi ASR va scene detection co the chay song song, nhung implementation dang chay tuan tu.
- Video dai se tang latency theo tong thoi gian tung module, khong phai thoi gian lon nhat cua cac nhanh song song.
- Khi mot stage dau cham, toan bo pipeline bi keo theo.

Tac dong:
- Kho dat muc tieu xu ly nhanh voi video 30-60 phut.
- Kho scale khi co nhieu job cung luc, vi moi worker bi giu lau.

## 2. Fail-fast va recovery giua cac stage con yeu

Pipeline boc nhieu stage trong mot task Celery lon. Neu mot stage loi, task fail chung; neu mot stage tra du lieu rong nhung khong raise exception, stage sau van co the chay voi input kem.

Diem yeu:
- Chua co contract validation ro sau moi stage: audio phai co segment, visual phai co scene/keyframe, timeline phai co chapters.
- Chua co retry rieng theo stage. Loi tam thoi o LLM/R2/ChromaDB co the lam fail ca job hoac tao ket qua fallback.
- Chua co checkpoint/cache stage-level de resume tu stage da thanh cong.

Tac dong:
- Mot loi nho o cuoi pipeline co the bat chay lai toan bo video.
- Ket qua co the "done" nhung thieu thanh phan quan trong neu fallback im lang.

## 3. Kiem tra revoke/cancel chi nam giua cac stage

`process_video` co ham `check_revoked()` nhung chi goi truoc cac stage lon.

Diem yeu:
- Neu user cancel khi model dang transcribe, detect scene, caption slide hoac summarize, worker chi dung sau khi stage hien tai thoat.
- `jobs.py` dung revoke terminate voi `SIGKILL`, de lai nguy co file/output dang ghi do dang.

Tac dong:
- Cancel co the cham hoac tao trang thai lech: DB da failed nhung worker van con dang ghi output.
- Temp files/cache/output co the bi orphan.

## 4. Input video remote phu thuoc download truc tiep trong worker

Worker ho tro YouTube bang `yt_dlp`, R2 bang boto3, va remote file bang `requests.get(..., stream=True)`.

Diem yeu:
- Download la mot phan cua AI task, nen loi mang/YouTube/R2 lam task AI fail.
- Chua thay gioi han timeout, kich thuoc tai ve, toc do tai ve, checksum, hay preflight metadata.
- Neu video remote thay doi/noi dung hong, pipeline chi phat hien muon.

Tac dong:
- Job co the treo lau o stage download.
- Kho tai lap ket qua benchmark vi input URL co the thay doi.

## 5. Audio ASR la diem ngheo chat luong dau vao

Stage audio tao transcript va segments, sau do speaker/timeline/summarizer deu phu thuoc vao ket qua nay.

Diem yeu:
- Neu ASR sai, timestamp lech hoac segment rong, cac stage sau khong co co che danh dau do tin cay.
- Chua thay quality gate nhu min confidence, WER proxy, silence/no speech detection, language mismatch detection.
- Neu duration/audio extraction fail, pipeline co the tiep tuc den khi module sau loi.

Tac dong:
- Summary va Q&A co the sai tu goc, nhung nhin van nhu ket qua hop le.
- Timestamp/citation trong ket qua co the khong dang tin.

## 6. Speaker diarization con mong manh voi video ngoai pham vi mot nguoi noi

Tai lieu ban dau uu tien video bai giang mot nguoi noi, nhung pipeline co stage speaker diarization rieng.

Diem yeu:
- Neu video co nhieu nguoi noi, overlap, nhac nen, hoi dap lop hoc, diarization co the gan sai speaker.
- Chua thay output co confidence/DER proxy de bao "speaker khong chac".
- Neu diarization fail, cac utterance van co the di tiep voi speaker mac dinh/khong chuan.

Tac dong:
- Summary co the nham vai tro nguoi noi.
- Q&A theo ngu canh speaker kem tin cay.

## 7. Visual pipeline de mat thong tin slide quan trong

Stage visual detect scene/keyframe, semantic loc slide trung lap va caption.

Diem yeu:
- Loc slide bang K-Means/semantic co nguy co loai slide quan trong neu slide nhin giong nhau nhung noi dung khac nho.
- Scene detection de loi voi animation, transition, picture-in-picture, camera quay giang vien, slide doi tung dong.
- Chua co quality gate cho keyframe blur, OCR rong, caption rac, hoac scene qua ngan/qua dai.

Tac dong:
- Summary thieu noi dung tren slide.
- RAG/Q&A khong tra loi duoc cau hoi dua tren hinh anh.

## 8. Semantic analysis va caption co nguy co hallucination

Semantic stage mo ta slide bang model vision/caption. Backend/LLM sau do dung mo ta nay nhu ngu canh.

Diem yeu:
- Caption co the sinh noi dung khong co tren slide.
- Chua thay co buoc verify caption/OCR voi evidence cu the.
- Neu model chay CPU hoac checkpoint khong phu hop, caption co the rac; repo co test Florence runtime rieng nhung smoke test that bi skip neu khong set env.

Tac dong:
- Summary co the dua vao visual caption sai.
- Q&A co the tra loi tu noi dung hallucinated cua caption.

## 9. Timeline alignment co fallback don gian

Sau timeline stage, neu khong co `aligned_segments`, code fallback sang overlap thoi gian giua utterance va scene.

Diem yeu:
- Fallback temporal overlap khong xet semantic, noi dung cau dang noi do dang, hay slide transition.
- Khong thay flag chat luong alignment trong output.
- Neu ASR timestamp hoac scene boundary lech, fallback se gan transcript sai slide.

Tac dong:
- Chapter/keyframe/script bi gan sai.
- Citation timestamp va slide reference kem tin cay.

## 10. Summarization/RAG co fallback mock va thieu guard chat luong

Summarizer goi LLM va build RAG index. Backend service LLM co fallback mock khi thieu/fail API key.

Diem yeu:
- Neu LLM provider fail, he thong co the tra mock response thay vi fail ro.
- Chua thay buoc verify summary grounding: moi claim co timestamp/slide evidence.
- RAG index fail duoc log/canh bao, nhung pipeline van co the tiep tuc.
- Chua co danh gia tu dong ROUGE/BERTScore/faithfulness tren output moi.

Tac dong:
- Ket qua trong demo co the "dep" nhung khong phai output AI that.
- Q&A co the dua tren index thieu/chua dung.

## 11. Ket qua tra ve phu thuoc schema ngam giua worker va backend

Worker return dict gom `summary`, `chapters`, `keyframes`, `transcript_segments`, `scenes`, `model_used`, `video_file_path`. Backend `sync_job_status` doc cac key nay de luu DB.

Diem yeu:
- Khong thay schema contract chung cho worker result.
- Neu module thay key `startTime/start_time`, `imageUrl/keyframe_url`, `importanceScore`, backend/frontend de vo.
- Loi schema chi lo ra khi job SUCCESS va sync DB.

Tac dong:
- Job Celery co the success nhung backend khong luu day du summary/scenes.
- Frontend/Q&A sau do bi thieu du lieu.

## 12. Do bao phu test AI pipeline con hep

Test hien co chu yeu tap trung Florence runtime/determinism va asset hash.

Diem yeu:
- Chua co test cho `process_video` end-to-end voi fixture video nho.
- Chua co test audio -> speaker -> visual -> timeline -> summary contract.
- Chua co test loi: video hong, khong audio, ChromaDB fail, LLM fail, R2 fail, cancel job.
- Smoke test Florence that bi skip neu khong set `RUN_FLORENCE_SMOKE_TEST=1`.

Tac dong:
- Moi thay doi module AI de gay regression ma khong bi bat.
- Kho chung minh pipeline hien tai on dinh bang test tu dong.

## 13. Diem yeu quan trong nhat can neu trong bao cao

1. Pipeline AI hien dang gan ket thanh mot Celery task lon, chay tuan tu, kho retry/resume theo stage.
2. Chat luong ket qua phu thuoc nang vao ASR va timeline alignment, nhung chua co confidence/quality gate.
3. Visual/semantic stage co nguy co bo sot slide hoac sinh caption sai, chua co verify grounding.
4. Summarization/RAG co fallback mock va chua co bo kiem tra hallucination/faithfulness bat buoc.
5. Cancel/revoke va loi ha tang co the de lai output/trang thai khong dong bo.
6. Test tu dong cho pipeline AI con thieu, moi co test runtime Florence rieng.

## 14. Huong khac phuc uu tien

1. Tach pipeline thanh stage co contract ro: input/output schema, required fields, confidence, error type.
2. Them checkpoint/cache per stage de retry/resume, khong chay lai toan bo video.
3. Them quality gates: ASR confidence, no-speech, scene count range, OCR/caption empty rate, alignment score, summary grounding score.
4. Bat label ro khi dung fallback/mock; production khong duoc silent mock.
5. Them test fixture video nho cho `process_video` contract va cac failed path.
6. Them benchmark nho: latency, WER proxy, scene/keyframe sanity, RAG citation accuracy.

## 15. Cau hoi chua ro

1. Pipeline demo co chap nhan mock/fallback khong, hay can fail ro khi model/API loi?
2. Video muc tieu chinh la mot nguoi noi hay can ho tro nhieu nguoi noi ngay?
3. Co bo video fixture chuan nao cua nhom de lam regression test khong?
