"""Descriptive plots of frozen CVID spotting exports; no inference or rescoring."""
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CANDIDATES = ('easyocr_craft_english_g2', 'paddle_db_v3_rec_v4_keep_all')
LABELS = ('A: EasyOCR', 'B: PaddleOCR')
COLORS = ('#3573a6', '#c77c2b')
VARIANTS = ('primary', 'iou_075', 'case_sensitive', 'observed_flag_frame_influence')
VARIANT_LABELS = ('Primary', 'IoU > .75', 'Case sensitive', 'Fixed flag influence')


def load_tables(output: Path) -> dict:
    """Read complete exports, preserving identifiers and literal text strings."""
    files = {'metrics': 'metrics.csv', 'course_metrics': 'course-metrics.csv',
             'source_group_metrics': 'source-group-metrics.csv',
             'frame_scores': 'frame-scores.csv.gz', 'bootstrap': 'bootstrap.csv',
             'failure_ledger': 'failure-ledger.csv', 'all_frame_text': 'all-frame-text.csv.gz'}
    return {key: pd.read_csv(Path(output) / name, keep_default_na=False,
                            dtype={'course': str, 'frame_id': str, 'source_group': str})
            for key, name in files.items()}


def _figure(title, note='', count=2):
    fig, axes = plt.subplots(1, count, figsize=(13, 5.8), squeeze=False)
    fig.suptitle(title, fontsize=14)
    fig.text(.02, .02, note, fontsize=9, va='bottom')
    fig.subplots_adjust(top=.76, bottom=.24, left=.08, right=.98, wspace=.35)
    return fig, axes.ravel()


def _rows(data, table='metrics', metric='spotting', variant='primary'):
    frame = data[table]
    return frame[(frame.variant == variant) & (frame.metric == metric)]


def _bars(ax, values, labels, ylabel, percent=False):
    """Grouped bars with stable candidate order and directly labeled values."""
    x = np.arange(len(labels))
    for i, (name, color) in enumerate(zip(LABELS, COLORS)):
        bars = ax.bar(x + (i - .5) * .36, values[i], .36, label=name, color=color)
        ax.bar_label(bars, fmt='%.1f' if percent else '%.0f', fontsize=8, padding=3)
    ax.set(xticks=x, xticklabels=labels, ylabel=ylabel)
    ax.set_ylim(0, 106 if percent else max(1, np.nanmax(values)) * 1.22)
    ax.legend(fontsize=8, loc='upper center', bbox_to_anchor=(.5, 1.18), ncol=2)


def _denominators(data):
    rows = _rows(data).set_index('candidate_id')
    return '; '.join(f'{label}: {int(rows.loc[cid, "selected_frames"]):,} frames, '
                     f'{int(rows.loc[cid, "gt_objects"]):,} GT, '
                     f'{int(rows.loc[cid, "failed_frames"]):,} failures'
                     for cid, label in zip(CANDIDATES, LABELS))


def plot_primary(data):
    fig, axes = _figure('Primary pooled released-label agreement', _denominators(data))
    for ax, metric in zip(axes, ('spotting', 'detection')):
        rows = _rows(data, metric=metric).set_index('candidate_id').loc[list(CANDIDATES)]
        _bars(ax, rows[['precision', 'recall', 'hmean']].to_numpy() * 100,
              ('Precision', 'Recall', 'Hmean' if metric == 'spotting' else 'F1'), 'Pooled score (%)', True)
        ax.set_title(metric.capitalize(), pad=60)
    return fig


def plot_sensitivity(data):
    rows = data['metrics']
    rows = rows[(rows.metric == 'spotting') & (rows.candidate_id == CANDIDATES[0])]
    denominators = '; '.join(f'{VARIANT_LABELS[VARIANTS.index(row.variant)]}: '
                             f'{int(row.selected_frames):,}/{int(row.gt_objects):,}'
                             for row in rows.itertuples())
    note = 'Frames/GT: ' + denominators + '\nSame predictions; fixed flag influence is not corrected gold.'
    fig, axes = _figure('Declared sensitivities', note)
    for ax, metric in zip(axes, ('spotting', 'detection')):
        rows = data['metrics'].query('metric == @metric')
        values = rows.pivot(index='candidate_id', columns='variant', values='hmean')
        _bars(ax, values.reindex(index=CANDIDATES, columns=VARIANTS).to_numpy() * 100,
              VARIANT_LABELS, 'Pooled Hmean / F1 (%)', True)
        ax.tick_params(axis='x', rotation=18, labelsize=8)
        ax.set_title(metric.capitalize(), pad=60)
    return fig


def plot_counts(data):
    fig, axes = _figure('Primary pooled match counts', _denominators(data))
    for ax, metric in zip(axes, ('spotting', 'detection')):
        rows = _rows(data, metric=metric).set_index('candidate_id').loc[list(CANDIDATES)]
        _bars(ax, rows[['tp', 'fp', 'fn']].to_numpy(), ('TP', 'FP', 'FN'), 'Released-label objects')
        ax.set_title(metric.capitalize(), pad=60)
    return fig


def plot_course(data):
    fig, axes = _figure('Primary course agreement and annotation concentration',
                        'Course scores pool counts within course; overall primary scores pool all objects. Course means are not primary scores.')
    rows = _rows(data, table='course_metrics')
    courses = sorted(rows.course.unique(), key=lambda value: (len(str(value)), str(value)))
    scores = rows.pivot(index='candidate_id', columns='course', values='hmean')
    _bars(axes[0], scores.reindex(index=CANDIDATES, columns=courses).to_numpy() * 100,
          courses, 'Pooled spotting Hmean (%)', True)
    axes[0].set_xlabel('Released course ID')
    counts = rows[rows.candidate_id == CANDIDATES[0]].set_index('course').reindex(courses)
    bars = axes[1].bar(courses, counts.gt_objects, color='#638675')
    axes[1].bar_label(bars, fmt='%.0f', fontsize=8, padding=3)
    axes[1].set(xlabel='Released course ID', ylabel='GT objects')
    axes[1].set_ylim(0, max(1, counts.gt_objects.max()) * 1.18)
    return fig


def plot_coverage(data):
    fig, axes = _figure('Primary coverage and prediction diagnostics', _denominators(data))
    rows = _rows(data).set_index('candidate_id').loc[list(CANDIDATES)]
    _bars(axes[0], rows[['successful_frames', 'failed_frames', 'empty_success_frames']].to_numpy(),
          ('Successful', 'Failed', 'Empty success'), 'Frames (empty success overlaps successful)')
    _bars(axes[1], rows[['predicted_objects', 'invalid_predictions', 'empty_transcriptions']].to_numpy(),
          ('Predictions', 'Invalid', 'Empty text'), 'Prediction records (diagnostic categories can overlap)')
    return fig


def plot_frame_pairs(data):
    fig, axes = _figure('Paired frame diagnostics',
                        'All primary frames, including failures. Per-frame scores and differences are diagnostic; primary scores pool counts.')
    rows = data['frame_scores'].query('variant == "primary"')
    pairs = rows.pivot(index='frame_id', columns='candidate_id', values='spotting_hmean').reindex(columns=CANDIDATES)
    if pairs.isna().any().any():
        raise ValueError('Paired diagnostic requires both candidates for every frame')
    axes[0].scatter(pairs.iloc[:, 0] * 100, pairs.iloc[:, 1] * 100, s=9, alpha=.35)
    axes[0].plot([0, 100], [0, 100], ':', color='gray')
    axes[0].set(xlabel='A frame spotting Hmean (%)', ylabel='B frame spotting Hmean (%)', xlim=(0, 100), ylim=(0, 100))
    difference = (pairs.iloc[:, 1] - pairs.iloc[:, 0]) * 100
    axes[1].hist(difference, bins=np.linspace(-100, 100, 41), color=COLORS[1])
    axes[1].axvline(0, color='gray', linestyle=':')
    axes[1].set(xlabel='B minus A frame Hmean (percentage points)', ylabel='Frames', xlim=(-100, 100),
                title=f'All {len(pairs):,} paired frames; mean difference {difference.mean():.2f} pp')
    return fig


def plot_costs(data):
    fig, axes = _figure('Observed per-frame inference wall time',
                        'Observed costs on this run; includes recorded failures. No speed ranking; startup/load costs are reported separately.')
    rows = data['frame_scores'].query('variant == "primary"')
    for cid, label, color in zip(CANDIDATES, LABELS, COLORS):
        candidate_rows = rows.loc[rows.candidate_id == cid, 'wall_seconds']
        values = pd.to_numeric(candidate_rows, errors='coerce')
        values = np.sort(values[np.isfinite(values)].to_numpy())
        if not len(values):
            for ax in axes:
                ax.plot([], [], color=color, label=f'{label}: no finite recorded costs ({len(candidate_rows):,} frames)')
            continue
        axes[0].step(values, np.arange(1, len(values) + 1) / len(values) * 100, where='post', color=color,
                     label=f'{label}: n={len(values):,}/{len(candidate_rows):,}, max={values[-1]:.2f}s')
        axes[1].plot([50, 90, 95, 99, 100], np.percentile(values, [50, 90, 95, 99, 100]), 'o-', color=color,
                     label=f'{label}: sum={values.sum():,.1f}s')
    axes[0].set(xlabel='Observed wall seconds (full tail)', ylabel='Recorded frames at or below (%)', ylim=(0, 100), xlim=(0, None))
    axes[1].set(xlabel='Percentile (100 = maximum)', ylabel='Observed wall seconds', ylim=(0, None))
    for ax in axes:
        ax.legend(fontsize=8)
    return fig


def plot_uncertainty(data):
    fig, axes = _figure('Exploratory paired spotting Hmean intervals: B minus A',
                        'Spotting only. Released course/folder proxies; seven courses do not establish a generalized winner. Zero is marked.')
    rows = data['bootstrap']
    for ax, group in zip(axes, ('course', 'source_group')):
        table = rows[rows.group_key == group].set_index('variant').reindex(VARIANTS)
        y = np.arange(len(table))
        ax.hlines(y, table.lower * 100, table.upper * 100, color='#638675', linewidth=3)
        ax.scatter(table.observed * 100, y, color='#222222', zorder=3)
        for i, row in enumerate(table.itertuples()):
            ax.annotate(f'{row.observed * 100:.2f} [{row.lower * 100:.2f}, {row.upper * 100:.2f}]',
                        (row.observed * 100, i), xytext=(0, 9), textcoords='offset points', ha='center', fontsize=8)
        ax.axvline(0, color='gray', linestyle=':')
        ax.margins(x=.35)
        ax.set(yticks=y, yticklabels=VARIANT_LABELS, xlabel='Spotting Hmean difference (percentage points)',
               title=f'{group.replace("_", " ")}: {int(table.iloc[0].cluster_count)} clusters', ylim=(-.6, len(table) - .4))
        ax.tick_params(axis='y', labelsize=8)
    fig.subplots_adjust(left=.15, wspace=.6)
    return fig
