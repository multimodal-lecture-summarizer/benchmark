"""Verify exact operating sizes, source-only strata and group role reservation."""
import pytest

from experiments.scripts.tib_model_benchmark_sampling import quotas, select_development
from experiments.scripts.tib_model_benchmark_qualification import qualify_rows, run


def validation(n):
    return [{"record_id": f"valid:{i}", "split": "valid", "group_id": f"g{i}",
             "source_words": (i % 3) * 1000 + i // 3 + 1} for i in range(n)]


def test_40_300_stable_with_no_group_overlap_or_input_order_dependency():
    rows = validation(430)
    rows[1]["group_id"] = rows[0]["group_id"]
    forward = select_development(rows, [1000, 2000])
    backward = select_development(list(reversed(rows)), [1000, 2000])
    assert forward == backward
    assert len(forward["pilot"]) == 40 and len(forward["selection"]) == 300
    assert not ({r["group_id"] for r in forward["pilot"]} & {r["group_id"] for r in forward["selection"]})
    assert not forward["selection_fallback"]
    assert all(n >= 25 for n in forward["selection_quotas"].values())


def test_availability_only_fallback_200_and_stop_below_200():
    result = select_development(validation(280), [1000, 2000])
    assert result["selection_fallback"] and len(result["selection"]) == 200
    with pytest.raises(ValueError, match="Below 200"):
        select_development(validation(239), [1000, 2000])
    bad = validation(400); bad[0]["split"] = "test"
    with pytest.raises(ValueError, match="validation only"):
        select_development(bad, [1000, 2000])


def test_source_strata_empty_floor_is_a_gate_not_silent_relabeling():
    with pytest.raises(ValueError, match="strata"):
        quotas(300, {"short": 200, "medium": 200, "long": 2}, 25)


def frames():
    metadata, rights, references, groups = {}, {}, {}, {}
    for name, group in [("train:0", "tuned"), ("test:0", "tuned"), ("valid:0", "fresh"), ("test:1", "fresh")]:
        metadata[name] = {"record_id": name, "split": name.split(":")[0], "source_words": 100,
                          "structure_pass": True, "language": "en", "source_raw_sha256": name,
                          "reference_raw_sha256": "ref"}
        rights[name] = {"source_raw_sha256": name, "reference_raw_sha256": "ref",
                        "allowed_for_reference_scoring": True, "source_use_status": "conditional"}
        references[name] = {"source_raw_sha256": name, "reference_raw_sha256": "ref", "reference_label": "B"}
        groups[name] = {"group_id": group, "source_raw_sha256": name}
    return metadata, rights, references, groups


def test_tuning_blocks_linked_test_and_protects_fresh_test_before_valid():
    args = frames()
    rows = {r["record_id"]: r for r in qualify_rows(*args, old_ids={"train:0"})}
    assert rows["test:0"]["exposure_reasons"] == ["linked_known_tuning_group"]
    assert rows["valid:0"]["exposure_reasons"] == ["protected_native_test_group"]
    assert rows["test:1"]["role_eligible"] is True
    assert rows["test:1"]["eda_exposed"] is True


def test_mixed_versions_and_truthy_rights_never_qualify():
    args = frames()
    args[1]["train:0"]["allowed_for_reference_scoring"] = "hold"
    with pytest.raises(ValueError, match="boolean"):
        qualify_rows(*args, old_ids=set())
    args = frames(); args[2]["train:0"]["reference_raw_sha256"] = "different"
    with pytest.raises(ValueError, match="hash mismatch"):
        qualify_rows(*args, old_ids=set())


def test_existing_cohort_is_preserved_even_if_no_policyfile(tmp_path):
    registry = tmp_path / "registry"
    registry.mkdir()
    existing = registry / "development_cohort.json"
    existing.write_text("existing sealed evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="must not be overwritten"):
        run(tmp_path / "root", registry, tmp_path / "not-loaded")
    assert existing.read_text(encoding="utf-8") == "existing sealed evidence"


def test_reviewed_a_retains_a_eligibility_label():
    args = frames()
    args[2]["test:1"]["reference_label"] = "A"
    rows = {row["record_id"]: row for row in qualify_rows(*args, old_ids=set())}
    assert rows["test:1"]["role_eligible"] is True
    assert rows["test:1"]["eligibility_status"] == "eligible"
