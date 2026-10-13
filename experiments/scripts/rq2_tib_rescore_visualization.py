"""Tables, plots and item exports for amended semantic-only scoring."""

import json

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import HTML, Markdown, display


def render_rescore(receipt, summary, origin, bundle, output):
    output.mkdir(parents=True, exist_ok=True)
    rows = receipt['rows']
    keyed = {row['id']: row for row in rows}
    items = {f"{r['split']}/{r['source_index']}": r for r in bundle['items']}
    metrics = summary['metrics']
    overview = pd.DataFrame([dict(metric=name, **report['overall']) for name, report in metrics.items()])
    display(Markdown('### Coverage and paired means — amended semantic scorer v2'))
    display(overview)
    overview.to_csv(output / 'metric-overview.csv', index=False)
    intervals, strata = [], []
    for name, report in metrics.items():
        table = pd.DataFrame([dict(stratum=k, **v) for k, v in report['strata'].items()])
        display(Markdown('**' + name + '**')); display(table)
        strata.extend(dict(metric=name, **row) for row in table.to_dict('records'))
        for field, interval in report['exploratory_group_sensitivity'].items():
            intervals.append(dict(metric=name, group=field, **interval))
    strata = pd.DataFrame(strata)
    intervals = pd.DataFrame(intervals)
    display(intervals)
    strata.to_csv(output / 'metric-by-stratum.csv', index=False)
    intervals.to_csv(output / 'exploratory-intervals.csv', index=False)

    records = []
    for old in origin['rows']:
        current = keyed[old['id']]
        row = dict(id=old['id'], stratum=old['length_stratum'], status=current['status'],
                   error=current.get('error'), title=items[old['id']].get('title'),
                   reference=items[old['id']]['reference_text'])
        for arm in ('S1', 'S3'):
            row[arm + '_summary'] = old['arms'][arm]['summary']
        for name in metrics:
            values = old['scores'] if name == 'rouge_l' else current.get('semantic_scores', {}).get(name)
            for key in ('S1', 'S3', 'S3_minus_S1'):
                row[name + '_' + key] = values[key] if values else None
        records.append(row)
    results = pd.DataFrame(records)
    results.to_csv(output / 'per-item-results.csv', index=False)
    missing = results[results.status != 'completed']
    display(Markdown('### All selected IDs; unavailable scores remain missing'))
    columns = ['id', 'stratum', 'status', 'error'] + [m + '_S3_minus_S1' for m in metrics]
    display(HTML('<div style="max-height:550px;overflow:auto">' +
                 results[columns].to_html(index=False, escape=True, na_rep='—') + '</div>'))
    display(Markdown('**Failures / pending records**')); display(missing[columns])
    missing.to_csv(output / 'failure-and-pending-ledger.csv', index=False)
    from html import escape
    panels = []
    for row in records:
        body = ''.join('<h5>' + title + '</h5><pre style="white-space:pre-wrap">' +
                       escape(str(row[key])) + '</pre>' for title, key in
                       [('Creator abstract', 'reference'), ('S1', 'S1_summary'), ('S3', 'S3_summary')])
        panels.append('<details><summary>' + escape(row['id']) + ' · ' +
                      escape(str(row['title'])) + '</summary>' + body + '</details>')
    display(HTML(''.join(panels)))

    def save(fig, name):
        fig.tight_layout(); fig.savefig(output / name, dpi=130, bbox_inches='tight')
        plt.show(); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, (name, report) in zip(axes, metrics.items()):
        scored = report['overall']['paired_scored']
        ax.bar(['Paired scored', 'Unscored'], [scored, 120 - scored])
        ax.set(title=name, ylabel='Records', ylim=(0, 125))
        for i, value in enumerate([scored, 120 - scored]):
            ax.text(i, value + 1, str(value), ha='center')
    save(fig, 'paired-coverage.png')
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, name in zip(axes, metrics):
        data = results.dropna(subset=[name + '_S3_minus_S1'])
        ax.hist(data[name + '_S3_minus_S1'], bins=20)
        if data.empty:
            ax.text(.5, .5, 'No paired scores', ha='center', transform=ax.transAxes)
        ax.axvline(0, color='gray', linestyle='--')
        ax.set(title=f'{name}: n={len(data)}', xlabel='S3 − S1', ylabel='Records')
    save(fig, 'paired-delta-distributions.png')
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, name in zip(axes, metrics):
        data = results.dropna(subset=[name + '_S1', name + '_S3'])
        ax.scatter(data[name + '_S1'], data[name + '_S3'], alpha=.6)
        if len(data):
            low = min(data[name + '_S1'].min(), data[name + '_S3'].min())
            high = max(data[name + '_S1'].max(), data[name + '_S3'].max())
            ax.plot([low, high], [low, high], '--', color='gray')
        ax.set(title=name, xlabel='S1', ylabel='S3')
    save(fig, 'paired-score-scatter.png')
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, name in zip(axes, metrics):
        part = strata[strata.metric == name].set_index('stratum')
        values = pd.to_numeric(part['S3_minus_S1'], errors='coerce')
        if values.notna().any():
            values.plot.bar(ax=ax, title=name)
        else:
            ax.text(.5, .5, 'No paired scores', ha='center', transform=ax.transAxes)
            ax.set_title(name); ax.set_xticks([])
        ax.axhline(0, color='gray'); ax.set_ylabel('Mean S3 − S1')
    save(fig, 'paired-stratum-deltas.png')
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, name in zip(axes, metrics):
        part = intervals[intervals.metric == name]
        available = False
        for i, row in enumerate(part.to_dict('records')):
            if row['ci95'] is not None:
                available = True
                ax.plot(row['ci95'], [i, i], linewidth=3)
                delta = metrics[name]['overall']['S3_minus_S1']
                ax.scatter([delta], [i])
        ax.set_yticks(range(len(part)), part['group'])
        ax.axvline(0, color='gray', linestyle='--')
        if not available:
            ax.text(.5, .5, 'Interval unavailable', ha='center', transform=ax.transAxes)
        ax.set(title=name, xlabel='Exploratory 95% interval, S3 − S1')
    save(fig, 'exploratory-intervals.png')

    display(Markdown('### Original generation costs; rescore costs reported separately'))
    costs = pd.DataFrame(summary['resources_by_arm']).T
    display(costs); costs.to_csv(output / 'original-generation-costs.csv')
    rescore_cost = summary.get('rescore_cost', {})
    display(pd.DataFrame([rescore_cost]))
    sessions = pd.DataFrame(summary.get('rescore_sessions', []))
    display(sessions)
    sessions.to_csv(output / 'rescore-sessions.csv', index=False)
    (output / 'rescore-cost.json').write_text(json.dumps(rescore_cost, indent=2), encoding='utf-8')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    costs[['prompt_tokens', 'output_tokens']].plot.bar(ax=axes[0], title='Original tokens')
    costs[['generation_seconds', 'segmentation_seconds']].plot.bar(ax=axes[1], title='Original seconds')
    save(fig, 'original-generation-costs.png')
    print('Claim: finite-cohort descriptive; creator abstracts are not verified factual summaries.')
    print('BERTScore and source SBERTScore are not factuality percentages.')
    print('Complete semantic coverage:', all(metrics[m]['overall']['paired_scored'] == 120
          for m in ('bertscore', 'sbertscore')))
    print('Tables, original texts, plots and receipts:', output)
