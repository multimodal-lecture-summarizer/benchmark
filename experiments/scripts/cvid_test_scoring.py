"""Frozen whole-frame influence endpoint and paired cluster uncertainty helpers."""
from collections import defaultdict
import math
import random

from experiments.scripts.spotting_metrics import count_metrics, score_cohort


def summarize_rows(rows):
    metrics = {}
    for endpoint in ('detection', 'spotting'):
        tp, fp, fn = (sum(row[endpoint][k] for row in rows) for k in ('tp','fp','fn'))
        metrics[endpoint] = count_metrics(tp, tp+fp, tp+fn)
    return dict(selected_frames=len(rows), successful_frames=sum(r['status']=='ok' for r in rows),
                failed_frames=sum(r['status']=='error' for r in rows),
                failure_ledger=[dict(frame_id=r['frame_id'],error=r['error']) for r in rows if r['status']=='error'],
                overall=metrics, frames=rows)


def score_test_endpoints(ground_truth, records, excluded_frame_ids, **kwargs):
    """Validate full primary first; reuse unchanged scored rows on retained frames."""
    primary = score_cohort(ground_truth, records, **kwargs)
    excluded = set(excluded_frame_ids)
    if len(excluded) != len(excluded_frame_ids) or not excluded <= {r['frame_id'] for r in ground_truth}:
        raise ValueError('invalid influence exclusion IDs')
    retained = [r for r in primary['frames'] if r['frame_id'] not in excluded]
    return dict(primary=primary, observed_flag_frame_influence=summarize_rows(retained))


def paired_cluster_bootstrap(rows_a, rows_b, group_key='course', draws=2000, seed=20261014):
    """Pair by exact IDs/groups, draw clusters with replacement and pool counts."""
    if group_key not in ('course','source_group') or draws < 100:
        raise ValueError('invalid bootstrap specification')
    a, b = ({r['frame_id']:r for r in rows} for rows in (rows_a,rows_b))
    if len(a)!=len(rows_a) or len(b)!=len(rows_b) or not a or a.keys()!=b.keys():
        raise ValueError('bootstrap requires identical unique frame IDs')
    counts = defaultdict(lambda: [[0,0,0],[0,0,0]])
    for ident in sorted(a):
        if a[ident][group_key] != b[ident][group_key]:
            raise ValueError('bootstrap cluster mismatch')
        for arm, row in enumerate((a[ident], b[ident])):
            for k, field in enumerate(('tp','fp','fn')):
                value = row['spotting'][field]
                if isinstance(value,bool) or not isinstance(value,int) or value < 0:
                    raise ValueError('bootstrap requires nonnegative integer counts')
                counts[row[group_key]][arm][k] += value
    groups = sorted(counts)
    rng, differences = random.Random(seed), []
    for _ in range(draws):
        totals = [[0,0,0],[0,0,0]]
        for _ in groups:
            sample = counts[rng.choice(groups)]
            for arm in (0,1):
                for k in range(3):
                    totals[arm][k] += sample[arm][k]
        scores = [2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0. for tp,fp,fn in totals]
        differences.append(scores[1]-scores[0])
    differences.sort()
    observed = [summarize_rows(rows)['overall']['spotting']['hmean'] for rows in (rows_a,rows_b)]
    return dict(statistic='B_minus_A_pooled_micro_spotting_hmean', observed=observed[1]-observed[0],
                interval_95=[differences[math.floor(.025*draws)],differences[math.floor(.975*draws)-1]],
                draws=draws, seed=seed, group_key=group_key, groups=groups, rng='Python random.Random.choice',
                limit='exploratory conditional uncertainty; cluster independence and population generalization unverified')
