"""Complete-cohort multi-candidate scoring using the unchanged frozen scorer."""
from collections import defaultdict
import csv
import gzip
import io
import json
from pathlib import Path
import unicodedata
import subprocess
import sys

from experiments.scripts.cvid_test_scoring import paired_cluster_bootstrap, summarize_rows
from experiments.scripts.spotting_metrics import score_cohort
from experiments.scripts.spotting_colab_data import GT, NAME, REGISTRY, verify_bundle
from experiments.scripts.spotting_colab_state import (
    digest, encode, load_records, read, require, sha, write_bytes_once, write_once,
)


def export(output, name, rows, columns=None):
    fields = columns or list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode('utf-8')
    if name.endswith('.gz'):
        data = gzip.compress(data, mtime=0)
    path = Path(output) / name
    write_bytes_once(path, data)
    return dict(path=name, sha256=sha(path), rows=len(rows))


def score_completed(root, output, registry):
    require(unicodedata.unidata_version == '14.0.0', 'frozen normalization requires Unicode 14 / Python 3.11')
    root, output = Path(root), Path(output)
    data = read(output / 'prepared-data.json')
    require(verify_bundle(root) == data['bundle_sha256'], 'analysis bundle identity changed')
    gt = [json.loads(line) for line in (root / GT).read_text(encoding='utf-8').splitlines()]
    require(len(gt) == 1754 and sum(len(row['objects']) for row in gt) == 40063, 'GT denominator mismatch')
    require({r['frame_id'] for r in gt} == {r['frame_id'] for r in data['frames']}, 'GT/input IDs differ')
    excluded = set(read(root / REGISTRY / (NAME + '-influence.json'))['excluded_frame_ids'])
    candidates, eligibility, inputs, raw = [], [], {}, {}
    for candidate in registry['candidates']:
        cid = candidate['candidate_id']
        gate_path = output / cid / 'preflight.json'
        passed = gate_path.exists() and read(gate_path).get('status') == 'passed'
        eligibility.append(dict(candidate_id=cid, preflight_passed=passed,
                                conditional=candidate.get('conditional', False)))
        if not passed:
            require(candidate.get('conditional', False), 'required candidate has no passed preflight: ' + cid)
            continue
        complete = read(output / cid / 'candidate-complete.json')
        gate = read(gate_path)
        require(complete['binding'] == gate['binding'] and complete['frames'] == len(gt), 'completion/gate mismatch')
        require(complete['binding']['run_binding']['data_sha256'] == digest(data), 'completion uses different cohort')
        require(complete['binding']['run_binding']['registry_sha256'] == digest(registry), 'completion uses different registry')
        require(complete['binding']['run_binding']['bundle_sha256'] == data['bundle_sha256'], 'completion uses different bundle')
        require(complete['binding']['configuration_sha256'] == digest(candidate), 'candidate configuration changed')
        require(gate['binding']['runtime_sha256'] == digest(gate['runtime']), 'preflight runtime seal changed')
        require(gate['binding']['prepared_sha256'] == digest(read(output / cid / 'prepared.json')), 'prepared artifact seal changed')
        records = load_records(output, cid, complete['binding'], data['frames'])
        require(len(records) == len(gt), 'incomplete checkpoint coverage')
        predictions = output / cid / 'predictions.jsonl'
        expected = b''.join(encode(records[row['frame_id']]) for row in data['frames'])
        require(predictions.read_bytes() == expected and sha(predictions) == complete['prediction_sha256'],
                'aggregate predictions differ from immutable checkpoints')
        require(complete['failed_frames'] == sum(r['status'] == 'error' for r in records.values()), 'failure count mismatch')
        candidates.append(cid)
        raw[cid] = list(records.values())
        inputs[cid] = dict(completion_sha256=sha(output / cid / 'candidate-complete.json'),
                           predictions_sha256=sha(predictions), gate_sha256=sha(gate_path))
    required = {c['candidate_id'] for c in registry['candidates'] if not c.get('conditional', False)}
    require(required <= set(candidates) and len(required) >= 5, 'all declared primary candidates must finish before comparison')
    import shapely
    scoring_runtime = dict(python=sys.version, python_sha256=sha(sys.executable),
                           unicode=unicodedata.unidata_version, shapely=shapely.__version__,
                           geos=shapely.geos_version_string,
                           packages=subprocess.check_output([sys.executable, '-m', 'pip', 'freeze', '--all'], text=True))
    binding = dict(data_sha256=digest(data), registry_sha256=digest(registry), candidates=inputs,
                   scoring_runtime=scoring_runtime, bundle_sha256=data['bundle_sha256'])
    cached = output / 'analysis-summary.json'
    if cached.exists():
        summary = read(cached)
        require(summary['binding'] == binding, 'cached analysis identity changed')
        for artifact in summary['artifacts'].values():
            require(sha(output / artifact['path']) == artifact['sha256'], 'analysis artifact changed')
        return summary
    metrics, groups, frame_rows, failures, texts, bootstrap, macro = [], [], [], [], [], [], []
    scored = {}
    variants = [('primary', .5, False, False), ('strict_iou', .75, False, False),
                ('case_sensitive', .5, True, False), ('observed_flag_frame_influence', .5, False, True)]
    for cid in candidates:
        for variant, iou, case, influence in variants:
            result = score_cohort(gt, raw[cid], iou_threshold=iou, case_sensitive=case)
            rows = [r for r in result['frames'] if not influence or r['frame_id'] not in excluded]
            scored[variant, cid] = rows
            summary = summarize_rows(rows)
            for endpoint in ('spotting', 'detection'):
                metrics.append(dict(candidate_id=cid, variant=variant, metric=endpoint,
                                    selected_frames=len(rows), failed_frames=summary['failed_frames'],
                                    **summary['overall'][endpoint]))
            for key in ('course', 'source_group'):
                clustered = defaultdict(list)
                for row in rows:
                    clustered[row[key]].append(row)
                for group, subrows in sorted(clustered.items()):
                    sub = summarize_rows(subrows)
                    for endpoint in ('spotting', 'detection'):
                        groups.append(dict(candidate_id=cid, variant=variant, metric=endpoint,
                                           group_type=key, group=group, frames=len(subrows), **sub['overall'][endpoint]))
            for row in rows:
                frame_rows.append(dict(candidate_id=cid, variant=variant,
                                       **{k: v for k, v in row.items() if k not in ('spotting', 'detection')},
                                       **{m + '_' + k: v for m in ('spotting', 'detection') for k, v in row[m].items()}))
        for record in raw[cid]:
            if record['status'] == 'error':
                failures.append(dict(candidate_id=cid, frame_id=record['frame_id'], error=record['error']))
            texts.append(dict(candidate_id=cid, frame_id=record['frame_id'], status=record['status'],
                              predictions_json=json.dumps(record['predictions'], ensure_ascii=False)))
    anchor = 'paddle_db_v3_rec_v4_t4'
    require(anchor in candidates, 'fixed Paddle anchor absent')
    for variant, *_ in variants:
        for cid in candidates:
            if cid == anchor:
                continue
            for group_key in ('course', 'source_group'):
                result = paired_cluster_bootstrap(scored[variant, anchor], scored[variant, cid], group_key=group_key)
                bootstrap.append(dict(candidate_id=cid, anchor=anchor, variant=variant, group_key=group_key,
                                      delta=result['observed'], low=result['interval_95'][0], high=result['interval_95'][1],
                                      draws=result['draws'], seed=result['seed']))
    artifacts = {}
    for cid in candidates:
        for variant, *_ in variants:
            for endpoint in ('spotting', 'detection'):
                selected = [r for r in groups if r['candidate_id'] == cid and r['variant'] == variant
                            and r['metric'] == endpoint and r['group_type'] == 'course']
                macro.append(dict(candidate_id=cid, variant=variant, metric=endpoint, courses=len(selected),
                                  mean_course_hmean=sum(r['hmean'] for r in selected) / len(selected)))
    for name, rows, columns in [('metrics.csv', metrics, None), ('group-metrics.csv', groups, None),
                                ('macro-course-means.csv', macro, None),
                                ('frame-scores.csv.gz', frame_rows, None), ('bootstrap.csv', bootstrap, None),
                                ('failure-ledger.csv', failures, ['candidate_id', 'frame_id', 'error']),
                                ('all-prediction-text.csv.gz', texts, None)]:
        artifacts[name] = export(output, name, rows, columns)
    summary = dict(schema='cvid_colab_analysis_v1', binding=binding, selected_frames=len(gt),
                   selected_objects=40063, candidate_order=candidates, eligibility=eligibility,
                   primary=[r for r in metrics if r['variant'] == 'primary'], bootstrap=bootstrap,
                   artifacts=artifacts, selection='no_selection',
                   limits='EDA-exposed selective released labels; seven course proxies; exploratory unadjusted CIs; no production winner or CPU/GPU speed equivalence')
    write_once(cached, summary)
    return summary
