"""Private source-only pilot40 packaging; never runs inference or changes cohorts."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / 'research-data/tib-pilot40-261020-v1'
REGISTRY = ROOT / 'experiments/registry/protocols/tib-pilot40-261020-v1'
QUAL = ROOT / 'research-data/tib-qualification-261019-1703'
SEALED = ROOT / 'experiments/registry/datasets/tib-text-model-benchmark-v1/qualification-261019-1703'
P4 = ROOT / 'experiments/registry/protocols/tib-model-benchmark-p4-261019-1802'
RECOVERY = ROOT / 'research-data/tib-p4-fresh-recovery-261020-v2/package'
ACTUAL = ROOT / 'experiments/registry/protocols/tib-p4-fresh-recovery-261020-v2/actual-colab-20261020T023840Z'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')


def sources():
    cohort = json.loads((SEALED / 'development_cohort.json').read_text())
    if sha(SEALED / 'qualification_policy.json') != cohort['policy_sha256']:
        raise ValueError('Sealed qualification policy differs')
    ids = cohort['selected_ids']['pilot']
    if len(ids) != len(set(ids)) or len(ids) != 40 or set(ids) & set(cohort['selected_ids']['selection']):
        raise ValueError('Expected exact sealed40, disjoint from selection')
    def selected(path):
        return {r['record_id']: r for r in map(json.loads, path.read_text(encoding='utf-8').splitlines())
                if r['record_id'] in ids}
    rights = selected(QUAL / 'source_use_ledger.jsonl')
    eligible = selected(QUAL / 'qualified_cohort/qualification_ledger.jsonl')
    canonical_path = QUAL / 'eda/canonical_records.jsonl.gz'
    eda = json.loads((QUAL / 'eda/receipt.json').read_text())
    if sha(canonical_path) != eda['files']['canonical_records.jsonl.gz']:
        raise ValueError('Canonical snapshot differs')
    with gzip.open(canonical_path, 'rt', encoding='utf-8') as handle:
        canonical = {r['record_id']: r for r in map(json.loads, handle) if r['record_id'] in ids}
    if any(set(v) != set(ids) for v in (canonical, rights, eligible)):
        raise ValueError('Incomplete pilot source evidence')
    rows, ledger = [], []
    low, high = cohort['source_word_cutpoints']
    for identifier in ids:
        source, right, qualified = canonical[identifier]['source_normalized'], rights[identifier], eligible[identifier]
        text_sha = hashlib.sha256(source.encode()).hexdigest()
        if not qualified['role_eligible'] or not right['allowed_for_current_local_use']:
            raise ValueError('Pilot eligibility/rights failed: ' + identifier)
        if text_sha != qualified['source_normalized_sha256'] or text_sha != right['source_normalized_sha256']:
            raise ValueError('Pilot source identity differs: ' + identifier)
        words = len(source.split())
        stratum = 'short' if words <= low else 'medium' if words <= high else 'long'
        attribution = {key: right[key] for key in ('author', 'title', 'source_url', 'released_license_raw',
                       'license_uri_canonical', 'modification_notice', 'conditions_recorded')}
        rows.append({'record_id': identifier, 'source_normalized': source,
                     'source_normalized_sha256': text_sha, 'source_stratum': stratum,
                     'source_words': words, 'attribution': attribution})
        ledger.append({'record_id': identifier, 'source_normalized_sha256': text_sha,
                       'group_id': qualified['group_id'], 'source_stratum': stratum,
                       'source_use_status': right['source_use_status'], 'allowed_for_current_local_use': True})
    if dict(Counter(r['source_stratum'] for r in rows)) != cohort['pilot_quotas']:
        raise ValueError('Sealed pilot strata differ')
    development = json.loads((QUAL / 'qualified_cohort/development_records.json').read_text())
    if {r['group_id'] for r in development['pilot']} & {r['group_id'] for r in development['selection']}:
        raise ValueError('Pilot/selection groups overlap')
    return cohort, rows, ledger


def build():
    package = LOCAL / 'package'
    package.mkdir(parents=True, exist_ok=True)
    cohort, rows, ledger = sources()
    original = RECOVERY / 'generation_bundle'
    recovery_manifest = json.loads((RECOVERY / 'recovery_manifest.json').read_text())
    for name, expected in recovery_manifest['files'].items():
        if name.startswith('generation_bundle/') and sha(RECOVERY / name) != expected:
            raise ValueError('Original generation dependency differs')
    shutil.copytree(original, package / 'original_generation', dirs_exist_ok=True)
    # Identical adapter modules in the new namespace; old bundle remains untouched.
    for path in (original / 'experiments').rglob('*.py'):
        dest = package / path.relative_to(original)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    names = ['tib_benchmark_acceptance', 'tib_p4_generation_recovery', 'tib_pilot_runtime',
             'tib_pilot_validation', 'tib_pilot_resources', 'tib_pilot_session']
    for name in names:
        shutil.copyfile(ROOT / 'experiments/scripts' / (name + '.py'),
                        package / 'experiments/scripts' / (name + '.py'))
    for src, name in [(RECOVERY / 'expected_generation.json', 'expected_generation.json'),
                      (ACTUAL / 'recovery/cross_session_recovery_receipt.json', 'actual_recovery_receipt.json'),
                      (ROOT / 'experiments/registry/protocols/tib-scorer-colab-runtime-261020-v1/actual-colab-20261020T010554Z/scorer_ready_receipt.json', 'actual_scorer_ready_receipt.json'),
                      (P4 / 'development-decision-261019-2341/intermediate_acceptance_policy_v1.json', 'acceptance_policy.json')]:
        shutil.copyfile(src, package / name)
    trials = json.loads((original / 'development_trials.json').read_text())
    proposals = json.loads((original / 'candidate_profiles.json').read_text())
    profiles = [{'candidate_id': p['candidate_id'], 'profile_id': p['candidate_id'], 'profile': p}
                for p in proposals['pipelines'] if p['candidate_id'] in ('lead3', 'lexrank')]
    profiles += [{'candidate_id': t['candidate_id'], 'profile_id': t['trial_id'], 'profile': t['profile']}
                 for t in trials['trials'] if t['trial_id'] in ('bart-control', 'led-ngram3', 'qwen-r384')]
    for entry in profiles:
        entry['profile_sha256'] = hashlib.sha256(json.dumps(entry['profile'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (package / 'pilot_sources.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    write(package / 'source_rights_ledger.json', ledger)
    write(package / 'pilot_contract.json', {'schema_version': 1, 'scope': 'Technical pilot generation only',
          'pilot_ids': cohort['selected_ids']['pilot'], 'source_strata': {r['record_id']: r['source_stratum'] for r in rows},
          'staged_ids': cohort['staged_pilot_ids'], 'profiles': profiles, 'word_cap': 350,
          'acceptance_policy_sha256': sha(package / 'acceptance_policy.json'),
          'original_bundle_manifest_sha256': sha(original / 'bundle_manifest.json'),
          'sealed_cohort_sha256': sha(SEALED / 'development_cohort.json'),
          'qualification_ledger_sha256': sha(QUAL / 'qualified_cohort/qualification_ledger.jsonl'),
          'rights_ledger_sha256': sha(QUAL / 'source_use_ledger.jsonl'), 'canonical_sha256': sha(QUAL / 'eda/canonical_records.jsonl.gz'),
          'pilot_quotas': cohort['pilot_quotas'], 'selection_disjoint_ids_and_groups_verified': True,
          'candidate_order': ['lead3', 'lexrank', 'bart', 'led', 'qwen3'], 'expected_matrix_cells': 200,
          'expected_imported_neural_cells': 9, 'expected_fresh_neural_cells': 111, 'expected_fresh_cpu_cells': 80,
          'metrics_executed': False, 'selection_authorized': False, 'final_test_authorized': False})
    requirements = (RECOVERY / 'requirements-recovery.txt').read_text()
    requirements += 'scikit-learn==1.6.1\nscipy==1.16.3\njoblib==1.6.0\nthreadpoolctl==3.7.0\n'
    (package / 'requirements-pilot.txt').write_text(requirements, encoding='utf-8')
    write(package / 'pilot_allocation.json', pilot_allocation())
    write(package / 'compute_budget.json', {**pilot_allocation(),
          'runtime_preflight_status': 'REQUIRED_NO_START_UNTIL_ACTUAL_CHECKS',
          'scope': 'Pilot40 only; full-study budget remains unset'})
    write(package / 'pilot_protocol.json', {
          'version': 'tib-pilot40-261020-v1', 'pilot_ids': cohort['selected_ids']['pilot'],
          'profile_ids': [p['profile_id'] for p in profiles], 'word_cap': 350,
          'allocation_sha256': sha(package / 'pilot_allocation.json'),
          'stop_order': ['lead3', 'lexrank', 'bart', 'led', 'qwen3'],
          'source_order': 'Unchanged sealed pilot ID order; no long-tail removal',
          'fresh_latency_frame': 'Fresh calls only; inherited costs and replay overhead reported separately',
          'partial_rule': 'Retain all40 per candidate; never relabel completed subset as complete',
          'retry_rule': 'No automatic retry of failed or interrupted attempted nodes/records',
          'metrics': 'Frozen scorer-ready/recovery dependency only; no metric execution in this generation bundle',
          'session_rule': 'At most2; cumulative ceilings; interrupted unobserved usage conservatively charged',
          'selection_authorized': False, 'final_test_authorized': False})
    manifest = {'schema_version': 1, 'files': {p.relative_to(package).as_posix(): sha(p)
                for p in sorted(package.rglob('*')) if p.is_file() and p.name != 'pilot_manifest.json' and '__pycache__' not in p.parts}}
    write(package / 'pilot_manifest.json', manifest)
    archive = LOCAL / 'tib-pilot40-261020-v1.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for name in manifest['files']:
            output.write(package / name, name)
        output.write(package / 'pilot_manifest.json', 'pilot_manifest.json')
    REGISTRY.mkdir(parents=True, exist_ok=True)
    for name in ('pilot_contract.json', 'pilot_manifest.json', 'requirements-pilot.txt',
                 'pilot_allocation.json', 'compute_budget.json', 'pilot_protocol.json'):
        shutil.copyfile(package / name, REGISTRY / name)
    receipt = {'status': 'PREPARED_ACTUAL_EXECUTION_REQUIRED', 'archive_local_path': str(archive),
               'archive_bytes': archive.stat().st_size, 'archive_sha256': sha(archive),
               'manifest_sha256': sha(package / 'pilot_manifest.json'), 'source_records': 40,
               'source_strata': cohort['pilot_quotas'], 'expected_matrix_cells': 200,
               'actual_pilot_executed': False, 'selection_start_authorized': False}
    write(REGISTRY / 'preparation_receipt.json', receipt)
    return receipt


def pilot_allocation():
    """User ceilings; nested reserves are not additional study budget or measured needs."""
    gib = 1024 ** 3
    return {'schema_version': 1, 'state': 'ALLOCATED', 'stage': 'pilot40_generation',
            'authorization': 'User2026-10-20 pilot40 allocation; not full study allocation',
            'total_gpu_hours': 11.5, 'total_cpu_hours': 23, 'total_wall_hours': 11.5,
            'session_wall_hours': 11.5, 'max_sessions': 2, 'session_headroom_fraction': .15,
            'default_session_slice_hours': 5.75,
            'persistent_storage_bytes': 2*gib, 'storage_capacity_bytes': 2*gib,
            'minimum_local_free_bytes': 32*gib, 'local_working_storage_bytes': 24*gib,
            'transfer_bytes': 16*gib, 'checkpoint_bytes': gib,
            'scoring_gpu_hours': 1.5, 'scoring_cpu_hours': 3, 'scoring_wall_hours': 1.5,
            'recovery_time_hours': .5, 'retry_limit_per_node': 0, 'retry_cost_reserve': 0,
            'checkpoint_flush_seconds': 0, 'checkpoint_flush_policy': 'fsync_after_every_committed_node',
            'transfer_wall_hours': .5, 'checkpoint_wall_hours': .25, 'session_overhead_hours': .75,
            'pilot_metric_tuning_trial_cap_per_candidate': 0,
            'pilot_feasibility_probe_cap_per_candidate': 0, 'pilot_total_profile_cap': 5,
            'max_records_per_pipeline': 40, 'candidate_order': ['lead3','lexrank','bart','led','qwen3'],
            'automatic_retries': False, 'node_forecast_safety_factor': 1.5,
            'ceilings_are_not_measured_needs': True, 'reserves_inside_totals': True,
            'scoring_runs_in_this_bundle': False, 'selection_start_authorized': False,
            'session_slice_note': 'Two 5.75h session grants preserve total11.5h; lost-session unobserved use charged conservatively',
            'reserve_note': 'Scoring wall reserve1.5h follows serial T4 GPU reserve; other suballocations are operating ceilings within total, not additions'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
