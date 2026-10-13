"""Append executed historical paired-recognition diagnostics, preserving earlier outputs."""
from pathlib import Path
import os
import nbformat
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
from traitlets.config import Config

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / 'experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb'
MARKER = '## Historical paired recognition analysis — 2026-10-13'


def cells():
    return [nbformat.v4.new_markdown_cell(MARKER + '''

These cells re-analyze the saved **2026-10-09 CPU predictions**, without model inference.
All 15,379 released validation labels remain unchanged. Micro CER weights characters;
exact-word accuracy uses normalized full-word equality. Video/course and feature bins
are descriptive, correlated and confounded; they do not establish causal image effects.
Historical runs overlapped, so their speed is not compared. Different-label dHash flags
are review candidates, **not demonstrated annotation errors**. This is an exposed
validation analysis, not an untouched test result.

Run locally with the benchmark repository, extracted validation data and historical
prediction files available. A separate comparison notebook handles fresh acquisition
and inference. Saved outputs below are real executed historical-data analyses.
'''), nbformat.v4.new_code_cell('''from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from IPython.display import display, Markdown
roots = [Path.cwd(), *Path.cwd().parents, Path.cwd()/'benchmark']
ROOT = next(p for p in roots if (p/'experiments/scripts/ocr_validation_recognition.py').is_file())
sys.path.insert(0, str(ROOT))
from experiments.scripts.ocr_validation_recognition import load_cohort, normalize
from experiments.scripts.summarize_ocr_validation import load, score, verify_archive, verify_extraction
DATA = ROOT/'experiments/datasets/iiit_cvid/IIIT-CVid'
HIST = ROOT/'experiments/outputs/ocr_validation_261009'
OUT = ROOT/'experiments/outputs/ocr_eda_261013'
OUT.mkdir(parents=True, exist_ok=True)
archive = ROOT/'research-data/iiit-cvid-source/IIIT-CVid.zip'
verify_archive(archive)
verified_files = verify_extraction(archive, DATA)
cohort = load_cohort(DATA)
references = {key: label for key, _, label in cohort}
expected_hashes = {'easyocr_cpu_full.jsonl':'93dfaa733cb6068a0152df63bd1c3122aba6e6260ad213bcf16a5ce7f93b1353',
 'paddleocr_full.jsonl':'3d4c1be2b403672aa325a3ecf685e2042e9eb8bc6f153250f6c7e176dfed901b'}
for name, expected in expected_hashes.items():
    assert hashlib.sha256((HIST/name).read_bytes()).hexdigest() == expected, name
easy = load('easyocr_cpu', HIST, references)
paddle = load('paddleocr', HIST, references)
records = []
for key, path, label in cohort:
    with Image.open(path) as image:
        gray = np.asarray(image.convert('L'))
        width, height = image.size
    parts = Path(key).parts
    records.append(dict(crop_id=key, course=parts[2], video='/'.join(parts[2:4]),
        label=label, chars=len(normalize(label)), width=width, height=height,
        contrast=float(gray.std()), digits=any(c.isdigit() for c in label),
        punctuation=any(not c.isalnum() and not c.isspace() for c in label),
        easy=easy[key]['edit_distance'], paddle=paddle[key]['edit_distance'],
        easy_prediction=easy[key]['prediction'], paddle_prediction=paddle[key]['prediction']))
paired = pd.DataFrame(records)
paired['delta_edits'] = paired.paddle - paired.easy
summary = pd.DataFrame([dict(engine=name, **score(list(rows.values())))
    for name, rows in [('EasyOCR CPU 1.7.2', easy), ('PaddleOCR CPU 2.8.1', paddle)]])
display(summary)
print('Verified extracted source files:', verified_files, '| paired crops:',len(paired),
      '| videos:',paired.video.nunique(),'| courses:',paired.course.nunique())
summary.to_csv(OUT/'historical-engine-summary.csv', index=False)
paired.to_csv(OUT/'historical-paired-features.csv', index=False)
'''), nbformat.v4.new_code_cell('''def grouped_scores(frame, feature):
    rows = []
    for name, group in frame.groupby(feature, observed=True, sort=True):
        chars = int(group.chars.sum())
        rows.append(dict(group=str(name), crops=len(group), reference_chars=chars,
            easy_cer=group.easy.sum()/chars, paddle_cer=group.paddle.sum()/chars,
            delta_cer=group.delta_edits.sum()/chars,
            easy_exact=(group.easy==0).mean(), paddle_exact=(group.paddle==0).mean()))
    return pd.DataFrame(rows)
course_scores = grouped_scores(paired, 'course')
video_scores = grouped_scores(paired, 'video')
display(course_scores)
display(video_scores.describe())
fig, axes = plt.subplots(1, 3, figsize=(16,4))
course_scores.set_index('group')[['easy_cer','paddle_cer']].plot.bar(ax=axes[0])
axes[0].set(title='Micro CER within each course', xlabel='Course ID', ylabel='CER')
axes[1].hist([video_scores.easy_cer, video_scores.paddle_cer], bins=20,
    label=['EasyOCR','PaddleOCR']); axes[1].legend()
axes[1].set(title='Video CER distribution (each video once)', xlabel='Video micro CER', ylabel='Videos')
axes[2].scatter(video_scores.easy_cer, video_scores.paddle_cer, s=np.sqrt(video_scores.crops)*5, alpha=.6)
limit=max(video_scores.easy_cer.max(),video_scores.paddle_cer.max())
axes[2].plot([0,limit],[0,limit], '--', color='gray')
axes[2].set(xlabel='EasyOCR video CER', ylabel='PaddleOCR video CER', title='Paired source-video scores')
plt.tight_layout(); plt.savefig(OUT/'historical-course-video.png', dpi=130); plt.show()
course_scores.to_csv(OUT/'historical-course-scores.csv',index=False)
video_scores.to_csv(OUT/'historical-video-scores.csv',index=False)
print('Video deltas negative / tied / positive:', (video_scores.delta_cer<0).sum(),
      (video_scores.delta_cer==0).sum(), (video_scores.delta_cer>0).sum())
'''), nbformat.v4.new_code_cell('''paired['length_bin'] = pd.cut(paired.chars,[0,1,3,6,10,np.inf], labels=['1','2-3','4-6','7-10','11+'])
paired['width_bin'] = pd.cut(paired.width,[0,20,40,80,160,np.inf], labels=['1-20','21-40','41-80','81-160','161+'])
paired['contrast_bin'] = pd.cut(paired.contrast,[-1,20,40,60,80,np.inf], labels=['0-20','20-40','40-60','60-80','80+'])
features = ['length_bin','width_bin','contrast_bin','digits','punctuation']
fig, axes = plt.subplots(2,3,figsize=(16,9))
for feature, ax in zip(features, axes.flat):
    table = grouped_scores(paired, feature)
    display(Markdown('**'+feature+'**')); display(table)
    table.to_csv(OUT/('historical-'+feature+'.csv'),index=False)
    table.set_index('group')[['easy_cer','paddle_cer']].plot.bar(ax=ax)
    ax.set(title=feature+' (descriptive)',ylabel='Micro CER',xlabel='Bin')
axes.flat[-1].axis('off')
plt.tight_layout(); plt.savefig(OUT/'historical-feature-strata.png',dpi=130); plt.show()
print('Intensity standard deviation is only a contrast proxy; no quality or readability labels were inferred.')
'''), nbformat.v4.new_code_cell('''paired['outcome'] = np.select([paired.paddle<paired.easy, paired.paddle>paired.easy],
    ['Paddle fewer edits','Easy fewer edits'],default='Equal edits')
wins = paired.outcome.value_counts().rename_axis('outcome').reset_index(name='crops')
display(wins)
fig, ax=plt.subplots(figsize=(7,4)); wins.set_index('outcome').crops.plot.bar(ax=ax)
ax.set(ylabel='Crops',title='Paired edit-distance outcome'); plt.tight_layout()
plt.savefig(OUT/'historical-paired-outcome.png',dpi=130); plt.show()
review = pd.read_csv(HIST/'eda_dhash_different_label_review.csv')
flagged = set(review.left)|set(review.right)
assert len(flagged)==537 and flagged <= set(paired.crop_id)
paired['review_flag'] = paired.crop_id.isin(flagged)
sensitivity=[]
for name, frame in [('All released validation labels',paired),
    ('537 dHash review candidates only',paired[paired.review_flag]),
    ('Complement excluding review candidates (sensitivity only)',paired[~paired.review_flag])]:
    for engine,column in [('EasyOCR','easy'),('PaddleOCR','paddle')]:
        sensitivity.append(dict(scope=name, engine=engine,crops=len(frame),
            reference_chars=int(frame.chars.sum()),micro_cer=frame[column].sum()/frame.chars.sum(),
            exact_word_rate=(frame[column]==0).mean()))
sensitivity=pd.DataFrame(sensitivity); display(sensitivity)
sensitivity.to_csv(OUT/'historical-review-flag-sensitivity.csv',index=False)
print('Primary result retains all 15379 crops. Flags do not prove corrupt labels; exclusion is not a new benchmark cohort.')
'''), nbformat.v4.new_code_cell('''# Deterministic examples: largest paired gain, largest loss, and largest shared
# error; ties break by crop ID. Selection exposes errors and is not representative.
galleries = {
 'Paddle fewer edits':paired[paired.delta_edits<0].sort_values(['delta_edits','crop_id']).head(4),
 'Easy fewer edits':paired[paired.delta_edits>0].sort_values(['delta_edits','crop_id'],ascending=[False,True]).head(4),
 'Both wrong':paired[(paired.easy>0)&(paired.paddle>0)].assign(shared_error=lambda f:np.minimum(f.easy,f.paddle)).sort_values(['shared_error','crop_id'],ascending=[False,True]).head(4)}
for title, frame in galleries.items():
    fig, axes=plt.subplots(len(frame),1,figsize=(13,2.1*len(frame)),squeeze=False)
    for ax, row in zip(axes.flat,frame.itertuples()):
        with Image.open(DATA/row.crop_id) as image: ax.imshow(image.convert('RGB'))
        ax.set_title(f'{row.crop_id} | released={row.label!r} | review flag={row.review_flag}\\n'
            f'Easy={row.easy_prediction!r} ({row.easy} edits); Paddle={row.paddle_prediction!r} ({row.paddle} edits)',fontsize=9)
        ax.axis('off')
    fig.suptitle(title+' — error-focused examples'); plt.tight_layout()
    plt.savefig(OUT/('historical-errors-'+title.replace(' ','-')+'.png'),dpi=130); plt.show()
paired.to_csv(OUT/'historical-paired-features.csv',index=False)
receipt={'scope':'historical CPU validation recognition; no new inference',
    'crops':len(paired),'courses':paired.course.nunique(),'videos':paired.video.nunique(),
    'review_flagged_crops':len(flagged),'verified_source_files':verified_files,
    'prediction_sha256':expected_hashes,'paired_outcomes':paired.outcome.value_counts().to_dict(),
    'source_labels_modified':False,'timing_comparable':False,'unseen_test_claim':False}
(OUT/'historical-analysis-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
display(Markdown('**Interpretation:** read course/video and feature tables together: course composition and word length can explain apparent feature differences. '
    'Paired crop outcomes and deterministic galleries reveal complementary failures; released labels remain the scoring reference. '
    'PaddleOCR has lower aggregate CER in this historical validation run, but this establishes neither frame detection performance nor a general deployment winner.'))
''')]


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    cutoff = next((i for i,c in enumerate(notebook.cells) if MARKER in c.source),len(notebook.cells))
    notebook.cells = notebook.cells[:cutoff]
    # Resolve the repository from either its root, workspace root or notebook folder.
    notebook.cells[1].source = notebook.cells[1].source.replace('ROOT = Path.cwd()',
        "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents, Path.cwd()/'benchmark'] if (p/'experiments/scripts/ocr_validation_recognition.py').is_file())")
    notebook.cells[9].source = notebook.cells[9].source.replace('outputs/ocr_validation_261009/eda_dhash', 'outputs/ocr_eda_261013/eda_dhash')
    notebook.cells[12].source = notebook.cells[12].source.replace("ROOT / 'plans/reports/ocr-iiit-cvid-validation-frame-adjudication-261010.csv'",
        "ROOT / 'experiments/outputs/ocr_eda_261013/validation-frame-adjudication.csv'")
    extension=nbformat.v4.new_notebook(cells=cells())
    # An in-process IPython execution captures real rich tables/plots without
    # requiring a Jupyter server/socket. Record this explicitly in the notebook.
    extension.cells[0].source += '\nExecution provenance: added cells executed with in-process IPython (not a fresh Jupyter kernel).\n'
    config=Config()
    config.HistoryManager.enabled=False
    shell = InteractiveShell.instance(config=config)
    import matplotlib
    matplotlib.use('module://matplotlib_inline.backend_inline')
    os.chdir(ROOT)
    count = max((c.execution_count or 0 for c in notebook.cells if c.cell_type=='code'),default=0)
    for cell in extension.cells:
        if cell.cell_type!='code':
            continue
        count += 1
        with capture_output() as captured:
            result = shell.run_cell(cell.source)
        if result.error_before_exec or result.error_in_exec:
            raise RuntimeError(captured.stdout + captured.stderr) from (result.error_before_exec or result.error_in_exec)
        cell.execution_count=count
        cell.outputs=[]
        if captured.stdout:
            cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
        if captured.stderr:
            cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
        for output in captured.outputs:
            cell.outputs.append(nbformat.v4.new_output('display_data',data=output.data,metadata=output.metadata))
        print('Executed analysis cell',count,flush=True)
    notebook.cells.extend(extension.cells)
    nbformat.validate(notebook)
    nbformat.write(notebook,NOTEBOOK)
    print('Preserved',cutoff,'historical cells; executed',len(extension.cells)-1,'new code cells.')


if __name__=='__main__':
    main()
