"""Phase 3a of the LED OCR ablation: two LED summaries per video from the same extracted input.

Arm A runs with LED_INCLUDE_OCR=False, arm D with True; nothing else differs. Each cell is generated once,
in the order A then D per video, and a failed cell is final (no rerun to change a result). Summary and source
texts go to a private file; the receipt carries hashes and counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from experiments.scripts.led_ocr_ablation_extract import EXTRACTION_ENV, assert_app_commit, assert_pinned_settings, assert_private_dir, append_ledger, gpu_line, log, log_traceback, read_ledger, read_rows, video_slug

ARMS = ("A", "D")
ARM_FLAG = {"A": False, "D": True}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plain_transcript(utterances: list[dict]) -> str:
    """Same joining as the app: stripped, non-empty utterance texts."""
    return " ".join(t for t in ((u.get("text") or "").strip() for u in utterances) if t)


def cell_key(video_id: str, arm: str) -> str:
    return f"{video_id}|{arm}"


def valid_cell(arm: str, result: dict | None) -> str | None:
    """None when the result is a valid cell for the arm, else the reason it is not."""
    if not result:
        return "led_returned_none"
    if result.get("summary_method") != "led":
        return "not_led_method"
    if arm == "A" and "OCR" in str(result.get("model_used")):
        return "arm_a_contains_ocr"
    return None


def generate_cell(video: dict, arm: str, inputs: dict, led, set_flag, merge, call_counter: list, observed: dict | None = None) -> tuple[dict, dict]:
    """One cell. `led` is build_led_result, `set_flag` toggles LED_INCLUDE_OCR, `merge` is merge_speech_and_ocr.

    `observed` is filled by a wrapper around led_map_reduce with {"match": bool}: whether the token ids LED really
    received equal the encoding of the source this harness expects for the arm. Returns (receipt row, private row).
    """
    data = inputs["data"]
    utterances, keyframes, chapters = data["utterances"], data["keyframes"], data["chapters"]
    observed = observed if observed is not None else {}
    row = {"id": video["id"], "stratum": video["stratum"], "arm": arm, "input_sha256": inputs["_sha256"]}
    private = {"id": video["id"], "arm": arm}
    started = time.perf_counter()
    try:
        transcript = plain_transcript(utterances)
        merged, stats = merge(utterances, keyframes)
        source = merged if arm == "D" else transcript
        observed["expected_source"], observed["match"] = source, None
        row.update(source_sha256=sha256_text(source), transcript_words=stats["transcript_words"],
                   ocr_words=stats["ocr_words"] if arm == "D" else 0, slides_used=stats["slides_used"] if arm == "D" else 0)
        private.update(source_text=source, transcript_text=transcript)
        set_flag(ARM_FLAG[arm])
        call_counter[0] = 0
        result = led(utterances, keyframes, chapters, f"ocrabl-{video_slug(video['id'])}-{arm}", "en", "detailed")
        reason = valid_cell(arm, result)
        if reason:
            raise ValueError(reason)
        row["source_observed_match"] = observed.get("match")
        if observed.get("match") is False:
            raise ValueError("source_mismatch: LED input differs from the expected source")
        if arm == "D" and (row["ocr_words"] > 0) != ("OCR" in str(result.get("model_used"))):
            raise ValueError("ocr_flag_inconsistent: harness and app disagree on OCR use")
        summary = result["summary"]
        row.update(status="ok", model_used=result["model_used"], word_count=len(summary.split()),
                   summary_sha256=sha256_text(summary), led_calls=call_counter[0])
        private["summary_text"] = summary
    except Exception as error:  # noqa: BLE001 - recorded, never rerun
        log_traceback(Path(os.environ.get("ABLATION_LOG_DIR", ".")), f"{video['id']}|{arm}")
        row.update(status="error", error=type(error).__name__, detail=str(error)[:160])
    row["generation_seconds"] = round(time.perf_counter() - started, 1)
    return row, private


def source_check(rows: list[dict]) -> list[str]:
    """Audit problems: arm A source must equal the transcript, and an arm pair must share one input hash."""
    problems = []
    by_video: dict[str, dict] = {}
    for row in rows:
        by_video.setdefault(row["id"], {})[row["arm"]] = row
    for vid, arms in by_video.items():
        if set(arms) != set(ARMS):
            problems.append(f"{vid}: missing arm {sorted(set(ARMS) - set(arms))}")
            continue
        if arms["A"]["input_sha256"] != arms["D"]["input_sha256"]:
            problems.append(f"{vid}: arms read different inputs")
        if arms["D"]["ocr_words"] == 0 and arms["A"]["source_sha256"] != arms["D"]["source_sha256"]:
            problems.append(f"{vid}: no OCR in D but sources differ")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--out-dir", required=True, help="private folder from the extract step (inputs/ + ledgers)")
    parser.add_argument("--set", choices=("smoke", "cohort"), required=True)
    parser.add_argument("--protocol-dir", required=True)
    args = parser.parse_args(argv)

    out_dir, protocol_dir, app_root = Path(args.out_dir).resolve(), Path(args.protocol_dir).resolve(), Path(args.app_root).resolve()
    cohort = json.loads((protocol_dir / "cohort.json").read_text(encoding="utf-8"))
    videos = cohort["smoke_videos" if args.set == "smoke" else "videos"]
    extracted = read_ledger(out_dir / f"extract_ledger_{args.set}.jsonl")
    receipt_path = out_dir / f"cells_receipt_{args.set}.jsonl"
    private_path = out_dir / f"cells_private_{args.set}.jsonl"
    done = {cell_key(r["id"], r["arm"]) for r in (json.loads(l) for l in receipt_path.read_text(encoding="utf-8").splitlines())} \
        if receipt_path.exists() else set()

    assert_app_commit(app_root, protocol_dir)
    assert_private_dir(out_dir)
    os.chdir(app_root)
    sys.path.insert(0, str(app_root))
    os.environ.update(EXTRACTION_ENV)  # same pinned settings as extraction; verified right after the import
    from ai_workers.core.config import worker_settings
    from ai_workers.modules.summarization import led_summarizer
    from ai_workers.modules.summarization.led_summarizer import build_led_result
    from ai_workers.modules.summarization.ocr_evidence import merge_speech_and_ocr

    assert_pinned_settings(worker_settings)
    import torch

    if not torch.cuda.is_available():  # infrastructure failure, not a result: stop before any cell is written
        raise SystemExit("no CUDA GPU; no cell written")
    led_summarizer.load_led()  # fails here, not as 80 permanent error cells

    calls = [0]
    original_generate = led_summarizer.LedModel.generate

    def counted(self, ids, max_new_tokens):
        calls[0] += 1
        return original_generate(self, ids, max_new_tokens)

    led_summarizer.LedModel.generate = counted
    observed: dict = {}
    original_map_reduce = led_summarizer.led_map_reduce

    def watched(source_ids, encode, generate):
        observed["match"] = list(source_ids) == list(encode(observed["expected_source"]))
        return original_map_reduce(source_ids, encode, generate)

    led_summarizer.led_map_reduce = watched
    (out_dir / f"generate_env_{args.set}.json").write_text(
        json.dumps({"LED_MODEL": worker_settings.LED_MODEL, "LED_MODEL_REVISION": worker_settings.LED_MODEL_REVISION,
                    "SUMMARIZER_ENGLISH_BACKEND": worker_settings.SUMMARIZER_ENGLISH_BACKEND,
                    "LED_KEEP_RESIDENT": worker_settings.LED_KEEP_RESIDENT}, indent=2), encoding="utf-8")

    def set_flag(value: bool) -> None:
        worker_settings.LED_INCLUDE_OCR = value

    os.environ["ABLATION_LOG_DIR"] = str(out_dir / "logs")
    log(f"set={args.set}: {len(videos)} videos, {len(done)} cells already in the receipt; model={worker_settings.LED_MODEL}")
    log(f"GPU: {gpu_line()}")
    for index, video in enumerate(videos, 1):
        info = extracted.get(video["id"])
        if not info or info.get("status") != "ok":
            for arm in ARMS:  # the pair is not comparable; recorded, not skipped silently
                if cell_key(video["id"], arm) not in done:
                    append_ledger(receipt_path, {"id": video["id"], "stratum": video["stratum"], "arm": arm,
                                                     "status": "error", "error": "missing_input"})
            continue
        inputs = json.loads(Path(info["input_path"]).read_text(encoding="utf-8"))
        inputs["_sha256"] = info["input_sha256"]
        for arm in ARMS:
            if cell_key(video["id"], arm) in done:
                continue
            log(f"[{index}/{len(videos)}] {video['id']} arm {arm}: generating (LED_INCLUDE_OCR={ARM_FLAG[arm]})")
            row, private = generate_cell(video, arm, inputs, build_led_result, set_flag, merge_speech_and_ocr, calls, observed)
            with private_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(private, ensure_ascii=False) + "\n")
            append_ledger(receipt_path, row)
            if row["status"] == "ok":
                log(f"[{index}/{len(videos)}] {video['id']} arm {arm}: OK in {row['generation_seconds']}s | words={row['word_count']} led_calls={row['led_calls']} "
                    f"| transcript_words={row['transcript_words']} ocr_words={row['ocr_words']} slides={row['slides_used']} "
                    f"| source_match={row['source_observed_match']} model={row['model_used']}")
            else:
                log(f"[{index}/{len(videos)}] {video['id']} arm {arm}: ERROR {row['error']}: {row.get('detail')}")
    final = read_rows(receipt_path)
    log(f"finished: {sum(r.get('status') == 'ok' for r in final)} ok cells, {sum(r.get('status') == 'error' for r in final)} error cells; GPU: {gpu_line()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
