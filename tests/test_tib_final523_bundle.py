"""Final523 generation bundle: builds reproducibly, validates, stays unauthorized, refuses a missing choice or drifted seal."""
import json
import shutil
import zipfile

import pytest

from experiments.scripts import tib_final523_bundle as bundle
from experiments.scripts import tib_selection_validation as validation


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("final523")
    registry = root / "registry"
    registry.mkdir()
    shutil.copyfile(bundle.REGISTRY / bundle.FINAL_COHORT, registry / bundle.FINAL_COHORT)
    first = bundle.build(root / "local-a", registry)
    second = bundle.build(root / "local-b", registry)
    return root, registry, first, second


def test_two_builds_are_byte_identical(built):
    _, _, first, second = built
    assert first["archive_sha256"] == second["archive_sha256"] and first["manifest_sha256"] == second["manifest_sha256"]


def test_package_validates_and_has_the_final_shape(built):
    root, _, receipt, _ = built
    contract, rows, manifest_sha = validation.validate_bundle(root / "local-a" / "package")
    assert manifest_sha == receipt["manifest_sha256"] and len(rows) == 523
    assert contract["stage"] == "final523" and contract["expected_cells"] == 523 * 4
    assert contract["candidate_order"] == ["lead3", "lexrank", "bart", "led"] and contract["word_cap"] == 350
    assert len(contract["excluded_pilot_ids"]) == 40 and len(contract["excluded_selection_ids"]) == 300
    assert all(i.startswith("test:") for i in contract["selection_ids"])


def test_bundle_never_authorizes_a_start(built):
    root, _, receipt, _ = built
    contract = json.loads((root / "local-a/package/selection_contract.json").read_text(encoding="utf-8"))
    assert contract["selection_authorized"] is False and contract["final_test_authorized"] is False
    assert receipt["final_test_authorized"] is False and receipt["selection_start_authorized"] is False
    assert not list((root / "local-a/package").rglob("start_authorization*"))


def test_choice_and_seal_are_locked_and_hashed(built):
    root, registry, _, _ = built
    contract = json.loads((root / "local-a/package/selection_contract.json").read_text(encoding="utf-8"))
    assert contract["locked_choice"]["selected_profile"] == "led"
    for name in ("final_cohort.json", "selection300_analysis_result.json", "analysis_declarations_261024_v1.json"):
        assert name in contract["locked_artifacts"]
    assert contract["final_cohort_sha256"] == bundle.sha(registry / bundle.FINAL_COHORT)


def test_zip_holds_exactly_the_manifest_files(built):
    root, _, receipt, _ = built
    manifest = json.loads((root / "local-a/package/selection_manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(root / "local-a" / bundle.ARCHIVE_NAME) as z:
        assert set(z.namelist()) == set(manifest["files"]) | {"selection_manifest.json"}
        assert {info.date_time for info in z.infolist()} == {bundle.FIXED_ZIP_TIME}
    assert bundle.sha(root / "local-a" / bundle.ARCHIVE_NAME) == receipt["archive_sha256"]


def keys_of(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys_of(inner)


def forbidden(keys):
    return [k for k in keys if "reference" in k.lower() or "abstract" in k.lower()]


def test_no_reference_or_abstract_key_anywhere_and_no_source_text_in_the_registry_copies(built):
    root, registry, _, _ = built
    for name in ("selection_contract.json", "node_forecast.json", "selection_allocation.json", "preparation_receipt.json"):
        keys = set(keys_of(json.loads((registry / name).read_text(encoding="utf-8"))))
        assert not forbidden(keys) and "source_normalized" not in keys
    package = root / "local-a/package"
    for line in (package / "selection_sources.jsonl").read_text(encoding="utf-8").splitlines():
        assert not forbidden(keys_of(json.loads(line)))
    assert not forbidden(keys_of(json.loads((package / "selection_contract.json").read_text(encoding="utf-8"))))


def test_written_files_have_no_windows_newlines(built):
    root, _, _, _ = built
    package = root / "local-a/package"
    for name in ("selection_sources.jsonl", "selection_contract.json", "selection_manifest.json", "selection_allocation.json"):
        assert b"\r\n" not in (package / name).read_bytes(), name


def test_the_final_cohort_comes_from_the_registry_argument(tmp_path):
    registry = tmp_path / "registry"
    registry.mkdir()
    shutil.copyfile(bundle.REGISTRY / bundle.FINAL_COHORT, registry / bundle.FINAL_COHORT)
    bundle.build(tmp_path / "local", registry)
    locked = tmp_path / "local/package/locked" / bundle.FINAL_COHORT
    assert locked.read_bytes() == (registry / bundle.FINAL_COHORT).read_bytes()


def test_no_locked_choice_stops_the_build(tmp_path):
    result = json.loads((bundle.ANALYSIS / "selection300_analysis_result.json").read_text(encoding="utf-8"))
    result.update(label="no_selection", selected_profile=None)
    (tmp_path / "selection300_analysis_result.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="no locked choice"):
        bundle.locked_choice(tmp_path)


@pytest.mark.parametrize("change,text", [
    (lambda c: c.update(final_test_authorized=True), "sealed, unauthorized"),
    (lambda c: c.update(generation_executed=True), "sealed, unauthorized"),
    (lambda c: c.update(final_test_sealed=False), "sealed, unauthorized"),
    (lambda c: c.update(quotas={"short": 183, "medium": 171, "long": 169}), "quotas"),
    (lambda c: c.update(qualification_ledger_sha256="0" * 64), "changed since the seal"),
    (lambda c: c["selected_ids"].__setitem__(0, c["selected_ids"][1]), "Expected exact"),
])
def test_drifted_seal_is_refused(tmp_path, change, text):
    cohort = json.loads((bundle.REGISTRY / bundle.FINAL_COHORT).read_text(encoding="utf-8"))
    change(cohort)
    (tmp_path / bundle.FINAL_COHORT).write_text(json.dumps(cohort), encoding="utf-8")
    with pytest.raises(ValueError, match=text):
        bundle.final_sources(tmp_path)
