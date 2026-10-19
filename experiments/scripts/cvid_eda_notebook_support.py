"""Visible notebook exports, review identity checks and source metadata inventory."""
from collections import Counter
import csv
import json
import re
import zipfile

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import HTML, Image, Markdown, display

from experiments.scripts.cvid_eda_common import OUT, ROOT, SOURCE, sha, write_csv, write_json
from experiments.scripts.cvid_eda_pair_review import validate_pair_decisions

EXPORTS = []


def table(frame, name, preview=None):
    """Always export every row; preview truncation is explicit in the caption."""
    EXPORTS.append(write_csv('tables/'+name+'.csv',frame.to_dict('records')))
    shown = frame if preview is None else frame.head(preview)
    display(Markdown(f'**{name}: {len(frame):,} rows exported; {len(shown):,} shown.**'))
    display(HTML(shown.to_html(index=False,escape=True)))


def figure(fig, name):
    folder = OUT/'figures'; folder.mkdir(exist_ok=True)
    for suffix in ('png','svg'):
        path = folder/(name+'.'+suffix)
        fig.savefig(path,dpi=140,bbox_inches='tight')
        EXPORTS.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
    display(fig); plt.close(fig)


def gallery(folder):
    for path in sorted((OUT/folder).glob('*.jpg')):
        display(Markdown(f'**{folder}/{path.name}**'))
        display(Image(filename=str(path)))


def video_metadata():
    records = []
    with zipfile.ZipFile(SOURCE) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith('IIIT-CVid/Frames/') and name.endswith('/metadata.txt') and len(name.split('/'))==6:
                raw = archive.read(name); text = raw.decode('utf-8-sig',errors='replace')
                _,_,split,course,video,_ = name.split('/')
                complete = next((line.split(':',1)[1].strip() for line in text.splitlines()
                                 if line.strip().startswith('Complete name') and ':' in line),'')
                records.append(dict(split=split,course=course,source_group=course+'/'+video,complete_name=complete,
                    http_urls=' | '.join(sorted(set(re.findall(r'https?://[^\s]+',text)))),
                    verified_per_video_source_url='',source_mapping='not_verified; local media filename only',
                    metadata_member=name,metadata_sha256=__import__('hashlib').sha256(raw).hexdigest()))
    return pd.DataFrame(records)


def verify_reviews(frames, objects):
    pair_receipt = json.loads((OUT/'pair-review-input-receipt.json').read_text(encoding='utf-8'))
    if sha(ROOT/pair_receipt['inputs']['path'])!=pair_receipt['inputs']['sha256']:
        raise ValueError('pair input identity mismatch')
    for entry in pair_receipt['contact_sheets']:
        if sha(OUT/entry['path'])!=entry['sha256']: raise ValueError('pair contact sheet changed')
    visual = json.loads((OUT/'pair-review-visual-receipt.json').read_text(encoding='utf-8'))
    if sha(OUT/'pair-review-decisions.csv')!=visual['decisions_sha256'] or visual['coverage']['reviewed_pairs']!=469:
        raise ValueError('visual pair review receipt mismatch')
    if visual['inputs_sha256']!=pair_receipt['inputs']['sha256']:
        raise ValueError('reviewed pair input identity mismatch')
    if len(visual['contact_sheets'])!=59 or not all(x['directly_inspected'] for x in visual['contact_sheets']):
        raise ValueError('visual page review coverage incomplete')
    reviewed_pages = {(x['path'],x['sha256']) for x in visual['contact_sheets']}
    expected_pages = {(x['path'],x['sha256']) for x in pair_receipt['contact_sheets']}
    if len(reviewed_pages)!=59 or reviewed_pages!=expected_pages:
        raise ValueError('reviewed pair page/hash set differs from inputs')
    pairs = pd.DataFrame(validate_pair_decisions())
    expected = frames.set_index('frame_id').image_sha256.to_dict()
    for row in pairs.to_dict('records'):
        for key in ('left','right'):
            if expected[row[key]]!=row[key+'_image_sha256']: raise ValueError('current frame/pair identity mismatch')
    sem_receipt = json.loads((OUT/'semantic-review-receipt.json').read_text(encoding='utf-8'))
    if sha(OUT/'semantic-sample.csv')!=sem_receipt['sample_csv_sha256']:
        raise ValueError('semantic sample changed after review')
    item = sem_receipt['decisions']
    if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('semantic decision ledger changed')
    semantic = pd.read_csv(ROOT/item['path'],keep_default_na=False,dtype={'course':str})
    sample = pd.read_csv(OUT/'semantic-sample.csv',keep_default_na=False,dtype={'course':str})
    if len(semantic)!=72 or semantic.sample_id.duplicated().any() or set(semantic.object_id)!=set(sample.object_id):
        raise ValueError('semantic review incomplete or duplicate')
    if semantic.set_index('sample_id').object_id.to_dict()!=sample.set_index('sample_id').object_id.to_dict():
        raise ValueError('semantic sample/object mapping changed')
    allowed = {'visually_consistent_at_review_resolution','apparent_disagreement','uncertain'}
    if not semantic.decision.isin(allowed).all() or not semantic.rationale.str.strip().ne('').all() or not semantic.reviewer.str.strip().ne('').all():
        raise ValueError('invalid semantic review decision/rationale/reviewer')
    gallery_receipt = json.loads((OUT/'gallery-receipt.json').read_text(encoding='utf-8'))
    expected_semantic_pages = {(x['path'],x['sha256']) for x in gallery_receipt['galleries'] if x['path'].startswith('semantic-contact-sheets/')}
    reviewed_semantic_pages = {(x['path'],x['sha256']) for x in sem_receipt['reviewed_pages']}
    if len(sem_receipt['reviewed_pages'])!=12 or len(reviewed_semantic_pages)!=12 or reviewed_semantic_pages!=expected_semantic_pages:
        raise ValueError('semantic reviewed page coverage differs')
    if sha(OUT/'semantic-focused-review.png')!=sem_receipt['focused_review_sha256']:
        raise ValueError('focused semantic review pixels changed')
    gt = objects.set_index('object_id').text.to_dict()
    for row in semantic.to_dict('records'):
        if gt[row['object_id']]!=row['xml_text']: raise ValueError('review XML identity changed')
        for kind in ('context','crop'):
            if sha(OUT/'semantic-source'/(row['sample_id']+'-'+kind+'.png'))!=row['source_'+kind+'_sha256']:
                raise ValueError('semantic review source pixels changed')
    for entry in sem_receipt['reviewed_pages']:
        if sha(OUT/entry['path'])!=entry['sha256']: raise ValueError('semantic contact sheet changed')
    return pairs,semantic


def finish(scan_receipt, pairs, semantic, snapshot):
    if sha(SOURCE)!=scan_receipt['source_archive_sha256']: raise ValueError('source ZIP changed during EDA')
    current = {p:sha(ROOT/p) for p in snapshot}
    if current!=snapshot: raise ValueError('existing spotting freeze changed during EDA')
    inputs = scan_receipt['artifacts'] + EXPORTS
    for name in ('pair-review-input-receipt.json','pair-review-visual-receipt.json','pair-review-decisions.csv',
                 'semantic-review-receipt.json','semantic-review-decisions.csv','semantic-sample.csv',
                 'semantic-sample-rule.json','gallery-receipt.json','scan-receipt.json'):
        path = OUT/name
        inputs.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
    summary = dict(schema='cvid_all_split_eda_v1',source_archive_sha256=scan_receipt['source_archive_sha256'],
        coverage={k:scan_receipt[k] for k in ('frames','objects','decoded_crops','indexed_crops','read_failures','unmatched_objects')},
        crop_correspondence=scan_receipt['crop_correspondence'],raw_crop_xml_label_differences=scan_receipt['raw_crop_xml_label_differences'],
        visual_pair_review=dict(count=len(pairs),decisions=pairs.decision.value_counts().to_dict(),reviewer='single Codex visual review; queue-limited'),
        semantic_review=dict(samples=len(semantic),decisions=semantic.decision.value_counts().to_dict(),
            limit='course/height diagnostic sample; two Codex reviewers, not independent human gold; no population error rate'),
        readiness=dict(eda_execution_complete=True,descriptive_released_label_protocol_design_supported=True,
            blind_test_claim_supported=False,source_video_independence_verified=False,semantic_gt_certified=False,
            cohort_test_frozen=False,spotting_inference_executed=False),
        unresolved=['semantic flags and selective annotation scope need a predeclared test-GT policy',
                    'per-video identity and writer independence not established',
                    'historical test model-use completeness and model-pretraining overlap unknown'],
        existing_spotting_freeze_sha256=snapshot,scan_runtime=scan_receipt['runtime'],wall_seconds=scan_receipt['wall_seconds'],
        code_sha256={p.name:sha(p) for p in (ROOT/'experiments/scripts').glob('cvid_eda_*.py')},artifacts=inputs)
    write_json('eda-summary.json',summary)
    return summary
