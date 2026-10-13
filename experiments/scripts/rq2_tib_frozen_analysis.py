"""Finite-cohort paired summaries and exploratory component sensitivity."""
import random
from collections import Counter, defaultdict
from experiments.scripts.rq2_tib_pilot_runtime import digest


def seal(value):
    value = {k:v for k,v in value.items() if k!='receipt_sha256'}
    return {**value, 'receipt_sha256':digest(value)}


def verify(value):
    if value.get('receipt_sha256')!=seal(value)['receipt_sha256']:
        raise ValueError('Receipt checksum mismatch')


def grouped_interval(rows, field, samples, seed):
    groups = defaultdict(list)
    for row, delta in rows:
        groups[row[field]].append(delta)
    if len(groups)<2:
        return {'ci95':None,'group_count':len(groups)}
    rng, units, means = random.Random(seed), list(groups.values()), []
    for _ in range(samples):
        draw=rng.choices(units,k=len(units))
        means.append(sum(map(sum,draw))/sum(map(len,draw)))
    means.sort()
    return {'ci95':[means[int(.025*(samples-1))],means[int(.975*(samples-1))]],
            'group_count':len(groups),'samples':samples,'seed':seed,
            'implementation':'whole_component_record_weighted_percentile_v1'}


def summarize_frozen(receipt,manifest,protocol):
    verify(receipt)
    if (receipt['identity']['protocol_sha256']!=protocol['protocol_sha256']
            or receipt['protocol']!=protocol or receipt['manifest']!=manifest):
        raise ValueError('Analysis identity mismatch')
    rows=receipt['rows']
    if [r['id'] for r in rows]!=[r['id'] for r in manifest['selected']]:
        raise ValueError('Analysis denominator mismatch')
    result={'selected':len(rows),'claim':'finite_cohort_descriptive',
            'estimand':'paired_successful_intersection_creator_abstract_agreement',
            'population_superiority_claim':False,'missingness':dict(Counter(r['status'] for r in rows)),
            'arms':{},'metrics':{},'counts':receipt.get('counts',{}),
            'rows':[{k:r.get(k) for k in ('id','length_stratum','status','scores','semantic_scores')}
                    for r in rows], 'resources_by_arm':{}}
    for arm in ('S1','S3'):
        result['arms'][arm]={'selected':len(rows),**dict(Counter(
            r.get('arms',{}).get(arm,{}).get('status','not_attempted') for r in rows))}
        attempts=[r['arms'][arm] for r in rows if arm in r.get('arms',{})]
        result['resources_by_arm'][arm]={'attempts':len(attempts),
            **{k:sum(a[k] for a in attempts if a.get(k) is not None)
               if any(a.get(k) is not None for a in attempts) else None
               for k in ('prompt_tokens','output_tokens','generation_seconds','segmentation_seconds')},
            'usage_incomplete_attempts':sum(not a.get('usage_complete',True) for a in attempts)}
    for metric in ('rouge_l','bertscore','sbertscore'):
        scored=[]
        for row in rows:
            scores=row.get('scores') if metric=='rouge_l' else row.get('semantic_scores',{}).get(metric)
            if scores: scored.append((row,scores))
        def means(pairs,n):
            return {'selected':n,'paired_scored':len(pairs),'unscored':n-len(pairs),
                    **{k:sum(s[k] for _,s in pairs)/len(pairs) if pairs else None
                       for k in ('S1','S3','S3_minus_S1')}}
        strata={name:means([(r,s) for r,s in scored if r['length_stratum']==name],n)
                for name,n in protocol['strata_counts'].items()}
        result['metrics'][metric]={'overall':means(scored,len(rows)),'strata':strata,
            'balanced_strata_mean_delta':sum(v['S3_minus_S1'] for v in strata.values())/len(strata)
                if all(v['paired_scored'] for v in strata.values()) else None,
            'exploratory_group_sensitivity':{field:grouped_interval(
                [(r,s['S3_minus_S1']) for r,s in scored],field,
                protocol['analysis']['bootstrap_samples'],protocol['analysis']['seed'])
                for field in protocol['analysis']['group_fields']}}
    dispatches=receipt.get('dispatches',[])
    known=sum(sum(d['output_tokens']) for d in dispatches if d['output_tokens'] is not None)
    unknown=sum(d['output_tokens'] is None for d in dispatches)
    possible=sum(r.get('possibly_attempted_unknown_usage',False) for r in rows)
    result['dispatch_usage']={'dispatches':len(dispatches),
        'known_input_tokens':sum(sum(d['prompt_tokens']) for d in dispatches),
        'known_output_tokens':known,'unknown_output_dispatches':unknown,
        'possibly_attempted_records_with_unknown_input_and_output_usage':possible,
        'total_output_tokens':None if unknown or possible else known}
    return result
