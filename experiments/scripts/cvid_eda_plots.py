"""All-split CVID EDA figures from decoded exports; no sampling or inference."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from experiments.scripts.cvid_eda_common import OUT

SPLITS = ('train', 'val', 'test')
COLORS = dict(zip(SPLITS, ('#3573a6', '#d38b24', '#43896c')))


def load_tables():
    """Attach coarse course-level media metadata without multiplying records."""
    data = {key: pd.read_csv(OUT / filename, keep_default_na=False, dtype={'course': str})
            for key, filename in dict(frames='frames.csv.gz', objects='objects.csv.gz',
                                      crops='crops.csv.gz', courses='courses.csv').items()}
    metadata = data['courses'][['split', 'course', 'Medium']].rename(columns={'Medium': 'medium'})
    for key in ('frames', 'objects', 'crops'):
        count = len(data[key])
        data[key] = data[key].merge(metadata, on=['split', 'course'], how='left', validate='many_to_one')
        assert len(data[key]) == count and data[key]['medium'].notna().all()
    return data


def _figure(title, rows=1, cols=2, note=''):
    fig, axes = plt.subplots(rows, cols, figsize=(12, 4.8 * rows), squeeze=False)
    fig.suptitle(title, fontsize=15)
    if note:
        fig.text(.01, .01, note, fontsize=9)
    fig.subplots_adjust(top=.88 if rows == 1 else .93, bottom=.18 if note else .13, hspace=.4, wspace=.3)
    return fig, axes.ravel()


def _hist(ax, table, field, label, log=False):
    """One pooled bin grid per panel; all finite observations included."""
    values = table[field].to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    bins = np.linspace(values.min(), values.max(), 36) if values.max() > values.min() else 10
    for split in SPLITS:
        ax.hist(table.loc[table.split == split, field], bins=bins, histtype='step', linewidth=1.8,
                label=split, color=COLORS[split])
    if log:
        ax.set_yscale('symlog', linthresh=1)
    ax.set(xlabel=label, ylabel='Records' + (' (symlog)' if log else ''))
    ax.legend()


def _bars(ax, table, field, label, percent=False):
    values = pd.crosstab(table[field], table.split).reindex(columns=SPLITS, fill_value=0)
    if percent:
        values = values.div(values.sum(axis=0), axis=1) * 100
    values.plot.bar(ax=ax, color=[COLORS[s] for s in SPLITS], rot=20)
    ax.set(xlabel=label, ylabel='Percent within split' if percent else 'Records')


def plot_counts(data):
    fig, axes = _figure('Released annotation coverage by native split')
    counts = pd.DataFrame({key: data[key].groupby('split').size() for key in ('frames', 'objects', 'crops')}).reindex(SPLITS)
    counts.plot.bar(ax=axes[0], rot=0, logy=True)
    axes[0].set(ylabel='Records (log scale)', xlabel='Native split')
    for container in axes[0].containers:
        axes[0].bar_label(container, fmt='%.0f', fontsize=8, rotation=90, padding=3)
    structural = pd.DataFrame({
        'Courses': data['frames'].groupby('split').course.nunique(),
        'Video groups': data['frames'].groupby('split').source_group.nunique()}).reindex(SPLITS)
    structural.plot.bar(ax=axes[1], rot=0)
    axes[1].set(ylabel='Groups', xlabel='Native split')
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt='%.0f')
    return fig


def plot_courses(data):
    fig, axes = _figure('Course composition and concentration across video groups', note='Video groups are released course/video folders; they are not independent word samples.')
    counts = data['frames'].groupby(['course', 'split']).size().unstack(fill_value=0)
    counts = counts.reindex(sorted(counts.index, key=int)).reindex(columns=SPLITS, fill_value=0)
    counts.plot.bar(stacked=True, ax=axes[0], color=[COLORS[s] for s in SPLITS], rot=0)
    axes[0].set(xlabel='Course ID (numeric order)', ylabel='Frames')
    for split in SPLITS:
        sizes = data['frames'].query('split == @split').groupby('source_group').size().sort_values(ascending=False)
        axes[1].plot(np.arange(1, len(sizes)+1)/len(sizes)*100, sizes.cumsum()/sizes.sum()*100,
                     label=f'{split} ({len(sizes)} groups)', color=COLORS[split])
    axes[1].plot([0, 100], [0, 100], ':', color='gray', label='Equal size reference')
    axes[1].set(xlabel='Video groups, largest first (%)', ylabel='Cumulative frames (%)', xlim=(0,100), ylim=(0,100))
    axes[1].legend(fontsize=8)
    return fig


def plot_density(data):
    fig, axes = _figure('Text density and number of frames per video group')
    _hist(axes[0], data['frames'], 'objects', 'Word boxes per frame', log=True)
    groups = data['frames'].groupby(['split', 'source_group']).size().reset_index(name='frames')
    _hist(axes[1], groups, 'frames', 'Frames per released video group', log=True)
    return fig


def plot_modalities(data):
    fig, axes = _figure('Released course-level medium composition', note='Medium is coarse author metadata for a course; Mixed is retained. It is not a per-frame visual label.')
    _bars(axes[0], data['frames'], 'medium', 'Course medium')
    _bars(axes[1], data['objects'], 'medium', 'Course medium', percent=True)
    axes[0].set_ylabel('Frames'); axes[1].set_ylabel('Word boxes within split (%)')
    return fig


def plot_resolution(data):
    fig, axes = _figure('Decoded frame dimensions and aspect ratio', rows=2)
    frames = data['frames'].assign(aspect=data['frames'].width/data['frames'].height)
    for ax, field, label in zip(axes[:3], ('width','height','aspect'), ('Frame width (px)','Frame height (px)','Frame width / height')):
        _hist(ax, frames, field, label, log=True)
    _bars(axes[3], frames.assign(resolution=frames.width.astype(str)+' × '+frames.height.astype(str)), 'resolution', 'All decoded resolutions')
    axes[3].tick_params(axis='x', labelsize=7, rotation=65)
    return fig


def plot_boxes(data):
    objects = data['objects']; valid = objects[objects.geometry_valid]
    fig, axes = _figure('Raw XML box geometry', rows=2,
                         note=f'Distributions use geometry-valid boxes ({len(valid):,}/{len(objects):,}); raw coordinates are preserved. Invalid boxes shown separately.')
    for ax, field, label in zip(axes[:3], ('box_height_rel','area_rel','aspect_ratio'),
                               ('Box height / decoded frame height','Box area / decoded frame area','Box width / height')):
        _hist(ax, valid, field, label, log=True)
    counts = objects.assign(status=np.where(objects.geometry_valid, 'Valid', 'Invalid'))
    _bars(axes[3], counts, 'status', 'Raw geometry status')
    axes[3].set_yscale('symlog', linthresh=1); axes[3].set_ylabel('Word boxes (symlog)')
    return fig


def plot_crops(data):
    fig, axes = _figure('Decoded word crops and index-to-XML correspondence', rows=2,
                         note='Equivalent ambiguous = multiple pixel/text-identical objects; allocation does not prove author object identity.')
    for ax, field, label in zip(axes[:3], ('width','height','characters'), ('Crop width (px)','Crop height (px)','Normalized crop-label characters')):
        _hist(ax, data['crops'], field, label, log=True)
    _bars(axes[3], data['crops'], 'correspondence', 'Pixel + normalized label correspondence')
    axes[3].set_yscale('symlog', linthresh=1)
    axes[3].set_ylabel('Crops (symlog)')
    for container in axes[3].containers:
        axes[3].bar_label(container, fmt='%.0f', fontsize=8)
    axes[3].tick_params(axis='x', labelsize=8)
    return fig


def plot_text(data):
    fig, axes = _figure('XML transcription length and character composition', note='Flags overlap. Punctuation includes all non-alphanumeric, non-whitespace characters; normalized length uses spotting normalization.')
    _hist(axes[0], data['objects'], 'characters', 'Normalized XML transcription characters', log=True)
    fields = ['one_character','has_digit','has_punctuation','normalization_changed','slash_in_xml']
    rates = data['objects'].groupby('split')[fields].mean().reindex(SPLITS).T * 100
    rates.index = ['One character','Contains digit','Punctuation / symbol','Normalization changed','Contains slash']
    rates.plot.barh(ax=axes[1], color=[COLORS[s] for s in SPLITS])
    axes[1].set(xlabel='Word boxes within split (%)', ylabel='Flag')
    axes[1].tick_params(axis='y', labelsize=9)
    fig.subplots_adjust(wspace=.75)
    return fig


def plot_quality(data):
    fig, axes = _figure('Image intensity and edge-energy proxies', rows=2,
                         note='Intensity SD and discrete Laplacian variance are uncalibrated proxies; they do not measure legibility or OCR accuracy. Full tails retained.')
    for ax, table, field, label in zip(axes, (data['frames'],data['frames'],data['crops'],data['crops']),
                                      ('gray_std','laplacian_variance','gray_std','laplacian_variance'),
                                      ('Frame grayscale SD','Frame Laplacian variance','Crop grayscale SD','Crop Laplacian variance')):
        _hist(ax, table, field, label, log=True)
    return fig


def plot_vocabulary(data):
    fig, axes = _figure('Normalized transcription vocabulary overlap', note='Repeated word strings across splits are expected vocabulary reuse; they do not establish image/content leakage.')
    vocabulary = {s: set(data['objects'].loc[data['objects'].split == s, 'normalized_text']) for s in SPLITS}
    matrix = np.array([[len(vocabulary[a] & vocabulary[b])/len(vocabulary[a] | vocabulary[b]) for b in SPLITS] for a in SPLITS])
    image = axes[0].imshow(matrix, vmin=0, vmax=1, cmap='Blues')
    axes[0].set(xticks=range(3), xticklabels=SPLITS, yticks=range(3), yticklabels=SPLITS, title='Unique-string Jaccard overlap')
    for i in range(3):
        for j in range(3):
            axes[0].text(j,i,f'{matrix[i,j]:.1%}',ha='center',va='center',color='white' if matrix[i,j]>.5 else 'black')
    fig.colorbar(image, ax=axes[0], shrink=.8)
    axes[1].bar(SPLITS, [len(vocabulary[s]) for s in SPLITS], color=[COLORS[s] for s in SPLITS])
    axes[1].set(xlabel='Native split', ylabel='Distinct normalized XML transcriptions')
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt='%.0f')
    return fig
