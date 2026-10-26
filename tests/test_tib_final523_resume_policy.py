"""The final523 scoring bundle carries the user's pre-run partial-resume policy, and the validator insists on it."""
import json
import shutil

import pytest

from experiments.scripts import tib_final523_scorer_bundle as builder
from experiments.scripts import tib_final523_scorer_validation as validation
from experiments.scripts import tib_pilot40_scorer_runner as runner
from final523_scoring_fixtures import build_final_bundle, make_final_world
from selection_scoring_fixtures import reseal


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    world = make_final_world(tmp_path_factory.mktemp("policy-world"))
    return world, build_final_bundle(world, tmp_path_factory.mktemp("policy-built"))


def test_the_registry_policy_is_the_users_pre_run_declaration():
    policy = json.loads(builder.RESUME_POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["declared_by"] == "user" and policy["post_hoc"] is False and policy["partial_resume_allowed"] is True
    assert policy["flag"] == "--resume-partial" and policy["runtime_binding"]["mode"] == "portable"
    assert policy["canary"]["rows"] == runner.CANARY_ROWS and policy["canary"]["tolerance_absolute_per_metric"] == runner.CANARY_TOLERANCE
    assert policy["scoring_start_authorized"] is False
    assert set(policy["runtime_binding"]["bound"]) == set(runner.PORTABLE_RUNTIME_FIELDS)


def test_the_bundle_ships_the_policy_and_binds_its_hash(built):
    _, (receipt, local, _) = built
    shipped = local / "bundle" / validation.RESUME_POLICY
    contract = json.loads((local / "bundle/scoring_contract.json").read_text())
    assert shipped.read_bytes() == builder.RESUME_POLICY_PATH.read_bytes()
    assert contract["resume_policy_sha256"] == builder.file_hash(shipped)
    assert validation.FINAL_STAGE["partial_resume_allowed"] is True and validation.FINAL_STAGE["portable_binding"] is True


def test_other_stages_do_not_get_the_opt_in():
    from experiments.scripts import tib_selection300_scorer_validation as selection
    assert "partial_resume_allowed" not in selection.SELECTION_STAGE and "portable_binding" not in selection.SELECTION_STAGE
    assert "partial_resume_allowed" not in runner.PILOT40_STAGE


@pytest.mark.parametrize("change", [
    lambda p: p.update(partial_resume_allowed=False),
    lambda p: p.update(declared_by="agent"),
    lambda p: p.update(post_hoc=True),
    lambda p: p.update(flag="--resume"),
])
def test_a_tampered_policy_is_refused_by_the_validator(built, tmp_path, change):
    _, (_, local, _) = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    path = copy / "bundle" / validation.RESUME_POLICY
    policy = json.loads(path.read_text())
    change(policy)
    path.write_text(json.dumps(policy))
    reseal(copy / "bundle")   # the manifest is honest, the contract hash is not
    with pytest.raises(ValueError, match="Resume policy"):
        validation.validate_final_scoring_bundle(copy / "bundle")


def test_a_missing_policy_file_is_refused(built, tmp_path):
    _, (_, local, _) = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    (copy / "bundle" / validation.RESUME_POLICY).unlink()
    reseal(copy / "bundle")
    with pytest.raises(FileNotFoundError):
        validation.validate_final_scoring_bundle(copy / "bundle")


@pytest.mark.parametrize("change", [lambda p: p.update(declared_by="agent"), lambda p: p.update(post_hoc=True),
                                    lambda p: p.update(partial_resume_allowed=False)])
def test_the_builder_refuses_a_policy_the_user_did_not_declare_before_the_run(built, tmp_path, change):
    world, _ = built
    policy = json.loads(builder.RESUME_POLICY_PATH.read_text(encoding="utf-8"))
    change(policy)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="pre-run declaration"):
        build_final_bundle(world, tmp_path / "b", resume_policy_path=path)


def test_the_builder_refuses_a_policy_whose_numbers_differ_from_the_runner(built, tmp_path):
    world, _ = built
    for change in (lambda p: p["canary"].update(rows=7), lambda p: p["canary"].update(tolerance_absolute_per_metric=1e-3),
                   lambda p: p["runtime_binding"].update(bound=["python"])):
        policy = json.loads(builder.RESUME_POLICY_PATH.read_text(encoding="utf-8"))
        change(policy)
        path = tmp_path / "policy.json"
        path.write_text(json.dumps(policy))
        with pytest.raises(ValueError, match="differ from the runner"):
            build_final_bundle(world, tmp_path / "b", resume_policy_path=path)
