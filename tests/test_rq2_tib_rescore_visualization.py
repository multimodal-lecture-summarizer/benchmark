"""Rendering failure states with explicitly synthetic unit fixtures, not research results."""

import matplotlib
matplotlib.use('Agg')
import pandas as pd
import pytest

from experiments.scripts import rq2_tib_rescore_visualization as visuals


@pytest.mark.parametrize('semantic_count', [0, 1])
def test_partial_or_empty_semantics_still_exports_coverage_and_missingness(tmp_path, monkeypatch, semantic_count):
    monkeypatch.setattr(visuals, 'display', lambda value: None)
    monkeypatch.setattr(visuals.plt, 'show', lambda: None)
    values = dict(S1=.1, S3=.2, S3_minus_S1=.1)
    origin = {'rows': []}
    receipt = {'rows': []}
    items = []
    for i in range(120):
        key = f'valid/{i}'
        origin['rows'].append(dict(id=key, length_stratum=('short', 'medium', 'long')[i // 40],
            arms={arm: {'summary': 'unit fixture only'} for arm in ('S1', 'S3')}, scores=values))
        receipt['rows'].append(dict(id=key, status='completed' if i < semantic_count else 'evaluation_failed',
            error=None if i < semantic_count else 'unit fixture error',
            semantic_scores={name: values for name in ('bertscore', 'sbertscore')} if i < semantic_count else {}))
        items.append(dict(split='valid', source_index=i, title='unit fixture', reference_text='unit fixture'))
    metrics = {}
    for name in ('rouge_l', 'bertscore', 'sbertscore'):
        count = 120 if name == 'rouge_l' else semantic_count
        means = values if count else dict.fromkeys(values)
        strata = {}
        for i, stratum in enumerate(('short', 'medium', 'long')):
            n = 40 if name == 'rouge_l' else (semantic_count if i == 0 else 0)
            strata[stratum] = dict(selected=40, paired_scored=n, unscored=40-n,
                                  **(values if n else dict.fromkeys(values)))
        metrics[name] = dict(overall=dict(selected=120, paired_scored=count, unscored=120-count, **means),
            strata=strata, exploratory_group_sensitivity={'dependence_group': dict(ci95=None, group_count=count)})
    costs = {arm: dict(prompt_tokens=0, output_tokens=0, generation_seconds=0, segmentation_seconds=0)
             for arm in ('S1', 'S3')}
    summary = dict(metrics=metrics, resources_by_arm=costs, rescore_sessions=[])
    visuals.render_rescore(receipt, summary, origin, {'items': items}, tmp_path)
    missing = pd.read_csv(tmp_path / 'failure-and-pending-ledger.csv')
    results = pd.read_csv(tmp_path / 'per-item-results.csv')
    assert len(missing) == 120 - semantic_count
    assert results.bertscore_S1.notna().sum() == semantic_count
    assert len(list(tmp_path.glob('*.png'))) == 6
