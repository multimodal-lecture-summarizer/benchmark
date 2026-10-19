"""Freeze released-label native test after EDA; never infer OCR or repair GT."""
import argparse
from collections import Counter, defaultdict
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import unicodedata

from experiments.scripts.cvid_eda_common import EXPECTED, ROOT, SOURCE, sha
from experiments.scripts.cvid_test_contract import (
    NAME, REGISTRY, EDA_RECEIPT, descriptor, prerequisites, sensitivity_selection, test_protocol,
)
from experiments.scripts.cvid_test_source import require, scan_test
from experiments.scripts.freeze_iiit_cvid_spotting import frozen_write, json_bytes

DERIVED = ROOT/'experiments/outputs'/NAME
DEPENDENCIES = ['freeze_cvid_test_spotting.py','cvid_test_contract.py','cvid_test_source.py','cvid_test_scoring.py',
    'freeze_iiit_cvid_spotting.py','spotting_metrics.py','cvid_eda_common.py','cvid_eda_notebook_support.py',
    'cvid_eda_pair_review.py','inventory_cvid_splits.py','qualification_visual_pairs.py','verify_cvid_test_freeze.py']


def bundle_descriptor(path, data):
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def write_bundle(bundle, dry_run=False):
    """Reject every pre-existing difference before any write; receipt commits last."""
    for path, data in bundle.items():
        require(path.resolve().is_relative_to(ROOT.resolve()), 'output outside benchmark root')
        if path.exists() and path.read_bytes() != data:
            raise ValueError('frozen artifact differs; use a new version: '+str(path))
    if not dry_run:
        for path, data in bundle.items():
            frozen_write(path, data)


def verify_snapshot(snapshot):
    for name, expected in snapshot.items():
        require(sha(ROOT/name) == expected, 'input changed during freeze: '+name)


def build_bundle(archive):
    # Capture bytes before parsing and hashes before the long source scan.
    implementation = {n:sha(Path(__file__).with_name(n)) for n in DEPENDENCIES}
    require(sha(archive) == EXPECTED, 'source archive identity mismatch')
    policy_path = REGISTRY/(NAME+'-gt-policy.json')
    candidates_path = REGISTRY/'iiit-cvid-spotting-candidates-261014.json'
    policy_bytes, candidate_bytes = policy_path.read_bytes(), candidates_path.read_bytes()
    policy_entry = bundle_descriptor(policy_path,policy_bytes)
    candidate_entry = bundle_descriptor(candidates_path,candidate_bytes)
    policy, candidates = json.loads(policy_bytes), json.loads(candidate_bytes)
    require(policy['policy_id'] == NAME and not policy['primary_reference']['text_corrections'], 'unsupported policy version')
    frames, objects, semantic, summary = prerequisites()
    eda_receipt = json.loads(EDA_RECEIPT.read_text(encoding='utf-8'))
    snapshot = dict(summary['existing_spotting_freeze_sha256'])
    snapshot.update({item['path']:item['sha256'] for item in summary['artifacts']})
    snapshot.update({eda_receipt[k]['path']:eda_receipt[k]['sha256'] for k in ('notebook','html','eda_summary')})
    snapshot.update({entry['path']:entry['sha256'] for entry in (policy_entry,candidate_entry,descriptor(EDA_RECEIPT))})
    snapshot.update({'experiments/scripts/'+n:h for n,h in implementation.items()})
    verify_snapshot(snapshot)
    source_frames, gt, holds = scan_test(archive,frames,objects)
    require([h['frame_id'] for h in holds] == policy['eligibility']['expected_held_frame_ids'], 'held frame IDs changed')
    sensitivity = sensitivity_selection(policy,semantic,gt)
    course_rows = defaultdict(lambda: dict(frames=0,objects=0,metadata_repairs=0,source_groups=set()))
    for frame in source_frames:
        if frame['selected']:
            row = course_rows[frame['course']]
            row['frames'] += 1
            row['objects'] += frame['object_count']
            row['metadata_repairs'] += frame['decision']=='REPAIR_METADATA_DERIVED'
            row['source_groups'].add(frame['source_group'])
    for row in course_rows.values():
        row['source_groups'] = sorted(row['source_groups'])
    bundle = {
        DERIVED/'ground-truth.jsonl': b''.join((json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n').encode() for r in gt),
        REGISTRY/(NAME+'-selected-frame-ids.txt'): ''.join(r['frame_id']+'\n' for r in gt).encode(),
        REGISTRY/(NAME+'-annotation-holds.json'): json_bytes(holds),
        REGISTRY/(NAME+'-influence.json'): json_bytes(sensitivity),
    }
    derived = [bundle_descriptor(p,b) for p,b in bundle.items()]
    manifest = dict(schema='iiit_cvid_spotting_test_cohort_v1',cohort_id=NAME,
        source_zip_sha256=EXPECTED, selected_split='test',source_frames=1755,source_objects=40103,
        selected_frames=len(gt),selected_objects=sum(len(r['objects']) for r in gt),
        decisions=dict(Counter(f['decision'] for f in source_frames)),
        courses=sorted(course_rows),source_groups=sorted({r['source_group'] for r in gt}),
        per_course=dict(course_rows),frames=source_frames,derived_artifacts=derived,
        gt_policy=policy_entry,eda_execution=descriptor(EDA_RECEIPT),
        claim='descriptive EDA-exposed native-course-held-out released-label agreement; semantic GT and exhaustive coverage uncertified')
    cohort_path, protocol_path = (REGISTRY/(NAME+suffix+'.json') for suffix in ('-cohort','-protocol'))
    bundle[cohort_path], bundle[protocol_path] = json_bytes(manifest), json_bytes(test_protocol(policy,policy_entry))
    binding = dict(schema='iiit_cvid_spotting_test_candidate_binding_v1',
        candidate_registry=candidate_entry,validation_cohort_binding_preserved=candidates['cohort_binding'],
        test_inputs=[bundle_descriptor(p,b) for p,b in bundle.items()]+[policy_entry],
        candidates=[dict(candidate_id=c['candidate_id'],configuration_sha256=c['configuration_sha256'],model_sha256=c['model_sha256']) for c in candidates['candidates']],
        status='test_use_binding_frozen; runtime_loading_verification_pending; inference_not_executed',
        rule='exact pinned candidate configuration/weights, no test tuning; new runtime run identity required, never resume validation records as test')
    bundle[REGISTRY/(NAME+'-candidate-binding.json')] = json_bytes(binding)
    receipt = dict(schema='iiit_cvid_spotting_test_freeze_v1',date='2026-10-14',cohort_frozen=True,
        gt_policy_frozen=True,spotting_inference_executed=False,semantic_gt_certified=False,blind_test=False,
        source_zip_sha256=EXPECTED,selected_frames=1754,selected_objects=40063,
        influence_frames=1751,influence_objects=40023,source_test_png_xml_redecoded_and_compared_with_eda=True,
        artifacts=[bundle_descriptor(p,b) for p,b in bundle.items()]+[policy_entry],
        prerequisites=[descriptor(EDA_RECEIPT),descriptor(ROOT/'experiments/outputs/cvid-all-split-eda-261014/eda-summary.json')],
        implementation_sha256=implementation,
        preserved_sha256=snapshot,python=platform.python_version(),unicode_version=unicodedata.unidata_version,
        runtime_packages={p:metadata.version(p) for p in ('Pillow','pandas','numpy','matplotlib','shapely','IPython')},
        no_source_gt_edits=True,no_model_loading=True,inference_gate='pending pinned candidate runtime-loading verification',
        limits=policy['claim_limits'])
    require(unicodedata.unidata_version == '14.0.0', 'normalizer Unicode runtime changed')
    # Recheck review-source images too: these are transitively bound by review receipts.
    prerequisites()
    verify_snapshot(snapshot)
    # No selected source pixels or EDA artifacts are rewritten by this command.
    require(sha(archive) == EXPECTED, 'source archive changed during freeze')
    bundle[REGISTRY/(NAME+'-freeze.json')] = json_bytes(receipt)
    return bundle, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=SOURCE)
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args()
    bundle, receipt = build_bundle(args.archive)
    verify_snapshot(receipt['preserved_sha256'])
    write_bundle(bundle,args.dry_run)
    print(json.dumps(dict(dry_run=args.dry_run,selected_frames=receipt['selected_frames'],
        selected_objects=receipt['selected_objects'],influence_frames=receipt['influence_frames'],
        influence_objects=receipt['influence_objects'],artifact_count=len(bundle),cohort_frozen=not args.dry_run),indent=2))


if __name__ == '__main__':
    main()
