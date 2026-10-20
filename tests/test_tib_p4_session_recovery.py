"""Session/context tests use synthetic VM IDs, not actual Colab execution evidence."""
import hashlib
import json
from pathlib import Path
import time

import pytest

from experiments.scripts import tib_p4_session_recovery as session
from experiments.scripts import tib_p4_recovery_context as context


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    package, drive = tmp_path / 'package', tmp_path / 'drive'
    package.mkdir(); drive.mkdir()
    layout = {'generation': 'old-generation/checkpoints', 'scorer': 'old-scorer/checkpoints'}
    for stage, relative in layout.items():
        file = drive / relative / 'sealed.json'
        write(file, {'original': stage})
        write(package / ('expected_' + stage + '.json'), {'files': {'sealed.json': session.sha(file)}})
    write(package / 'drive_layout.json', layout)
    write(package / 'recovery_manifest.json', {'files': {p.name: session.sha(p) for p in package.iterdir()}})
    boot = ['origin-VM']
    fingerprint = lambda: {'google_colab_imported': True, 'boot_id': boot[0], 'pid': 123,
                            'observed_epoch_ns': time.time_ns() + (10**9 if boot[0] != 'origin-VM' else 0)}
    monkeypatch.setattr(session, 'session_fingerprint', fingerprint)
    monkeypatch.setattr(context, 'session_fingerprint', fingerprint)
    witness = drive / 'recovery/origin_witness.json'
    session.seal_origin(package, drive, witness)
    return package, drive, witness, boot


def test_same_vm_even_new_python_process_is_not_fresh(workspace):
    package, drive, witness, boot = workspace
    with pytest.raises(ValueError, match='Same VM'):
        session.verify_fresh(package, drive, witness)


def test_fresh_boot_and_directory_identity_required(workspace):
    package, drive, witness, boot = workspace
    boot[0] = 'fresh-VM'
    assert session.verify_fresh(package, drive, witness)['different_vm_boot_id']
    (drive / 'old-generation/checkpoints/sealed.json').write_text('changed')
    with pytest.raises(ValueError, match='missing/changed'):
        session.verify_fresh(package, drive, witness)


def test_existing_origin_witness_never_replaced_in_new_vm(workspace):
    package, drive, witness, boot = workspace
    original = witness.read_bytes(); boot[0] = 'fresh-VM'
    with pytest.raises(ValueError, match='do not replace'):
        session.seal_origin(package, drive, witness)
    assert witness.read_bytes() == original


@pytest.mark.parametrize('stage', ['generation', 'scorer'])
def test_witness_and_output_cannot_enter_original_checkpoint_store(workspace, stage):
    package, drive, witness, boot = workspace
    bad = drive / ('old-' + stage) / 'checkpoints/new-receipt'
    with pytest.raises(ValueError, match='overlap'):
        context.create_run_context(package, drive, witness, bad)
    assert not bad.exists()


def test_stage_context_requires_current_vm_and_exact_output(workspace):
    package, drive, witness, boot = workspace; boot[0] = 'fresh-VM'
    output = drive / 'recovery/run1'
    context.create_run_context(package, drive, witness, output)
    path = output / 'session_context.json'
    bound = context.validate_stage_context(path, output / 'generation', 'generation')
    assert bound['recovery_boot_id'] == 'fresh-VM'
    with pytest.raises(ValueError, match='output'):
        context.validate_stage_context(path, output / 'wrong', 'generation')
    boot[0] = 'another-VM'
    with pytest.raises(ValueError, match='identity'):
        context.validate_stage_context(path, output / 'generation', 'generation')


def stage_receipts(package, drive, witness, output, *, stale=False):
    bound = context.validate_stage_context(output / 'session_context.json', output / 'generation', 'generation')
    if stale:
        bound['recovery_run_id'] = 'copied-from-old-run'
    write(output / 'generation/recovery_receipt.json', {'status': 'PASS', 'stage_session_context': bound,
          'new_generation_calls': 0, 'reused_outputs': 21, 'reused_nodes': 123,
          'denied_generation_attempts': 0, 'store_unchanged_verified': True, 'test_only': False})
    rows = [{'sample_id': str(i), 'failures': {}, 'metrics': dict.fromkeys(
        ['rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_f1', 'source_sentence_similarity_v1'], 0.5)} for i in range(21)]
    metric_path = output / 'scorer/metrics_replay.jsonl'
    metric_path.parent.mkdir(parents=True)
    metric_path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    write(output / 'scorer/scorer_replay_receipt.json', {'status': 'PASS', 'stage_session_context': bound,
          'new_metric_calls': 0, 'reused_records': 21, 'testing_dependency_injection': False,
          'stage_checks': {'original_store_unchanged': True},
          'artifact_sha256': {'metrics_replay.jsonl': session.sha(metric_path)}})


def test_combiner_rejects_stale_pass_copied_into_current_run(workspace):
    package, drive, witness, boot = workspace; boot[0] = 'fresh-VM'
    output = drive / 'recovery/run1'
    context.create_run_context(package, drive, witness, output)
    stage_receipts(package, drive, witness, output, stale=True)
    result = context.finalize(package, drive, witness, output)
    assert result['status'] == 'HOLD' and not result['cross_session_recovery_verified']


def test_combiner_verifies_both_stage_hashes_and_actual_counts(workspace):
    package, drive, witness, boot = workspace; boot[0] = 'fresh-VM'
    output = drive / 'recovery/run1'
    context.create_run_context(package, drive, witness, output)
    stage_receipts(package, drive, witness, output)
    result = context.finalize(package, drive, witness, output)
    assert result['status'] == 'PASS'  # synthetic fixture only; never real Colab proof
    assert set(result['stage_receipt_sha256']) == {'generation', 'scorer'}


def test_combiner_rejects_metrics_tampering(workspace):
    package, drive, witness, boot = workspace; boot[0] = 'fresh-VM'
    output = drive / 'recovery/run1'
    context.create_run_context(package, drive, witness, output)
    stage_receipts(package, drive, witness, output)
    (output / 'scorer/metrics_replay.jsonl').write_text('{}\n')
    result = context.finalize(package, drive, witness, output)
    assert result['status'] == 'HOLD'
