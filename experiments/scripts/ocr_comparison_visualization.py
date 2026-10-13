"""Display and export paired validation OCR diagnostics without model inference."""

import json
import random

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display

from experiments.scripts.summarize_ocr_validation import score


def render_comparison(paired, easy, paddle, summary, output):
    """Keep full-cohort scores primary; feature strata are descriptive only."""
    frame = paired.copy()
    assert set(frame.index) == set(easy) == set(paddle)
    output.mkdir(parents=True, exist_ok=True)
    names = ['EasyOCR', 'PaddleOCR']

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(output / name, dpi=130, bbox_inches='tight')
        plt.show()
        plt.close(fig)

    overall = pd.DataFrame([score(list(easy.values())), score(list(paddle.values()))], index=names)
    display(Markdown('### Overall scores and coverage — lower CER is better'))
    display(overall)
    overall.to_csv(output / 'overall-scores.csv')
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, metric in zip(axes[:2], ['micro_cer', 'exact_word_rate']):
        overall[metric].plot.bar(ax=ax, rot=0, title=metric)
        ax.set_ylabel('Rate')
    overall[['failures', 'empty_predictions']].plot.bar(ax=axes[2], rot=0, title='Failure / empty counts')
    axes[2].set_ylabel('Crops')
    save(fig, 'overall-scores.png')

    def grouped_scores(feature):
        result = frame.groupby(feature, observed=True).agg(
            crops=('refchars', 'size'), reference_chars=('refchars', 'sum'),
            easy_edits=('easy_edits', 'sum'), paddle_edits=('paddle_edits', 'sum'))
        for name in ('easy', 'paddle'):
            result[name + '_cer'] = result[name + '_edits'] / result.reference_chars
            result[name + '_exact'] = frame[name + '_edits'].eq(0).groupby(frame[feature], observed=True).mean()
        result['delta_cer'] = result.paddle_cer - result.easy_cer
        return result

    display(Markdown('### Per-course and per-video results'))
    course = grouped_scores('course')
    video = grouped_scores('video')
    course.to_csv(output / 'course-scores.csv')
    video.to_csv(output / 'video-scores.csv')
    display(course)
    display(video.describe())
    with pd.option_context('display.max_rows', None):
        display(video)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    axes[0].hist([video.easy_cer, video.paddle_cer], bins=20, label=names)
    axes[0].set(xlabel='Video micro CER', ylabel='Videos', title='Each video counted once')
    axes[0].legend()
    axes[1].scatter(video.easy_cer, video.paddle_cer, alpha=.65)
    bound = max(video.easy_cer.max(), video.paddle_cer.max(), .01)
    axes[1].plot([0, bound], [0, bound], '--', color='gray')
    axes[1].set(xlabel='EasyOCR video CER', ylabel='PaddleOCR video CER', title='Below diagonal: Paddle lower')
    axes[2].hist(video.delta_cer, bins=25)
    axes[2].axvline(0, color='gray', linestyle='--')
    axes[2].set(xlabel='Paddle − Easy video CER', ylabel='Videos', title='Paired video differences')
    save(fig, 'video-comparison.png')

    # Reconstruct ordered bins even when features were reloaded from a CSV.
    for column, source, edges in [
        ('length_bin', 'chars', [0, 2, 5, 10, float('inf')]),
        ('width_bin', 'width', [0, 32, 64, 128, float('inf')]),
        ('height_bin', 'height', [0, 16, 32, 64, float('inf')]),
        ('contrast_bin', 'contrast', [0, 20, 40, 60, 128]),
    ]:
        frame[column] = pd.cut(frame[source], edges, include_lowest=True)
    features = ['length_bin', 'width_bin', 'height_bin', 'contrast_bin',
                'has_digit', 'punctuation', 'review_flag']
    display(Markdown('### Feature strata — correlated descriptive groups, not causal effects'))
    fig, axes = plt.subplots(3, 3, figsize=(16, 14))
    for ax, feature in zip(axes.flat, features):
        table = grouped_scores(feature)
        assert table.crops.sum() == len(frame), f'Unbinned crops: {feature}'
        display(Markdown('**' + feature + '**'))
        display(table)
        table.to_csv(output / f'stratum-{feature}.csv')
        table[['easy_cer', 'paddle_cer']].plot.bar(ax=ax, title=feature)
        ax.set_ylabel('Micro CER')
        ax.set_xticklabels([f'{group}\nn={n}' for group, n in zip(table.index, table.crops)], rotation=30)
    for ax in list(axes.flat)[len(features):]:
        ax.axis('off')
    save(fig, 'feature-strata.png')

    display(Markdown('### Paired outcomes: edit distance and exact-word agreement'))
    gap = frame.paddle_edits - frame.easy_edits
    outcomes = pd.Series({'Paddle fewer edits': int((gap < 0).sum()),
                          'Equal edits': int((gap == 0).sum()),
                          'Easy fewer edits': int((gap > 0).sum())}, name='crops')
    e, p = frame.easy_edits.eq(0), frame.paddle_edits.eq(0)
    agreement = pd.Series({'Both exact': int((e & p).sum()), 'Easy only exact': int((e & ~p).sum()),
                           'Paddle only exact': int((~e & p).sum()), 'Neither exact': int((~e & ~p).sum())}, name='crops')
    display(outcomes.to_frame()); display(agreement.to_frame())
    outcomes.to_csv(output / 'paired-outcomes.csv')
    agreement.to_csv(output / 'exact-word-agreement.csv')
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    outcomes.plot.bar(ax=axes[0], title='Paired edit-distance outcomes', rot=20)
    agreement.plot.bar(ax=axes[1], title='Normalized exact-word agreement', rot=20)
    for ax in axes:
        ax.set_ylabel('Crops')
    save(fig, 'paired-outcomes.png')

    display(Markdown('### Review-flag sensitivity — primary includes every crop'))
    sensitivity = []
    for group, mask in [('All crops (primary)', pd.Series(True, index=frame.index)),
                        ('Flagged only', frame.review_flag), ('Unflagged only', ~frame.review_flag)]:
        keys = list(frame.index[mask])
        for name, records in zip(names, [easy, paddle]):
            sensitivity.append(dict(group=group, engine=name, **score([records[k] for k in keys])))
    sensitivity = pd.DataFrame(sensitivity)
    display(sensitivity)
    sensitivity.to_csv(output / 'review-flag-sensitivity.csv', index=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    sensitivity.pivot(index='group', columns='engine', values='micro_cer').plot.bar(ax=ax, rot=15)
    ax.set(ylabel='Micro CER', title='Flags are review signals, not proven label errors')
    save(fig, 'review-flag-sensitivity.png')

    display(Markdown('### Paired source-video bootstrap: Paddle − Easy micro CER'))
    # Same cluster resampling, seed and percentile indices as the owning summary script.
    totals = video[['easy_edits', 'paddle_edits', 'reference_chars']].to_numpy()
    rng = random.Random(summary['bootstrap_seed'])
    differences = []
    for _ in range(summary['bootstrap_draws']):
        sampled = totals[[rng.randrange(len(totals)) for _ in totals]].sum(axis=0)
        differences.append((sampled[1] - sampled[0]) / sampled[2])
    differences.sort()
    draws = summary['bootstrap_draws']
    interval = [differences[int(.025 * draws)], differences[int(.975 * draws) - 1]]
    assert np.allclose(interval, summary['paired_video_bootstrap_95_interval'])
    delta = overall.loc['PaddleOCR', 'micro_cer'] - overall.loc['EasyOCR', 'micro_cer']
    assert np.isclose(delta, summary['paddle_minus_easy_micro_cer'])
    ci = pd.DataFrame([dict(delta_cer=delta, lower_95=interval[0], upper_95=interval[1],
                            videos=len(video), draws=draws, seed=summary['bootstrap_seed'])])
    display(ci)
    ci.to_csv(output / 'paired-bootstrap-interval.csv', index=False)
    pd.Series(differences, name='delta_cer').to_csv(output / 'paired-bootstrap-draws.csv', index=False)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    axes[0].hist(differences, bins=45)
    for value, label, color in [(delta, 'Observed delta', 'tab:orange'),
                                (interval[0], '95% endpoints', 'tab:blue'),
                                (interval[1], None, 'tab:blue')]:
        axes[0].axvline(value, linestyle='--', label=label, color=color)
    axes[0].axvline(0, color='gray'); axes[0].legend()
    axes[0].set(xlabel='Paddle − Easy micro CER', ylabel='Bootstrap draws')
    axes[1].plot(interval, [0, 0], linewidth=3)
    axes[1].scatter([delta], [0], zorder=3)
    axes[1].axvline(0, color='gray', linestyle='--')
    axes[1].set(yticks=[], xlabel='CER difference', title=f'{delta:.4f} [{interval[0]:.4f}, {interval[1]:.4f}]')
    save(fig, 'paired-bootstrap.png')
    (output / 'visualization-receipt.json').write_text(json.dumps(dict(
        crops=len(frame), videos=len(video), courses=len(course),
        bootstrap_interval=interval, labels_modified=False, inference_performed=False), indent=2))
