import json
from pathlib import Path

from experiments.scripts import led_ocr_ablation_extract as ex

VIDEO = {"id": "10.5446/1", "stratum": "S1_cs_talk_scored", "media_url": "http://invalid.test/x.mp4"}


def fake_merge(utterances, keyframes):
    return "x", {"transcript_words": 4, "ocr_words": 3, "slides_used": 1}


def checkpoint_doc():
    return {"data": {"utterances": [{"text": "a b c d"}], "keyframes": [{"ocr_text": "Alpha Beta"}, {"ocr_text": ""}],
                     "visual_result": {"segmenter": "slide", "scenes": [1, 2]},
                     "audio_result": {"asr_model": "Qwen/Qwen3-ASR-0.6B", "language": "en"}}}


def test_slug_and_ledger_resume(tmp_path):
    assert ex.video_slug("10.5446/32263") == "10_5446_32263"
    ledger = tmp_path / "l.jsonl"
    ex.append_ledger(ledger, {"id": "a", "status": "ok"})
    ledger.write_bytes(ledger.read_bytes() + b'{"id": "b", "sta')  # torn write
    assert set(ex.read_ledger(ledger)) == {"a"}
    ex.append_ledger(ledger, {"id": "c", "status": "error"})
    assert set(ex.read_ledger(ledger)) == {"a", "c"}


def test_errors_are_final_not_rerun():
    videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    ledger = {"a": {"id": "a", "status": "ok"}, "b": {"id": "b", "status": "error"}}
    assert [v["id"] for v in ex.pending(videos, ledger)] == ["c"]


def test_extract_one_copies_checkpoint_and_hashes(tmp_path):
    source = tmp_path / "ckpt.json"
    source.write_text(json.dumps(checkpoint_doc()), encoding="utf-8")

    def run_task(job_id, path, stub):
        stub(None, [], [], [], job_id=job_id)
        return {"processing_time": 12.5}

    row = ex.extract_one(VIDEO, tmp_path / "v.mp4", tmp_path / "inputs", run_task, lambda job: source, fake_merge)
    assert row["status"] == "ok"
    assert row["segmenter"] == "slide" and row["keyframes_with_ocr"] == 1 and row["raw_ocr_words"] == 2
    assert row["input_sha256"] == ex.sha256_file(Path(row["input_path"]))
    assert row["merge_ocr_words"] == 3


def test_extract_one_records_error_when_stub_not_reached(tmp_path):
    row = ex.extract_one(VIDEO, tmp_path / "v.mp4", tmp_path / "inputs", lambda *a: {}, lambda job: tmp_path / "none", fake_merge)
    assert row["status"] == "error"


def test_stub_fails_when_checkpoint_missing(tmp_path):
    stub = ex.make_stub(lambda job: tmp_path / "missing.json", tmp_path / "out.json", {})
    try:
        stub(None, [], [], [], job_id="j")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_env_dump_is_allowlist_and_hides_token():
    out = ex.redacted_settings({"HF_TOKEN": "abc", "CF_R2_ACCESS_KEY_ID": "k", "LED_MODEL": "m", "SCENE_SEGMENTER": "slide"})
    assert out == {"HF_TOKEN": "<set>", "LED_MODEL": "m", "SCENE_SEGMENTER": "slide"}


def test_pinned_settings_reject_stray_env():
    class S:
        SCENE_SEGMENTER = "content"; ENABLE_FLORENCE_CAPTIONING = False; ENABLE_OBJECT_TRACKING = False
        ASR_ENGLISH_BACKEND = "qwen3"; SUMMARIZER_ENGLISH_BACKEND = "led"; HF_TOKEN = ""
    try:
        ex.assert_pinned_settings(S)
    except SystemExit:
        return
    raise AssertionError("expected SystemExit")


def test_whisper_fallback_is_not_recorded_and_leaves_no_input(tmp_path):
    doc = checkpoint_doc()
    doc["data"]["audio_result"]["asr_model"] = "small"
    source = tmp_path / "ckpt.json"
    source.write_text(json.dumps(doc), encoding="utf-8")

    def run_task(job_id, path, stub):
        stub(None, [], [], [], job_id=job_id)
        return {}

    row = ex.extract_one(VIDEO, tmp_path / "v.mp4", tmp_path / "inputs", run_task, lambda job: source, fake_merge)
    assert row["status"] == "asr_fallback"
    assert not (tmp_path / "inputs" / "10_5446_1.json").exists()


def test_pending_rechecks_done_inputs_and_honours_retry_ids(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "a.json").write_text("12345", encoding="utf-8")
    videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
    ledger = {"a": {"id": "a", "status": "ok", "input_bytes": 5}, "b": {"id": "b", "status": "ok", "input_bytes": 9},
              "c": {"id": "c", "status": "error"}}
    assert [v["id"] for v in ex.pending(videos, ledger, inputs)] == ["b", "d"]  # b: input file missing; d: no row
    assert [v["id"] for v in ex.pending(videos, ledger, inputs, retry_ids=["c"])] == ["b", "c", "d"]
    ledger["a"]["input_bytes"] = 6  # file changed size: done no longer holds
    assert "a" in [v["id"] for v in ex.pending(videos, ledger, inputs)]


def test_progress_numbers_and_eta(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for name in ("a", "b"):
        (inputs / f"{name}.json").write_text("xx", encoding="utf-8")
    videos = [{"id": n} for n in "abcde"]
    ledger = {"a": {"id": "a", "status": "ok", "input_bytes": 2, "wall_seconds": 1000, "segmenter": "slide"},
              "b": {"id": "b", "status": "ok", "input_bytes": 2, "wall_seconds": 2000, "segmenter": "content"},
              "c": {"id": "c", "status": "error"}}
    progress = ex.build_progress(videos, ledger, inputs)
    assert (progress["done"], progress["error"], progress["remaining"]) == (2, 1, 2)
    assert progress["average_seconds"] == 1500.0 and progress["eta_hours"] == round(1500 * 2 / 3600, 2)
    assert progress["segmenter"] == {"content": 1, "slide": 1}
    assert "2/5 done" in ex.progress_line(progress)


def test_budget_stop_decision():
    assert ex.should_stop(0, 0, 1200) is False                    # no budget
    assert ex.should_stop(3000, 60, 1200) is True                 # 3000 + 1200 > 3600
    assert ex.should_stop(2000, 60, 1200) is False
    assert ex.should_stop(2000, 60, None) is True                 # unknown average: assume 30 minutes


def test_download_retries_then_records_failure(tmp_path, monkeypatch):
    calls = []

    def failing(url, timeout):
        calls.append(url)
        raise OSError("boom")

    monkeypatch.setattr(ex.urllib.request, "urlopen", failing)
    row = ex.download({"id": "10.5446/9", "media_url": "http://x.test/v.mp4"}, tmp_path / "videos", tmp_path / "dl.jsonl", sleep=lambda s: None)
    assert row["status"] == "error" and row["attempts"] == 3 and len(calls) == 3
    assert not list((tmp_path / "videos").glob("*.part"))


def test_download_succeeds_on_a_later_attempt(tmp_path, monkeypatch):
    import io

    attempts = {"n": 0}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def flaky(url, timeout):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise OSError("transient")
        return Response(b"video-bytes")

    monkeypatch.setattr(ex.urllib.request, "urlopen", flaky)
    row = ex.download({"id": "10.5446/9", "media_url": "http://x.test/v.mp4"}, tmp_path / "videos", tmp_path / "dl.jsonl", sleep=lambda s: None)
    assert row["status"] == "ok" and row["attempts"] == 2 and row["bytes"] == len(b"video-bytes")


def test_retry_ids_are_used_once_and_only_for_error_rows(tmp_path):
    videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    ledger = {"a": {"id": "a", "status": "error"}, "b": {"id": "b", "status": "ok"}, "c": {"id": "c", "status": "error", "retry_of": {"status": "error"}}}
    assert [v["id"] for v in ex.pending(videos, ledger, retry_ids=["a", "b", "c"])] == ["a"]  # b is ok, c already retried
    ledger["a"] = {"id": "a", "status": "ok", "retry_of": {"status": "error"}}
    assert ex.pending(videos, ledger, retry_ids=["a", "b", "c"]) == []  # same list in the next session selects nothing


def test_truncated_download_is_rejected_and_retried(tmp_path, monkeypatch):
    import io

    class Short(io.BytesIO):
        headers = {"Content-Length": "100"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ex.urllib.request, "urlopen", lambda url, timeout: Short(b"only-ten-b"))
    row = ex.download({"id": "10.5446/9", "media_url": "http://x.test/v.mp4"}, tmp_path / "videos", tmp_path / "run" / "dl.jsonl", sleep=lambda s: None)
    assert row["status"] == "error" and row["attempts"] == 3
    assert not (tmp_path / "videos" / "10_5446_9.mp4").exists()
    assert (tmp_path / "run" / "logs" / "errors.log").exists()


def test_complete_row_missing_its_newline_is_kept(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ledger.write_bytes(b'{"id": "a", "status": "ok"}\n{"id": "b", "status": "ok"}')  # second row lost only its newline
    ex.append_ledger(ledger, {"id": "c", "status": "ok"})
    assert [r["id"] for r in ex.read_rows(ledger)] == ["a", "b", "c"]


def test_unicode_line_separator_inside_a_row_does_not_break_reading(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ex.append_ledger(ledger, {"id": "a", "status": "error", "detail": "bad\u2028char\u0085here"})
    ex.append_ledger(ledger, {"id": "b", "status": "ok"})
    assert [r["id"] for r in ex.read_rows(ledger)] == ["a", "b"]
