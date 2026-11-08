import hashlib
import json
import zipfile

import pytest

from experiments.scripts import tib_final523_applm as ap

SOURCE = "Source {braces} text about steel and how it is made."
REFERENCE = "An abstract about steel."
ABSTRACT = "This talk covers steel. It explains how steel is made. It ends with a conclusion about cost."


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bundle_row(profile, rid, stratum="short"):
    return {"sample_id": f"{profile}__{rid}", "record_id": rid, "profile_id": profile, "source_stratum": stratum,
            "source": SOURCE, "reference": REFERENCE, "source_sha256": sha(SOURCE), "reference_sha256": sha(REFERENCE),
            "source_receipt_sha256": "r" * 64}


def make_bundle(path, rids, tamper=None):
    rows = [bundle_row(p, rid) for rid in rids for p in ("lead3", "led")]
    if tamper:
        rows[0]["source"] += " x"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("scoring_outputs.jsonl", "\n".join(json.dumps(r) for r in rows))
    return path


def stop(text=ABSTRACT, **extra):
    return {"text": text, "finish_reason": "stop", "prompt_tokens": 10, "completion_tokens": 20, "seconds": 1.5, **extra}


def test_messages_keep_the_source_verbatim_and_the_prompt_frozen():
    messages = ap.build_messages(SOURCE)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"].endswith("Transcript:\n" + SOURCE)
    assert "about 110 words" in messages[1]["content"] and "reference" not in messages[1]["content"].lower()


def test_collect_sources_are_distinct_sorted_and_hash_checked(tmp_path):
    sources = ap.collect_sources(make_bundle(tmp_path / "b.zip", ["test:2", "test:10", "test:2"]))
    assert [s["record_id"] for s in sources] == ["test:10", "test:2"]
    assert ap.collect_sources(make_bundle(tmp_path / "b.zip", ["test:2", "test:10"]), limit=1)[0]["record_id"] == "test:10"
    with pytest.raises(ValueError, match="hash mismatch"):
        ap.collect_sources(make_bundle(tmp_path / "t.zip", ["test:1"], tamper=True))


def test_make_row_statuses_and_warnings():
    src = {"record_id": "test:1", "stratum": "short", "source": SOURCE, "reference": REFERENCE,
           "source_sha256": sha(SOURCE), "reference_sha256": sha(REFERENCE), "source_receipt_sha256": "r"}
    ok = ap.make_row(src, stop())
    assert ok["generation_status"] == "completed" and ok["scoreable"] and ok["warnings"] == []
    assert ok["delivered_summary"] == ABSTRACT and set(ok["views"]) == {"S", "M", "L"}
    cut = ap.make_row(src, stop(finish_reason="length"))
    assert cut["generation_status"] == "completed_with_warning" and "no_terminal_eos_token_budget_exhausted" in cut["warnings"]
    loop = ap.make_row(src, stop(text=" ".join(["We repeat the same words again."] * 6)))
    assert "repetition" in loop["warnings"]
    for bad in ({"error": "prompt_too_long"}, {"text": "   ", "finish_reason": "stop"}, {"text": None}):
        failed = ap.make_row(src, bad)
        assert failed["generation_status"] == "failed" and failed["scoreable"] is False and failed["delivered_summary"] is None
    assert ap.make_row(src, {"error": "prompt_too_long"})["failure_reason"] == "prompt_too_long"


def long_outcome():
    return stop(text=" ".join(f"Sentence number {i} says something useful here." for i in range(120)))


def test_a_long_output_is_cut_at_the_contract_cap_on_a_sentence_boundary():
    src = {"record_id": "test:1", "stratum": "short", "source": SOURCE, "reference": REFERENCE,
           "source_sha256": sha(SOURCE), "reference_sha256": sha(REFERENCE), "source_receipt_sha256": "r"}
    row = ap.make_row(src, long_outcome())
    assert len(row["delivered_summary"].split()) <= ap.CONTRACT_CAP and row["delivered_summary"].endswith(".")
    assert len(row["views"]["S"].split()) <= 60 < len(row["views"]["L"].split()) <= 240


def sources(n):
    return [{"record_id": f"test:{i}", "stratum": "short", "source": SOURCE, "reference": REFERENCE,
             "source_sha256": sha(SOURCE), "reference_sha256": sha(REFERENCE), "source_receipt_sha256": "r"}
            for i in range(n)]


def test_generate_rows_resumes_and_retries_only_retryable_failures(tmp_path):
    out, calls = tmp_path / "o.jsonl", []

    def first(prompts):
        calls.append(len(prompts))
        return [stop(), {"error": "prompt_too_long"}, {"error": "RuntimeError"}, stop()][:len(prompts)]
    rows = ap.generate_rows(sources(4), first, out, batch_size=4)
    assert [r["generation_status"] for r in rows] == ["completed", "failed", "failed", "completed"]

    def second(prompts):
        calls.append(len(prompts))
        return [stop() for _ in prompts]
    rows = ap.generate_rows(sources(4), second, out, batch_size=4)
    assert calls == [4, 1]  # only the RuntimeError row is generated again; prompt_too_long is final
    assert [r["failure_reason"] for r in rows] == [None, "prompt_too_long", None, None]


def test_generate_rows_stops_after_two_failed_batches(tmp_path):
    out = tmp_path / "o.jsonl"
    with pytest.raises(RuntimeError, match="2 consecutive failed batches"):
        ap.generate_rows(sources(12), lambda prompts: [{"error": "CudaError"} for _ in prompts], out, batch_size=4)
    assert len(out.read_text().splitlines()) == 8  # never more than two batches of failure rows
    # A batch with one generated row is not a failed batch.
    mixed = tmp_path / "m.jsonl"
    rows = ap.generate_rows(sources(8), lambda prompts: [stop()] + [{"error": "CudaError"}] * (len(prompts) - 1), mixed, batch_size=4)
    assert sum(r["scoreable"] for r in rows) == 2


def test_a_torn_last_line_is_cut_off_the_file_so_the_next_row_is_not_lost(tmp_path):
    out = tmp_path / "o.jsonl"
    ap.generate_rows(sources(2), lambda prompts: [stop() for _ in prompts], out, batch_size=2)
    out.write_text(out.read_text() + '{"record_id": "test:9", "gener')
    rows = ap.generate_rows(sources(4), lambda prompts: [stop() for _ in prompts], out, batch_size=4)
    assert len(rows) == 4 and all(r["scoreable"] for r in rows)
    lines = out.read_text().splitlines()
    assert [json.loads(line)["record_id"] for line in lines] == ["test:0", "test:1", "test:2", "test:3"]  # every line parses
    with pytest.raises(ValueError, match="different number"):
        ap.generate_rows(sources(2), lambda prompts: [], tmp_path / "x.jsonl")


def test_a_retried_row_is_appended_again_and_latest_rows_keeps_one_per_record(tmp_path):
    out = tmp_path / "o.jsonl"
    ap.generate_rows(sources(3), lambda p: [stop(), {"error": "RuntimeError"}, stop()][:len(p)], out, batch_size=3)
    ap.generate_rows(sources(3), lambda p: [stop() for _ in p], out, batch_size=3)
    assert len(out.read_text().splitlines()) == 4  # 3 + the retried record
    latest = ap.latest_rows(out)
    assert [r["record_id"] for r in latest] == ["test:0", "test:1", "test:2"] and all(r["scoreable"] for r in latest)


def test_receipt_is_text_free_and_counts_statuses(tmp_path):
    out = tmp_path / "o.jsonl"
    rows = ap.generate_rows(sources(3), lambda p: [stop(), stop(finish_reason="length"), {"error": "prompt_too_long"}][:len(p)],
                            out, batch_size=3)
    receipt = ap.generation_receipt(rows)
    assert receipt["status_counts"] == {"completed": 1, "completed_with_warning": 1, "failed": 1}
    assert receipt["no_terminal_eos"] == 1 and receipt["failures"] == ["prompt_too_long"] and receipt["prompt_tokens_max"] == 10
    assert receipt["finish_reasons"] == {"length": 1, "stop": 1} and receipt["prompt_sha256"] == ap.PROMPT_SHA256
    assert receipt["decoding"]["seed"] == 20261031 and receipt["decoding"]["temperature"] == 0
    assert "steel" not in json.dumps(receipt)


def test_to_faithfulness_row_has_the_contract_view_and_views():
    src = {"record_id": "test:1", "stratum": "long", "source": SOURCE, "reference": REFERENCE,
           "source_sha256": sha(SOURCE), "reference_sha256": sha(REFERENCE), "source_receipt_sha256": "r"}
    row = ap.to_faithfulness_row(ap.make_row(src, stop()))
    assert row["candidate"] == "applm" and row["stratum"] == "long" and set(row["views"]) == {"contract", "S", "M", "L"}


def test_rouge_matches_the_scorer_v2_configuration():
    rouge = pytest.importorskip("rouge_score")  # noqa: F841
    scores = ap.rouge_scores("the cat sat on the mat", "the cat sat on the mat")
    assert scores == {"rouge1_f1": 1.0, "rouge2_f1": 1.0, "rougeL_f1": 1.0}


def metric_tables(ids, drop_applm=(), drop_bart=()):
    applm = {"rougeL_f1": {rid: 0.20 for rid in ids}, "rouge1_f1": {rid: 0.30 for rid in ids}}
    reference = {"led": {m: {rid: v for rid in ids} for m, v in (("rougeL_f1", 0.15), ("rouge1_f1", 0.25))},
                 "bart": {m: {rid: v for rid in ids} for m, v in (("rougeL_f1", 0.25), ("rouge1_f1", 0.35))}}
    for rid in drop_applm:
        applm["rougeL_f1"][rid] = None
    for rid in drop_bart:
        reference["bart"]["rouge1_f1"][rid] = None
    return applm, reference


def test_analysis_uses_one_cohort_for_every_metric_and_contrast():
    pytest.importorskip("experiments.scripts.tib_final523_analysis")
    ids = [f"test:{i}" for i in range(30)]
    strata = {rid: ap.STRATA[i % 3] for i, rid in enumerate(ids)}
    applm, reference = metric_tables(ids, drop_applm=["test:0"], drop_bart=["test:1"])
    result = ap.analyze(applm, reference, strata)
    assert result["c_applm_n"] == 28  # test:0 (applm rougeL) and test:1 (bart rouge1) leave the cohort for ALL metrics
    assert {c["n"] for c in result["contrasts"].values()} == {28}
    vs_led, vs_bart = result["contrasts"]["applm-led:rougeL_f1"], result["contrasts"]["applm-bart:rougeL_f1"]
    assert vs_led["mean"] == pytest.approx(0.05) and vs_led["low"] > 0
    assert vs_bart["mean"] == pytest.approx(-0.05) and vs_bart["high"] < 0
    assert result["means"]["rougeL_f1"] == pytest.approx({"applm": 0.20, "led": 0.15, "bart": 0.25})
    assert result["labels"] == "none" and result["label_kind"] == "exploratory_post_hoc"


def test_analysis_refuses_a_missing_reference_profile_or_metric():
    pytest.importorskip("experiments.scripts.tib_final523_analysis")
    ids = [f"test:{i}" for i in range(3)]
    strata = {rid: "short" for rid in ids}
    applm, reference = metric_tables(ids)
    with pytest.raises(ValueError, match="bart"):
        ap.analyze(applm, {"led": reference["led"]}, strata)
    del reference["bart"]["rouge1_f1"]
    with pytest.raises(ValueError, match="rouge1_f1"):
        ap.analyze(applm, reference, strata)
