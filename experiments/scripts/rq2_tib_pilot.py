"""Development-only S1/S3 technical pilot; never freezes or selects by scores."""
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig, _save_result
from experiments.scripts.rq2_tib_benchmark_bundle import generation_input, validate_bundle
from experiments.scripts.rq2_tib_benchmark_pair import run_source_pair
from experiments.scripts.rq2_tib_benchmark_results import score_pair
from experiments.scripts.rq2_tib_pilot_runtime import TimedPilotBackend, code_identity, digest, hardware_profile


def _write(value, path):
    _save_result(value, Path(path))


def _receipt(rows, identity, directory, initialization_seconds, design, metric_profile):
    receipt = {'purpose':'development_technical_pilot_not_model_selection', 'cohort_frozen':False,
               'identity':identity, 'initialization_seconds':initialization_seconds,
               'design':design, 'metric_profile':metric_profile, 'rows':rows,
               'counts':{'selected':len(design['selected']), 'observed':sum(r['status']!='not_attempted' for r in rows),
                         'label_valid':len(design['selected']), 'media_valid':0,
                         'evaluated':sum(bool(r.get('scores')) for r in rows),
                         'failed':sum(r['status'] in {'failed','interrupted'} for r in rows),
                         'not_attempted':sum(r['status']=='not_attempted' for r in rows)},
               'observed_unit':'selected source records entering the pilot, not media decoding',
               'label_valid_scope':'released creator abstract passes structural screening; not verified factual GT',
               'media_valid_scope':'video_not_required_for_text_only_claim',
               'quality_selection_allowed':False,
               'failure_policy':'no automatic retry; retain every selected ID and unknown usage',
               'deadline_policy':'soft wall stop between dispatches; not a hard kernel timeout'}
    _write(receipt, directory/'pilot-receipt.json')
    return receipt


def run_pilot(backend, bundle, design, *, output_dir, initialization_seconds,
              config=None, wall_limit_seconds=7200, on_event=None):
    """Run only a source-length-selected train subset, with counterbalanced arms."""
    validate_bundle(bundle)
    if any(r['split']!='train' for r in bundle['items']) or len(bundle['items'])!=len(design['selected']):
        raise ValueError('Technical pilot must use the declared train-only subset')
    declared = {r['id']:r['source_sha256'] for r in design['selected']}
    actual = {f"{r['split']}/{r['source_index']}":r['source_sha256'] for r in bundle['items']}
    if declared != actual or len(declared)!=len(design['selected']):
        raise ValueError('Pilot bundle IDs/source hashes differ from declared design')
    config = config or BenchmarkConfig()
    config.validate()
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
    profile = hardware_profile(backend)
    identity = {'code':code_identity(), 'profile':profile, 'config':asdict(config),
                'selection':bundle['metadata']['selection_sha256'],
                'source_selection':design['selection_source_sha256'],
                'budget_policy':'equal_allocated_map_and_final_caps_common_prompt_cap_actual_usage_measured',
                'timeout_policy':{'wall_limit_seconds':wall_limit_seconds, 'automatic_retries':0}}
    path = directory/'pilot-identity.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=identity:
        raise ValueError('Pilot code/config/cohort/hardware changed; use a NEW output directory')
    _write(identity, path)
    wrapped = TimedPilotBackend(backend, directory/'dispatches.jsonl', wall_limit_seconds=wall_limit_seconds)
    ledger = {r['id']:r for r in design['selected']}
    rows = []
    for index, item in enumerate(bundle['items']):
        ident = f"{item['split']}/{item['source_index']}"
        result_path = directory/f"train-{item['source_index']}.json"
        old = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else None
        if old and old['status'] in {'generated','completed'}:
            rows.append({**old, 'resumed':True})
            _receipt(rows, identity, directory, initialization_seconds, design, 'rouge_l_only')
            continue
        row = {**ledger[ident], 'status':'in_progress', 'arms':{}, 'checkpoint_seconds':0.0,
               'scoring_seconds':None, 'shared_preparation_seconds':None, 'resumed':old is not None,
               'prior_attempts':([*old.get('prior_attempts', []), old] if old else [])}
        def checkpoint(partial):
            started = time.perf_counter()
            row.update(partial)
            _write(row, result_path)
            row['checkpoint_seconds'] += time.perf_counter()-started
        wrapped.item_id = ident
        def emit(event):
            wrapped.arm = event.get('arm', wrapped.arm)
            if on_event:
                on_event({**event, 'id':ident, 'index':index+1, 'total':len(bundle['items'])})
        interrupted = False
        try:
            if wrapped.blocked_reason:
                row.update(status='not_attempted', error=wrapped.blocked_reason)
            else:
                pair = run_source_pair(generation_input(item), wrapped, config,
                    on_progress=checkpoint, on_event=emit,
                    arm_order=('S1','S3') if index%2==0 else ('S3','S1'),
                    continue_on_arm_failure=True, reject_empty=True)
                row.update(pair)
                if all(a['status']=='completed' for a in row['arms'].values()) and len(row['arms'])==2:
                    started = time.perf_counter()
                    row['scores'] = score_pair(row['arms'], item['reference_text'])
                    row.update(scoring_seconds=time.perf_counter()-started, status='generated')
                else:
                    row.update(status='failed', error='one_or_more_arms_failed; inspect arm and dispatch receipts')
        except (ValueError, RuntimeError, OSError, KeyboardInterrupt) as exc:
            interrupted = isinstance(exc, KeyboardInterrupt)
            row.update(status='interrupted' if interrupted else 'failed', error=f'{type(exc).__name__}: {exc}')
        checkpoint(row)
        rows.append(row)
        _receipt(rows, identity, directory, initialization_seconds, design, 'rouge_l_only')
        if interrupted:
            break
    return _receipt(rows, identity, directory, initialization_seconds, design, 'rouge_l_only')


def evaluate_pilot(receipt, bundle, semantic_scorer, *, output_dir, metric_initialization_seconds):
    """Reuse predictions, measure existing secondary scorers after freeing generator."""
    directory = Path(output_dir)
    if receipt['identity']['code'] != code_identity():
        raise ValueError('Pilot source changed before evaluation; preserve receipt and use a NEW pilot root')
    profile = receipt['identity']['profile']
    current = hardware_profile(SimpleNamespace(device=profile['device'], model_id=profile['model'],
        tokenizer_id=profile['tokenizer'], map_batch_size=profile['map_batch_size']))
    receipt['evaluation_hardware_profile'] = current
    receipt['metric_hardware_matches_generation'] = current == profile
    references = {f"{r['split']}/{r['source_index']}":r for r in bundle['items']}
    receipt['metric_initialization_seconds'] = metric_initialization_seconds
    receipt['semantic_metadata'] = getattr(semantic_scorer, 'metadata', None)
    for row in receipt['rows']:
        if row['status']=='completed' and 'semantic_scores' in row:
            row['resumed'] = True
            continue
        if row['status']!='generated':
            continue
        item = references[row['id']]
        started = time.perf_counter()
        try:
            row['semantic_scores'] = semantic_scorer.score_pair(row['arms'], item['reference_text'], item['source_text'])
            row['status'] = 'completed'
        except (ValueError, RuntimeError, OSError, ImportError, KeyboardInterrupt) as exc:
            row.update(status='evaluation_failed', evaluation_error=f'{type(exc).__name__}: {exc}')
        row['scoring_seconds'] += time.perf_counter()-started
        checkpoint_started = time.perf_counter()
        _write(row, directory/f"train-{item['source_index']}.json")
        row['checkpoint_seconds'] += time.perf_counter()-checkpoint_started
        receipt.update(metric_profile='rouge_l_bertscore_sbertscore',
                       counts={**receipt['counts'], 'semantic_evaluated':sum(r['status']=='completed' for r in receipt['rows']),
                               'semantic_failed':sum(r['status']=='evaluation_failed' for r in receipt['rows'])})
        _write(receipt, directory/'pilot-receipt.json')
        if row['status']=='evaluation_failed':
            # Unknown evaluator/device state; preserve the receipt and stop.
            break
    return receipt


def forecast_receipt(receipt, *, population_by_stratum=None):
    from experiments.scripts.rq2_tib_pilot_forecast import forecast_pilot
    init = receipt.get('initialization_seconds')
    metric_init = receipt.get('metric_initialization_seconds')
    complete_init = init+metric_init if isinstance(init, (int,float)) and isinstance(metric_init, (int,float)) else None
    rows = list(receipt['rows'])
    for selected in receipt['design']['selected']:
        if not any(r['id']==selected['id'] for r in rows):
            rows.append({**selected, 'status':'not_attempted'})
    return forecast_pilot(rows, initialization_seconds=complete_init,
        population_by_stratum=population_by_stratum or receipt['design']['population_by_stratum'],
        length_range_covered=not receipt['design']['full_pool_exceeds_pilot_length_range'],
        hardware_consistent=(receipt['metric_profile']=='rouge_l_bertscore_sbertscore'
            and receipt.get('metric_hardware_matches_generation', False)))
