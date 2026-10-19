"""Score complete frozen-test predictions in the locked runtime; immutable exports."""
from collections import defaultdict
import csv
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata

from experiments.scripts.spotting_candidate_contract import ROOT, canonical_sha, sha, verify_files
from experiments.scripts.spotting_comparison_io_v2 import OUT, CONTRACT, encode, load_checkpoints, write_bytes_once, write_once
from experiments.scripts.spotting_runtime_binding import NAME, TEST, VENV, isolated_runtime, read_json, require

GT = ROOT/'experiments/outputs/iiit-cvid-spotting-test-261014/ground-truth.jsonl'
CODE = ('spotting_comparison_analysis.py', 'spotting_metrics.py', 'cvid_test_scoring.py')
METRICS = ('spotting', 'detection')
COUNTS = ('tp', 'fp', 'fn', 'precision', 'recall', 'hmean')
COVERAGE = ('selected_frames', 'successful_frames', 'failed_frames', 'gt_objects',
            'predicted_objects', 'empty_success_frames', 'invalid_predictions', 'empty_transcriptions')


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def csv_bytes(rows, fields, compressed=False):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='raise', lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    data = stream.getvalue().encode('utf-8')
    return gzip.compress(data, mtime=0) if compressed else data


def export(name, rows, fields, artifacts):
    path = OUT/name
    write_bytes_once(path, csv_bytes(rows, fields, name.endswith('.gz')))
    artifacts[name] = dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path),
                           bytes=path.stat().st_size, rows=len(rows), columns=list(fields))


def strict_records(candidate, identity, frames, complete):
    """No missing/extra records, and aggregate bytes must equal committed evidence."""
    path = OUT/candidate/'predictions.jsonl'
    records = read_lines(path)
    known = {f['frame_id'] for f in frames}
    require(len(records) == len(known) == len(frames) and
            {r['frame_id'] for r in records} == known, 'incomplete/duplicate/extra predictions')
    checkpoints = load_checkpoints(identity, frames, candidate)
    expected = b''.join(encode(checkpoints[f['frame_id']]) for f in frames)
    require(path.read_bytes() == expected, 'aggregate differs from immutable checkpoints')
    receipt = read_json(OUT/candidate/'candidate-complete.json')
    require(receipt == complete and receipt['run_id'] == identity['run_id'] and
            receipt['prediction_sha256'] == sha(path), 'candidate completion mismatch')
    require(receipt['committed_frames'] == len(records) and receipt['missing_records'] == 0 and
            receipt['successful_frames'] == sum(r['status'] == 'ok' for r in records) and
            receipt['failed_frames'] == sum(r['status'] == 'error' for r in records), 'coverage mismatch')
    return {r['frame_id']: r for r in records}


def summarize(rows, variant, candidate, group=None):
    from experiments.scripts.cvid_test_scoring import summarize_rows
    overall = summarize_rows(rows)
    shared = dict(variant=variant, candidate_id=candidate,
                  selected_frames=len(rows), successful_frames=overall['successful_frames'],
                  failed_frames=overall['failed_frames'],
                  gt_objects=sum(r['gt_objects'] for r in rows),
                  predicted_objects=sum(r['predictions_count'] for r in rows),
                  empty_success_frames=sum(r['status'] == 'ok' and r['predictions_count'] == 0 for r in rows),
                  invalid_predictions=sum(r['invalid_predictions'] for r in rows),
                  empty_transcriptions=sum(r['empty_transcriptions'] for r in rows))
    if group: shared.update(group)
    return [dict(shared, metric=metric, **overall['overall'][metric]) for metric in METRICS]


def enriched_rows(scored, raw, refs):
    return [dict(row, predictions_count=len(raw[row['frame_id']]['predictions']),
                 gt_objects=len(refs[row['frame_id']]['objects']),
                 wall_seconds=raw[row['frame_id']]['wall_seconds']) for row in scored['frames']]


def flatten(row, variant, candidate):
    result = {k: v for k, v in row.items() if k not in METRICS}
    result.update(variant=variant, candidate_id=candidate)
    for metric in METRICS:
        result.update({metric+'_'+k: row[metric][k] for k in COUNTS})
    return result


def score_variants(ground_truth, records, variants, excluded):
    from experiments.scripts.cvid_test_scoring import score_test_endpoints
    from experiments.scripts.spotting_metrics import score_cohort
    endpoints = score_test_endpoints(ground_truth, records, excluded,
                                     iou_threshold=.5, case_sensitive=False)
    for variant in variants:
        name = variant['id']
        scored = endpoints.get(name)
        if scored is None:
            scored = score_cohort(ground_truth, records, iou_threshold=variant['iou_threshold'],
                                  case_sensitive=variant['case_sensitive'])
        require(scored['selected_frames'] == variant['frames'] and
                sum(r['spotting']['tp']+r['spotting']['fn'] for r in scored['frames']) == variant['objects'],
                'variant denominator changed: '+name)
        yield name, scored


def source_identity(identity, complete, packages):
    implementation = {str(Path(__file__).with_name(n).relative_to(ROOT)).replace('\\', '/'): sha(Path(__file__).with_name(n)) for n in CODE}
    inputs = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
              (GT, CONTRACT, OUT/'run-identity.json', OUT/'inference-complete.json', OUT/'input-manifest.json')}
    for candidate in identity['candidate_order']:
        for name in ('predictions.jsonl', 'candidate-complete.json'):
            path = OUT/candidate/name
            inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    return dict(run_id=identity['run_id'], inputs=inputs, implementation=implementation,
                runtime=dict(python=sys.version, executable=str(Path(sys.executable).resolve()),
                             executable_sha256=sha(sys.executable), unicode_version=unicodedata.unidata_version,
                             packages=packages), inference_records=complete['committed_records'])


def full_text_rows(frames, refs, records, candidates):
    rows = []
    for frame in frames:
        ident = frame['frame_id']; gt = refs[ident]
        row = dict(frame_id=ident, course=gt['course'], source_group=gt['source_group'],
                   gt_objects=len(gt['objects']),
                   gt_object_ids=json.dumps([o['object_id'] for o in gt['objects']], ensure_ascii=False),
                   gt_texts=json.dumps([o['text'] for o in gt['objects']], ensure_ascii=False))
        for prefix, candidate in zip(('easyocr', 'paddleocr'), candidates):
            raw = records[candidate][ident]
            row.update({prefix+'_texts': json.dumps([p['text'] for p in raw['predictions']], ensure_ascii=False),
                        prefix+'_status': raw['status'], prefix+'_error': raw.get('error'),
                        prefix+'_wall_seconds': raw['wall_seconds'], prefix+'_origin': raw['origin']})
        rows.append(row)
    return rows


def score_and_export():
    from experiments.scripts.cvid_test_scoring import paired_cluster_bootstrap
    packages = isolated_runtime()
    require(unicodedata.unidata_version == '14.0.0', 'scoring Unicode runtime changed')
    identity = read_json(OUT/'run-identity.json'); complete = read_json(OUT/'inference-complete.json')
    require(complete['run_id'] == identity['run_id'] and complete['snapshot'] == identity['snapshot'] and
            complete['committed_records'] == 3508 and complete['frame_inference_executed'] is True,
            'inference not complete or wrong identity')
    verify_files(identity['snapshot'], ROOT)
    contract = read_json(CONTRACT); frames = read_json(OUT/'input-manifest.json')
    require(contract == read_json(OUT/'analysis-contract.json') and
            identity['candidate_order'] == contract['candidate_order'], 'analysis contract mismatch')
    candidates = contract['candidate_order']; gt = read_lines(GT); refs = {r['frame_id']: r for r in gt}
    require(len(refs) == len(gt) == len(frames) == 1754 and sum(len(r['objects']) for r in gt) == 40063 and
            set(refs) == {f['frame_id'] for f in frames}, 'GT/cohort denominator mismatch')
    require(len(complete['candidates']) == len(candidates) == 2 and
            [r['candidate_id'] for r in complete['candidates']] == candidates, 'completion candidate order changed')
    records = {cid: strict_records(cid, identity, frames, receipt) for cid, receipt in zip(candidates, complete['candidates'])}
    binding = source_identity(identity, complete, packages)
    cached = OUT/'analysis-summary.json'
    if cached.exists():
        summary = read_json(cached)
        require(summary['binding'] == binding, 'cached analysis source/runtime/implementation changed')
        for name, artifact in summary['artifacts'].items():
            require(sha(OUT/name) == artifact['sha256'], 'cached analysis export changed: '+name)
        return summary
    excluded = read_json(TEST/(NAME+'-influence.json'))['excluded_frame_ids']
    metrics, courses, groups, frame_scores, bootstrap, macro, failures = [], [], [], [], [], [], []
    scored_rows = {}
    for candidate in candidates:
        raw = records[candidate]
        for variant, scored in score_variants(gt, list(raw.values()), contract['variants'], excluded):
            rows = enriched_rows(scored, raw, refs); scored_rows[variant, candidate] = rows
            metrics.extend(summarize(rows, variant, candidate))
            frame_scores.extend(flatten(r, variant, candidate) for r in rows)
            for key, target in (('course', courses), ('source_group', groups)):
                grouped = defaultdict(list)
                for row in rows: grouped[row[key]].append(row)
                for group in sorted(grouped): target.extend(summarize(grouped[group], variant, candidate, {key: group}))
            for metric in METRICS:
                course_rows = [r for r in courses if r['variant'] == variant and r['candidate_id'] == candidate and r['metric'] == metric]
                macro.append(dict(variant=variant, candidate_id=candidate, metric=metric, courses=len(course_rows),
                                  **{'mean_course_'+k: sum(r[k] for r in course_rows)/len(course_rows) for k in ('precision','recall','hmean')}))
        for ident in sorted(raw):
            r = raw[ident]
            if r['status'] == 'error':
                failures.append(dict(candidate_id=candidate, frame_id=ident, course=refs[ident]['course'],
                    source_group=refs[ident]['source_group'], gt_objects=len(refs[ident]['objects']),
                    error=r['error'], origin=r['origin'], wall_seconds=r['wall_seconds'],
                    worker_pid=r.get('worker_pid'), completed_at_utc=r.get('completed_at_utc')))
    for variant in contract['variants']:
        for key in contract['uncertainty']['groups']:
            result = paired_cluster_bootstrap(*(scored_rows[variant['id'], cid] for cid in candidates),
                group_key=key, draws=contract['uncertainty']['draws'], seed=contract['uncertainty']['seed'])
            bootstrap.append(dict(variant=variant['id'], group_key=key, observed=result['observed'],
                lower=result['interval_95'][0], upper=result['interval_95'][1], draws=result['draws'],
                seed=result['seed'], cluster_count=len(result['groups'])))
    require(len(metrics) == 16 and len(frame_scores) == 14026 and len(bootstrap) == 8, 'export coverage mismatch')
    artifacts = {}; base = ('variant', 'candidate_id', 'metric')+COUNTS+COVERAGE
    export('metrics.csv', metrics, base, artifacts)
    export('course-metrics.csv', courses, base+('course',), artifacts)
    export('source-group-metrics.csv', groups, base+('source_group',), artifacts)
    fields = ('variant','candidate_id','frame_id','course','source_group','status','error','predictions_count',
              'gt_objects','invalid_predictions','empty_transcriptions','wall_seconds')+tuple(m+'_'+k for m in METRICS for k in COUNTS)
    export('frame-scores.csv.gz', frame_scores, fields, artifacts)
    export('bootstrap.csv', bootstrap, ('variant','group_key','observed','lower','upper','draws','seed','cluster_count'), artifacts)
    export('failure-ledger.csv', failures, ('candidate_id','frame_id','course','source_group','gt_objects','error','origin',
                                          'wall_seconds','worker_pid','completed_at_utc'), artifacts)
    texts = full_text_rows(frames, refs, records, candidates)
    export('all-frame-text.csv.gz', texts, tuple(texts[0]), artifacts)
    export('macro-course-means.csv', macro, ('variant','candidate_id','metric','courses','mean_course_precision',
                                           'mean_course_recall','mean_course_hmean'), artifacts)
    require(source_identity(identity, complete, packages) == binding, 'analysis inputs/code changed during scoring')
    verify_files(identity['snapshot'], ROOT)
    summary = dict(schema='cvid_full_test_spotting_analysis_v1', binding=binding, artifacts=artifacts,
        selected_frames=1754, selected_objects=40063, variants=contract['variants'], candidate_order=candidates,
        primary=[r for r in metrics if r['variant'] == 'primary'], bootstrap=bootstrap,
        failure_records=len(failures), source_group_counts={v['id']: len({r['source_group'] for r in scored_rows[v['id'], candidates[0]]}) for v in contract['variants']},
        selection='no_selection', limits=contract['selection'], uncertainty_limit='Exploratory conditional course/folder bootstrap; seven course proxies; no detection CI.',
        full_text_rows=len(texts), implementation=binding['implementation'])
    write_once(cached, summary)
    return summary


def run_analysis():
    """The display kernel never substitutes its dependencies for frozen scoring."""
    require((OUT/'inference-complete.json').exists(), 'full inference must finish before scoring')
    env = dict(os.environ); env.pop('PYTHONPATH', None); env['PYTHONNOUSERSITE'] = '1'
    result = subprocess.run([str(VENV/'Scripts/python.exe'), '-s', '-m',
                             'experiments.scripts.spotting_comparison_analysis', '--score'],
                            cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True)
    if result.returncode:
        raise RuntimeError('Locked-runtime scoring failed:\n'+result.stdout+'\n'+result.stderr)
    return read_json(OUT/'analysis-summary.json')


if __name__ == '__main__':
    require(sys.argv[1:] == ['--score'], 'use --score in the locked venv or run_analysis() from notebook')
    result = score_and_export()
    print(json.dumps(dict(selected_frames=result['selected_frames'], artifacts=result['artifacts']), ensure_ascii=False))
