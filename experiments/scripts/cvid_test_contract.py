"""Pinned EDA prerequisites and versioned test protocol, without model loading."""
import copy
import json
from pathlib import Path

import pandas as pd

from experiments.scripts.cvid_eda_common import OUT, ROOT, sha, validate_artifacts
from experiments.scripts.cvid_eda_notebook_support import verify_reviews
from experiments.scripts.cvid_test_source import require

NAME = 'iiit-cvid-spotting-test-261014'
REGISTRY = ROOT/'experiments/registry/datasets'
EDA_RECEIPT = REGISTRY/'iiit-cvid-all-splits-eda-261014.json'
EDA_SHA = 'f79357888cda6e8407c5521f808bce982ee9b519f7842c7dad747a6f6bcb5a27'
BASE_PROTOCOL = REGISTRY/'iiit-cvid-spotting-validation-261013-protocol.json'
BASE_SHA = '8fde6c6d6dab81c7321b68c09738253b143c5a22fb96f2b38912c3471616e55e'


def descriptor(path):
    path = Path(path)
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), bytes=path.stat().st_size)


def prerequisites():
    require(sha(EDA_RECEIPT) == EDA_SHA, 'executed EDA receipt changed')
    require(sha(BASE_PROTOCOL) == BASE_SHA, 'inherited scoring protocol changed')
    receipt = json.loads(EDA_RECEIPT.read_text(encoding='utf-8'))
    require(receipt['fresh_kernel'] and receipt['executed_code_cells'] == 16 and receipt['saved_errors'] == 0, 'EDA execution incomplete')
    for key in ('notebook','html','eda_summary'):
        require(sha(ROOT/receipt[key]['path']) == receipt[key]['sha256'], 'EDA execution artifact mismatch: '+key)
    summary = json.loads((ROOT/receipt['eda_summary']['path']).read_text(encoding='utf-8'))
    validate_artifacts(summary)
    for name, expected in summary['code_sha256'].items():
        require(sha(ROOT/'experiments/scripts'/name) == expected, 'EDA module changed: '+name)
    for name, expected in summary['existing_spotting_freeze_sha256'].items():
        require(sha(ROOT/name) == expected, 'existing validation/candidate freeze changed: '+name)
    frames = pd.read_csv(OUT/'frames.csv.gz',keep_default_na=False,dtype={'course':str})
    objects = pd.read_csv(OUT/'objects.csv.gz',keep_default_na=False,dtype={'course':str})
    require(not frames.frame_id.duplicated().any() and not objects.object_id.duplicated().any(), 'duplicate EDA IDs')
    _, semantic = verify_reviews(frames, objects)
    return frames, objects, semantic, summary


def test_protocol(policy, policy_descriptor):
    protocol = copy.deepcopy(json.loads(BASE_PROTOCOL.read_text(encoding='utf-8')))
    protocol.update(schema='iiit_cvid_spotting_test_protocol_v1', protocol_id=NAME, frozen_date='2026-10-14',
                    status='test_cohort_and_gt_policy_frozen_before_study_spotting_outcomes',
                    claim=policy['scope']+'; descriptive EDA-exposed course-held-out released-label agreement')
    protocol['inherited_protocol'] = descriptor(BASE_PROTOCOL)
    protocol['gt_policy'] = policy_descriptor
    protocol['source'].update(split='test',annotation_creator_qc='not_certified; semantic flags and selective coverage preserved explicitly')
    protocol['cohort'] = dict(rule=policy['eligibility'], courses=['10','14','18','20','24','3','7'],
                              source_group_count=276, independence='course/video folders are unverified source proxies',
                              duplicate_review='no exact duplicate frames; all 469 dHash candidates reviewed different within that queue only')
    protocol['text']['do_not_care'] = 'none; native test difficult flags are 0; literal * and selective labels retained as released'
    protocol['annotation_scope'] = policy['selective_annotation']
    protocol['semantic_flag_sensitivity'] = policy['semantic_flag_sensitivity']
    protocol['metrics']['required'] += ['unweighted mean of per-course spotting Hmean and detection F1; retain seven course counts',
        'primary plus observed_flag_frame_influence; both denominators and candidate B-minus-A differences',
        'review flags are separate post-scoring diagnostics, never candidate inputs']
    bootstrap = dict(method='paired nonparametric cluster bootstrap; sample K cluster IDs with replacement per replicate, retain whole clusters',
        statistic='candidate B minus A pooled micro spotting Hmean, recomputed from resampled TP/FP/FN totals',
        draws=2000, seed=20261014, rng='Python random.Random(seed).choice(sorted IDs), fresh RNG for each endpoint/grouping',
        interval='sort N differences; lower at floor(0.025*N), upper at floor(0.975*N)-1, zero-based; no interpolation',
        pairing='same frame IDs and cluster assignments for both candidates; no complete-case removal of failed frames',
        limitation='few course proxies and uncertain dependence; exploratory conditional intervals, no generalization/power claim')
    protocol['metrics']['primary_uncertainty'] = dict(bootstrap,group_key='course',K=7,sorted_ids=['10','14','18','20','24','3','7'])
    protocol['metrics']['secondary_uncertainty'] = dict(bootstrap,group_key='source_group',K=276,sorted_ids='lexicographic sorted frozen source_group IDs')
    protocol['metrics']['selection'] = 'descriptive differences only; no generalized/production winner; report ranking sensitivity rather than choose favorable endpoint'
    protocol['execution_gate'] = dict(status='pending_candidate_runtime_loading_validation; no spotting inference in this freeze',
        configuration_selection='reuse pinned candidate defaults/configuration without test tuning; no GT-based prediction filtering',
        required_before_any_inference=['test cohort/GT/policy/protocol and candidate binding verified',
            'pinned model files/config/source hashes and locked runtime loading verified',
            'run identity binds source pixels, test freeze, weights, decoder, preprocessing, thresholds, grouping and failure schema'])
    protocol['scientific_sources'] = policy['scientific_sources']
    return protocol


def sensitivity_selection(policy, semantic, gt):
    test_flags = semantic[semantic.split.eq('test') & semantic.decision.isin(['uncertain','apparent_disagreement'])]
    observed = sorted('Frames/'+f for f in set(test_flags.frame_id))
    spec = policy['semantic_flag_sensitivity']
    require(observed == spec['excluded_frame_ids'], 'fixed semantic influence frame IDs changed')
    require(sorted(test_flags.sample_id) == spec['flagged_sample_ids'], 'fixed semantic influence sample IDs changed')
    selected = {r['frame_id'] for r in gt}
    require(set(observed) <= selected, 'influence frame outside primary cohort')
    retained = [r for r in gt if r['frame_id'] not in observed]
    require(len(retained) == spec['expected_frames'] and sum(len(r['objects']) for r in retained) == spec['expected_objects'], 'influence denominator changed')
    return dict(schema='iiit_cvid_observed_flag_frame_influence_v1', excluded_frame_ids=observed,
        flagged_objects=test_flags.to_dict('records'), selected_frame_ids=[r['frame_id'] for r in retained],
        selected_frames=len(retained), selected_objects=sum(len(r['objects']) for r in retained),
        excluded_frames=len(observed), excluded_objects=40, primary_gt_unchanged=True,
        limit=spec['limits'])
