"""Bind both recovery subprocesses to the witnessed fresh VM and one output run."""
import json
import math
import os
from pathlib import Path
import time
import uuid

try:
    from tib_p4_session_recovery import sha, read_witness, session_fingerprint, verify_fresh, _safe_output
except ModuleNotFoundError:
    from .tib_p4_session_recovery import sha, read_witness, session_fingerprint, verify_fresh, _safe_output


def create_run_context(package, drive, witness, output):
    package, output, witness = Path(package).resolve(), Path(output).resolve(), Path(witness).resolve()
    _safe_output(package, drive, output)
    proof = verify_fresh(package, drive, witness)
    if any((output / stage).exists() for stage in ('generation', 'scorer')):
        raise ValueError('Recovery stage directory exists; use a new output run')
    output.mkdir(parents=True, exist_ok=True)
    context = {'schema_version': 1, 'recovery_run_id': str(uuid.uuid4()), 'created_epoch_ns': time.time_ns(),
               'recovery_manifest_sha256': sha(package / 'recovery_manifest.json'),
               'origin_witness_sha256': sha(witness), 'origin_witness_path': str(witness),
               'package_root': str(package), 'drive_root': str(Path(drive).resolve()),
               'recovery_boot_id': proof['recovery_session']['boot_id'], 'output_root': str(output)}
    with (output / 'session_context.json').open('x', encoding='utf-8') as handle:
        json.dump(context, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    return context


def validate_stage_context(context_path, output, stage):
    context_path, output = Path(context_path).resolve(), Path(output).resolve()
    context = json.loads(context_path.read_text())
    if stage not in ('generation', 'scorer') or output != Path(context['output_root']) / stage:
        raise ValueError('Stage output does not match this recovery run')
    if context_path != Path(context['output_root']) / 'session_context.json':
        raise ValueError('Unexpected session context location')
    package, drive = Path(context['package_root']), Path(context['drive_root'])
    _safe_output(package, drive, output)
    _safe_output(package, drive, Path(context['origin_witness_path']).parent)
    now = session_fingerprint()
    prior = read_witness(context['origin_witness_path'])
    if (sha(context['origin_witness_path']) != context['origin_witness_sha256']
            or sha(package / 'recovery_manifest.json') != context['recovery_manifest_sha256']
            or context['recovery_boot_id'] != now['boot_id']
            or now['boot_id'] == prior['origin_session']['boot_id']
            or not prior['origin_session'].get('google_colab_imported')
            or not prior['created_epoch_ns'] <= context['created_epoch_ns'] <= now['observed_epoch_ns']):
        raise ValueError('Stage VM/witness/package identity mismatch')
    if prior['recovery_manifest_sha256'] != context['recovery_manifest_sha256']:
        raise ValueError('Origin package does not match current recovery')
    return {k: context[k] for k in ('recovery_run_id', 'recovery_manifest_sha256',
                                   'origin_witness_sha256', 'recovery_boot_id')} | {'context_sha256': sha(context_path)}


def finalize(package, drive, witness, output):
    output = Path(output).resolve()
    _safe_output(package, drive, output)
    reasons, proof, hashes = [], None, {}
    generation, scorer = {}, {}
    try:
        proof = verify_fresh(package, drive, witness)
        expected_g = validate_stage_context(output / 'session_context.json', output / 'generation', 'generation')
        expected_s = validate_stage_context(output / 'session_context.json', output / 'scorer', 'scorer')
        for stage, name in (('generation', 'recovery_receipt.json'), ('scorer', 'scorer_replay_receipt.json')):
            path = output / stage / name
            hashes[stage] = sha(path)
        generation = json.loads((output / 'generation/recovery_receipt.json').read_text())
        scorer = json.loads((output / 'scorer/scorer_replay_receipt.json').read_text())
        if (generation.get('status') != 'PASS' or generation.get('stage_session_context') != expected_g
                or generation.get('new_generation_calls') != 0 or generation.get('reused_outputs') != 21
                or generation.get('reused_nodes') != 123 or generation.get('denied_generation_attempts') != 0
                or generation.get('store_unchanged_verified') is not True or generation.get('test_only') is not False):
            reasons.append('generation_stage_identity_counts_or_zero_call_proof_failed')
        if (scorer.get('status') != 'PASS' or scorer.get('stage_session_context') != expected_s
                or scorer.get('new_metric_calls') != 0 or scorer.get('reused_records') != 21
                or scorer.get('testing_dependency_injection') is not False
                or not scorer.get('stage_checks') or not all(scorer['stage_checks'].values())):
            reasons.append('scorer_stage_identity_counts_or_zero_call_proof_failed')
        metric_file = output / 'scorer/metrics_replay.jsonl'
        if sha(metric_file) != scorer['artifact_sha256']['metrics_replay.jsonl']:
            raise ValueError('Replayed metrics artifact hash differs')
        metrics = [json.loads(line) for line in metric_file.read_text().splitlines()]
        metric_keys = {'rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_f1', 'source_sentence_similarity_v1'}
        if (len(metrics) != 21 or len({row['sample_id'] for row in metrics}) != 21
                or any(set(row['metrics']) != metric_keys or row['failures']
                       or any(type(v) not in (int, float) or not math.isfinite(v) for v in row['metrics'].values())
                       for row in metrics)):
            raise ValueError('Expected21 rows and105 finite cached metrics')
    except Exception as error:
        reasons.append(f'{type(error).__name__}: {error}')
    passed = not reasons
    receipt = {'schema_version': 1, 'status': 'PASS' if passed else 'HOLD', 'reasons': reasons,
               'cross_session_recovery_verified': passed, 'session_proof': proof,
               'stage_receipt_sha256': hashes, 'generation_receipt': generation, 'scorer_receipt': scorer,
               'new_generation_calls': generation.get('new_generation_calls'),
               'new_metric_calls': scorer.get('new_metric_calls'), 'pilot40_authorized': False,
               'selection_start_authorized': False, 'note': 'Recovery only; resource/admission/budget gates remain separate.'}
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'cross_session_recovery_receipt.json').open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
    return receipt
