# Ke hoach kiem thu va diem yeu he thong hien tai

Ngay lap: 03/08/2026

Pham vi: repository `multimodal-lecture-summarizer`, trong do source chinh nam tai `multimodal-lecture-summarizer/` gom Frontend React/Vite, Backend FastAPI, AI Workers Celery, PostgreSQL/SQLite, Redis, ChromaDB va R2/mock storage.

Can cu doc/code da doc:
- `multimodal-lecture-summarizer/README.md`: mo ta v0.2.0, microservice, AI stage con stub.
- `multimodal-lecture-summarizer/docs/ARCHITECTURE.md`: pipeline audio, speaker, visual, semantic, timeline, summarization, RAG.
- `backend/app/main.py`: khoi tao FastAPI, DB, ChromaDB, R2, Redis, static mock storage, polling Celery job.
- `backend/app/api/v1/*.py`: auth, videos, jobs, summaries, qa, stats, users.
- `ai_workers/tasks.py`: orchestration pipeline va download/upload video.
- `frontend/src/services/api.ts`: client API va luong token tren UI.
- `ai_workers/tests/*`: test hien co chu yeu cho Florence runtime.

## 1. Muc tieu kiem thu

1. Xac minh luong end-to-end: dang ky/dang nhap -> upload file/YouTube URL -> tao job -> worker xu ly -> luu summary/scenes/RAG -> hien thi ket qua -> Q&A -> export -> xoa/cancel.
2. Tim loi hop dong API giua frontend va backend: camelCase/snake_case, schema JSON, status/progress, response envelope `BaseDTO`.
3. Kiem tra bao mat: auth, phan quyen user/admin, truy cap video/stream, reset password, CORS/JWT, upload file, URL input, storage.
4. Kiem tra do tin cay AI pipeline: loi model, loi LLM, loi ChromaDB/R2/Redis, file video loi, video dai, cancel giua pipeline.
5. Kiem tra tinh dung du lieu: duplicate video URL, job status sync, transcript/chapters/keyframes, export TXT/SRT/PDF.
6. Kiem tra kha nang van hanh: docker compose, config env, migration/auto create table, logging, cleanup temp files, performance voi video lon.

## 2. Chien luoc kiem thu theo 12 chieu ck:scenario

| Chieu | Ap dung | Trong tam |
|---|---:|---|
| User types | Co | Guest, user thuong, admin, inactive user, user A truy cap data user B |
| Input extremes | Co | File rong, file sai dinh dang, spoof extension, Unicode filename, URL sai, video dai/qua lon |
| Timing | Co | Polling job, cancel khi worker dang chay, reload frontend, Redis/worker cham |
| Scale | Co | 0 video, nhieu video, nhieu scenes/keyframes, transcript dai, job queue nhieu request |
| State transitions | Co | pending -> processing -> done/failed/cancelled, retry upload, duplicate URL |
| Environment | Co | Docker/local Windows, thieu ffmpeg, thieu Redis, CPU-only Florence, browser refresh |
| Error cascades | Co | R2 fail -> mock, ChromaDB fail, LLM fail -> mock, DB fail, disk full |
| Authorization | Co | JWT het han, role admin/user, stream video khong token, xoa video user khac |
| Data integrity | Co | orphan summary/scenes, duplicate chunks, field JSON sai key, cleanup storage khong dong bo |
| Integration | Co | Frontend API, Celery task id, R2/ChromaDB/Groq/OpenRouter/yt-dlp |
| Compliance | Co | Video/transcript co PII, retention, xoa user/video, log co du lieu nhay cam |
| Business logic | Co | Tieu chuan video, export dung noi dung, Q&A phai dua tren video da xu ly |

## 3. Ma tran kiem thu he thong

| ID | Nhom | Kich ban | Buoc kiem thu | Ket qua mong doi | Muc do |
|---|---|---|---|---|---|
| E2E-01 | End-to-end | Upload file MP4 hop le | User dang nhap, upload MP4 nho, poll job den done, mo summary | Video status `done`, co summary, chapters, keyframes, transcript | Critical |
| E2E-02 | End-to-end | Upload YouTube URL | Gui `originalUrl` YouTube, worker tai ve, luu storage | Job done hoac failed co loi ro; khong treo pending | High |
| E2E-03 | End-to-end | Cancel job | Upload video dai, cancel khi progress > 0 | Job/video chuyen failed/cancelled ro rang, worker dung hoac khong ghi done sau cancel | High |
| E2E-04 | End-to-end | Q&A sau khi co summary | Hoi cau co trong transcript va cau khong co | Cau tra loi co timestamp/citation; cau khong co noi dung phai noi khong thay | High |
| E2E-05 | End-to-end | Export TXT/SRT/PDF | Export ca 3 format tu mot video da done | File dung MIME, dung noi dung cua video, khong dung noi dung demo | High |
| API-01 | Auth | Register/login/me | Tao user moi, login, goi `/auth/me` | Password hash, JWT hop le, response BaseDTO dung contract | Critical |
| API-02 | Auth | Password reset | User A yeu cau reset email user B | Phai bi chan neu khong co OTP/token reset | Critical |
| API-03 | AuthZ | User A doc video user B | Goi video detail, summary, scenes, jobs, qa cua user B | 404/403, khong ro ri metadata | Critical |
| API-04 | AuthZ | Stream video user B | Goi `/videos/{video_id}/stream` khong token va voi token user khac | Phai bi 401/403 | Critical |
| API-05 | Admin | Admin endpoints | User thuong goi `/admin/all`, standards update, users role/status | 403; admin moi duoc goi | Critical |
| API-06 | Validation | Upload khong file/URL | Gui form rong | 400 voi message ro | Medium |
| API-07 | Validation | File spoof extension | File text/zip doi ten `.mp4` | Bi tu choi bang MIME/magic/ffprobe, khong dua vao worker | Critical |
| API-08 | Validation | File qua lon | Upload > max_file_size | 400 truoc khi ghi/tai len storage | High |
| API-09 | Validation | Video qua dai | Upload video > max_duration | 400, temp file cleanup | High |
| API-10 | Search/list | Pagination boundary | limit 0, limit am, offset am, limit rat lon | Bi gioi han/validate, khong query vo han | Medium |
| WORKER-01 | Pipeline | Missing Redis/worker | Backend upload khi Redis/worker tat | Video/job failed co loi ro, khong pending vo han | High |
| WORKER-02 | Pipeline | LLM API key thieu | Xu ly pipeline khong co key LLM | Neu mock duoc phep thi gan nhan mock; neu prod thi fail ro | High |
| WORKER-03 | Pipeline | ChromaDB fail | Tat ChromaDB, xu ly video, hoi Q&A | Pipeline khong silent success neu RAG khong tao duoc; Q&A bao loi/fallback ro | High |
| WORKER-04 | Pipeline | R2 fail | Cau hinh R2 sai | Fallback mock chi trong dev; prod phai fail/canh bao | High |
| WORKER-05 | Pipeline | File video hong | Upload file co extension dung nhung ffprobe/doc khong doc duoc | Job failed, temp/output cleanup, khong ghi summary rong | High |
| WORKER-06 | Pipeline | Timeline fallback | Semantic alignment khong co `aligned_segments` | Fallback temporal overlap khong lam mat script; co log canh bao | Medium |
| WORKER-07 | Pipeline | Cancel/kill | Huy job khi dang download/model inference | Worker khong tiep tuc ghi ket qua done sau khi DB da failed | High |
| UI-01 | Frontend | Token expired | Xoa/het han token, vao `/upload`/`/admin` | Chuyen auth, khong reload loop | Medium |
| UI-02 | Frontend | Role guard | User thuong go URL admin | UI redirect va API 403 | High |
| UI-03 | Frontend | Progress polling | Video processing lau | UI hien stage/log, khong crash khi logs rong/null | Medium |
| UI-04 | Frontend | Empty states | 0 videos, 0 QA history, 0 stats | UI khong hien so lieu mock nhu that neu la production | Medium |
| UI-05 | Frontend | i18n/encoding | Text Vietnamese trong UI/API | Khong mojibake, message doc duoc | Medium |
| PERF-01 | Performance | Video 30-60 phut | Chay video dai, do CPU/RAM/GPU/disk | Latency trong gioi han, khong OOM, log stage day du | High |
| PERF-02 | Performance | Nhieu upload song song | 5-10 users upload | Queue xu ly tuan tu/song song co gioi han, khong mat status | High |
| SEC-01 | Security | CORS/JWT default | Chay voi env rong | Khong chap nhan secret mac dinh/CORS `*` o production | Critical |
| SEC-02 | Security | URL download SSRF | Dua URL noi bo vao worker path/queue | Worker khong tai IP private/metadata endpoint | Critical |
| SEC-03 | Security | Storage path | File name/object key dac biet | Khong path traversal, khong overwrite file khac | High |
| SEC-04 | Security | Logs | Upload video/co cau hoi chua PII | Log khong in token/API key/transcript nhay cam qua muc | Medium |
| DATA-01 | Data | Duplicate YouTube URL | 2 user upload cung URL | Khong ro ri file_path/data user khac; ownership rieng | High |
| DATA-02 | Data | Xoa video | Xoa video co summary/scenes/qa/chunks | DB cascade va R2/Chroma cleanup dong bo; loi cleanup khong lam record nua voi | High |

## 4. Diem yeu uu tien

### Critical

1. Endpoint stream video thieu authentication/ownership.
   - Bang chung: `backend/app/api/v1/videos.py:365` dinh nghia `stream_video`; tham so chi co `db: Session = Depends(get_db)` o `videos.py:368`, khong co `current_user`.
   - Rủi ro: bat ky ai biet `video_id` co the stream video, dac biet khi path la `/static/mock_r2/...`.
   - Test bat buoc: `API-04`.

2. Reset password khong co OTP/token reset.
   - Bang chung: `backend/app/api/v1/auth.py:122` `forgot_password` chi tra `resetAllowed`; `auth.py:144` `reset_password` chi can email va mat khau moi.
   - Rủi ro: chi can biet email la doi duoc mat khau.
   - Test bat buoc: `API-02`.

3. Cau hinh mac dinh yeu cho moi truong production.
   - Bang chung: `backend/app/core/config.py:26` `DEBUG=True`, `config.py:28` secret mac dinh, `config.py:29` token song 8 ngay, `config.py:32` CORS origins mac dinh rong, `config.py:40` DB password mac dinh.
   - Rủi ro: JWT de bi forge neu secret khong doi, CORS rong lam tang mat phang tan cong, debug ro ri loi.
   - Test bat buoc: `SEC-01`.

4. Upload chi validate extension, khong validate MIME/magic/file safety truoc worker.
   - Bang chung: `backend/app/api/v1/videos.py:69` lay extension tu filename; `videos.py:73` check extension; duration fallback co the ve `0.0` neu OpenCV/ffprobe fail.
   - Rủi ro: file gia mao `.mp4` vao storage/worker, gay crash, resource abuse, hoac chain loi multimedia parser.
   - Test bat buoc: `API-07`, `WORKER-05`.

5. Worker co logic tai remote URL bang `requests.get` neu nhan URL ngoai.
   - Bang chung: `ai_workers/tasks.py:188` goi `requests.get(video_path, stream=True)`. API hien chi cho YouTube, nhung task queue noi bo co the goi truc tiep voi URL bat ky.
   - Rủi ro: SSRF/internal network access neu co endpoint/queue nao truyen URL khong kiem soat.
   - Test bat buoc: `SEC-02`.

### High

6. Fallback/mock co the lam he thong bao thanh cong gia.
   - Bang chung: `backend/app/services/llm.py:39` no API key -> mock mode; `llm.py:111` all providers failed -> mock response; `backend/app/api/v1/stats.py:35` seed mock stats; `stats.py:68` default chart data.
   - Rủi ro: demo/prod kho phan biet ket qua AI that va mock, bao cao thong ke sai.
   - Test bat buoc: `WORKER-02`, `UI-04`.

7. Export SRT/PDF chua xuat noi dung that day du.
   - Bang chung: `backend/app/api/v1/summaries.py:196` SRT hardcode noi dung demo; `summaries.py:219` PDF tao stream toi gian; `summaries.py:148` docstring goi PDF Mock.
   - Rủi ro: user tai file sai noi dung video, anh huong demo/bao cao.
   - Test bat buoc: `E2E-05`.

8. Admin stats tu dong ghi mock records vao DB khi rong.
   - Bang chung: `backend/app/api/v1/stats.py:35` seed mock historical records neu DB empty.
   - Rủi ro: du lieu bao cao bi pha tap; kho tach demo data va real data.
   - Test bat buoc: `UI-04`, `DATA-02`.

9. Job sync/polling phu thuoc polling moi 10 giay va im lang khi loi.
   - Bang chung: `backend/app/main.py` tao background polling loop; `backend/app/api/v1/jobs.py` `sync_job_status` bat exception va chi log warning.
   - Rủi ro: job keo dai pending/running, loi ChromaDB/DB khong day len UI ro rang.
   - Test bat buoc: `WORKER-01`, `WORKER-03`.

10. Cancel job dung terminate `SIGKILL`, co nguy co de lai output tam/trang thai chen nhau.
    - Bang chung: `backend/app/api/v1/jobs.py:284` revoke terminate bang `SIGKILL`; worker chi check revoked giua cac stage.
    - Rủi ro: file temp/output/chunks dang ghi do dang; worker co the ghi ket qua sau khi API da mark failed neu race.
    - Test bat buoc: `E2E-03`, `WORKER-07`.

11. Storage mock duoc mount static cong khai.
    - Bang chung: `backend/app/main.py:146` mount `/static/mock_r2`; `backend/app/services/r2.py` fallback local mock mode.
    - Rủi ro: file video/keyframe trong mock storage co the duoc truy cap neu doan URL.
    - Test bat buoc: `API-04`, `SEC-03`.

12. Test coverage hien lech ve Florence runtime, thieu backend/API/e2e.
    - Bang chung: `ai_workers/tests/test_florence_runtime.py:27-122` chu yeu test runtime/determinism; smoke real model bi skip tru khi set `RUN_FLORENCE_SMOKE_TEST=1` tai `test_florence_golden.py:18-20`; frontend package khong co test script.
    - Rủi ro: auth, upload, job, summary, Q&A, export, admin khong co regression net.
    - Test bat buoc: uu tien viet pytest FastAPI va Playwright/Vitest.

### Medium

13. Frontend luu JWT trong `localStorage`.
    - Bang chung: `frontend/src/services/api.ts:4` doc token tu `localStorage`, `AuthPage.tsx` luu token.
    - Rủi ro: XSS lay token; can CSP/sanitize/httpOnly cookie neu production.
    - Test bat buoc: `SEC-04`, UI security scan.

14. Transcript plain text duoc noi suy timestamp/word tokens.
    - Bang chung: `backend/app/api/v1/summaries.py:89` tao segments noi suy khi transcript la plain text.
    - Rủi ro: timestamp/citation khong dung nguon that.
    - Test bat buoc: Q&A/export voi transcript plain text.

15. Kiem tra duration co fallback ve `0.0`.
    - Bang chung: `backend/app/api/v1/videos.py:100-124` doc duration bang OpenCV/ffprobe, loi thi de `0.0`.
    - Rủi ro: video qua dai hoac hong co the vuot qua max_duration o upload step.
    - Test bat buoc: `API-09`, `WORKER-05`.

16. Tai lieu va code co dau hieu drift.
    - Bang chung: README local command noi `cd backend_api`, nhung repo co `backend/`; README ghi AI stage stub trong khi code co pipeline v2.
    - Rủi ro: QA/onboarding chay sai lenh, danh gia sai trang thai.
    - Test bat buoc: doc smoke test theo setup-guide/README.

## 5. Ke hoach trien khai test theo uu tien

### Dot 1: Security/API regression toi thieu

Muc tieu: khoa cac loi Critical de tai lieu/demo khong ro ri data.

Test can tao:
- Pytest FastAPI cho auth register/login/me.
- Pytest cho reset password yeu cau token reset/OTP sau khi sua.
- Pytest cho ownership: video detail, summary, scenes, jobs, qa, delete, stream.
- Pytest cho upload spoof extension, file hong, limit size/duration.
- Config test: fail fast neu `APP_ENV=production` ma `SECRET_KEY`/CORS/default password chua doi.

Tieu chi xong:
- 100% endpoint co data user phai co auth dependency va owner/admin check.
- Test stream khong token/user khac tra 401/403.
- Upload spoof `.mp4` bi reject truoc khi enqueue Celery.

### Dot 2: End-to-end happy path va failed path

Muc tieu: xac minh pipeline that co the chay va loi duoc surface.

Test can tao:
- Docker/local smoke: backend health, Redis ping, worker ready.
- Upload MP4 mau nho -> job done -> summary/scenes co data.
- Tat worker/Redis -> upload fail co message ro.
- Tat LLM key -> ket qua phai gan nhan mock hoac fail theo mode.
- ChromaDB fail -> Q&A behavior duoc quy uoc ro.
- Cancel job dang chay -> khong ghi summary done sau cancel.

Tieu chi xong:
- Khong co job pending/running vo han sau loi ha tang.
- UI hien loi tu backend, khong chi spinner.

### Dot 3: Frontend/UI regression

Muc tieu: luong nguoi dung khong vo khi du lieu rong, token loi, job chay lau.

Test can tao:
- Playwright: login/register, route guard, admin guard.
- Playwright: upload form validation, progress page, history empty/done/failed.
- Playwright: results page voi summary/chapters/keyframes/trancript dai.
- Playwright: QA page voi history rong/nhieu cau, clear history.
- Visual smoke desktop/mobile cho upload, history, results, admin.

Tieu chi xong:
- Khong reload loop khi token 401.
- Khong hien mock stats nhu du lieu that neu production.
- Text Vietnamese khong bi mojibake trong UI.

### Dot 4: AI quality/evaluation regression

Muc tieu: do dung pipeline AI, khong chi chay thanh cong.

Test can tao:
- Golden fixtures video ngan: expected transcript rough match, scenes count range, keyframe URL exists.
- Florence CPU smoke voi `RUN_FLORENCE_SMOKE_TEST=1` tren may co checkpoint.
- Benchmark nho TED-LIUM/TVSum fixture: WER/F-score/latency baseline.
- RAG Q&A: cau hoi can timestamp phai tra citation hop le.
- Export TXT/SRT/PDF phai dung noi dung summary/transcript cua video.

Tieu chi xong:
- Co threshold chat luong toi thieu va duong lui khi model/API fail.
- Export khong con noi dung hardcode demo.

### Dot 5: Data/ops/performance

Muc tieu: van hanh on dinh voi du lieu lon hon demo.

Test can tao:
- Nhieu upload song song, queue depth, worker concurrency.
- Video dai 30-60 phut: memory/GPU/disk/elapsed time.
- Delete video: DB cascade, R2/mock files, Chroma chunks.
- Docker compose fresh start tren DB rong va DB co data.
- Backup/restore SQLite/Postgres neu dung trong demo.

Tieu chi xong:
- Cleanup temp/output ro rang.
- Khong seed mock vao DB production.
- Co script reset demo rieng, khong lan vao endpoint production.

## 6. De xuat cau truc test

```
multimodal-lecture-summarizer/
  backend/
    tests/
      conftest.py
      test_auth.py
      test_video_upload_validation.py
      test_video_authorization.py
      test_jobs.py
      test_summaries_export.py
      test_qa.py
      test_admin_stats.py
  ai_workers/
    tests/
      test_process_video_contract.py
      test_worker_error_paths.py
      test_storage_cleanup.py
  frontend/
    tests/
      auth.spec.ts
      upload.spec.ts
      history.spec.ts
      results.spec.ts
      admin.spec.ts
```

Khuyen nghi cong cu:
- Backend: `pytest`, `fastapi.testclient` hoac `httpx.AsyncClient`, SQLite temp DB, monkeypatch Celery/R2/ChromaDB.
- Worker: `pytest`, fixture video ngan, monkeypatch LLM/R2/ChromaDB, optional real smoke test co flag env.
- Frontend: Playwright cho e2e, Vitest/React Testing Library neu can unit component.
- Security quick scan: test config production, endpoint auth matrix, upload MIME/magic.

## 7. Cac lenh kiem thu de chuan hoa

Chua chay trong lan lap tai lieu nay vi yeu cau hien tai la tao ke hoach va danh sach diem yeu. Nen chuan hoa cac lenh sau sau khi bo sung test:

```powershell
cd C:\Users\hung\Documents\GitHub\multimodal-lecture-summarizer\multimodal-lecture-summarizer\backend
pytest -q

cd C:\Users\hung\Documents\GitHub\multimodal-lecture-summarizer\multimodal-lecture-summarizer\ai_workers
pytest -q

cd C:\Users\hung\Documents\GitHub\multimodal-lecture-summarizer\multimodal-lecture-summarizer\frontend
npm run build
npx playwright test
```

## 8. Cau hoi chua ro

1. Moi truong muc tieu la demo local hay production/public? Cau tra loi anh huong viec cho phep mock fallback, CORS `*`, static mock storage.
2. Co bat buoc ho tro reset password that qua email/OTP khong, hay nen tam thoi tat endpoint reset?
3. Export PDF/SRT can la tinh nang that trong dot nay hay co the gan nhan "demo/mock" tren UI?
4. ChromaDB/R2/LLM fail thi yeu cau UX la fail job hay cho fallback co gan nhan ro?
5. Video test chuan cua nhom la file nao, co the dua vao fixture nho trong repo hay luu ngoai repo?
