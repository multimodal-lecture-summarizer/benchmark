import json
from pathlib import Path

from experiments.scripts import led_ocr_ablation_extract as ex

VIDEO = {"id": "10.5446/1", "stratum": "S1_cs_talk_scored", "media_url": "http://invalid.test/x.mp4"}


def fake_merge(utterances, keyframes):
    return "x", {"transcript_words": 4, "ocr_words": 3, "slides_used": 1}


def checkpoint_doc():
    return {"data": {"utterances": [{"text": "a b c d"}], "keyframes": [{"ocr_text": "Alpha Beta"}, {"ocr_text": ""}],
                     "visual_result": {"segmenter": "slide", "scenes": [1, 2]},
                     "audio_result": {"asr_model": "qwen3", "language": "en"}}}


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
