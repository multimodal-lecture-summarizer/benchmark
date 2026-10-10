"""Reuse executed LVVO frame EDA and audit public source-link evidence, without decoding media."""
import csv
import hashlib
import json
import re
from collections import Counter
from io import StringIO
from urllib.parse import urljoin

import pandas as pd

from dataset_qualification_io import OUT, ROOT, receipt, sha, write_csv, write_json


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    prior = ROOT / 'plans/reports/lvvo-provenance-split-261010-receipt.json'
    evidence = json.loads(prior.read_text(encoding='utf-8'))
    image_path = prior.with_name('lvvo-provenance-split-261010-image-ledger.csv')
    group_path = prior.with_name('lvvo-provenance-split-261010-video-group-ledger.csv')
    verified = []
    for path, expected in [
        (ROOT / evidence['source_archive'], evidence['source_archive_sha256']),
        (ROOT / evidence['prior_eda_ledger'], evidence['prior_eda_ledger_sha256']),
        (image_path, evidence['image_ledger_sha256']),
        (group_path, evidence['video_group_ledger_sha256']),
    ]:
        actual = sha(path)
        if actual != expected:
            raise ValueError(f'Historical evidence hash mismatch: {path}')
        verified.append({'path': str(path.relative_to(ROOT)), 'sha256': actual})
    probes_path = OUT / 'lvvo-network-probes.json'
    probes = json.loads(probes_path.read_text(encoding='utf-8'))
    for probe in probes:
        if 'sha256' in probe:
            saved = OUT / probe['path'].replace('\\', '/').rsplit('/', 1)[-1]
            if sha(saved) != probe['sha256']:
                raise ValueError(f'Network proof changed: {saved}')
    images, groups = read_csv(image_path), read_csv(group_path)
    paths_by_token = {}
    for probe in probes:
        if not probe['name'].startswith('videopoints-course') or probe.get('status') != 200:
            continue
        saved = OUT / probe['path'].replace('\\', '/').rsplit('/', 1)[-1]
        html = saved.read_text(encoding='utf-8')
        # Only paths literally present in a public HTML <source> element qualify.
        for source in re.findall(r'''<source\s+src=["'](.+?\.mp4)["']''', html):
            match = re.search(r'/i(\d+)/v(\d+)/', source)
            if match:
                key = ('i' + match[1], 'v' + match[2])
                paths_by_token.setdefault(key, []).append({
                    'source_video_url': urljoin(probe['final_url'], source),
                    'source_page_url': probe['final_url'],
                    'source_page_sha256': probe['sha256'],
                })
    mapped = 0
    for group in groups:
        candidates = paths_by_token.get((group['author_instructor_token'], group['author_video_token']), [])
        group.update(decision='HOLD', reason='source_media_alignment_rights_and_duplicate_review_pending',
                     assigned_split='', eda_annotation_decision='KEEP', source_video_url='',
                     source_link_status='HOLD_no_public_token_match', media_alignment_status='HOLD_not_decoded')
        unique = {item['source_video_url']: item for item in candidates}
        if len(unique) == 1:
            group.update(next(iter(unique.values())))
            group['source_link_status'] = 'public_HTML_instructor_and_video_token_match_not_frame_alignment'
            mapped += 1
        elif len(unique) > 1:
            group['source_link_status'] = 'HOLD_multiple_public_source_paths'
        group['public_source_candidates'] = list(unique.values())
    by_group = {group['author_group_key']: group for group in groups}
    for image in images:
        group = by_group[image['author_group_key']]
        image.update(decision='HOLD', reason=group['reason'], eda_annotation_decision='KEEP',
                     source_video_url=group['source_video_url'], source_video_link_status=group['source_link_status'],
                     assigned_split='', label_valid=True, media_valid=True)
    # Recover only the displayed queue from the prior notebook; remaining pairs were not persisted.
    notebook = ROOT / 'experiments/notebooks/diagnostics/lvvo-four-class-detection-eda.ipynb'
    doc = json.loads(notebook.read_text(encoding='utf-8'))
    pairs = []
    for cell in doc['cells']:
        if 'near_pairs' not in ''.join(cell.get('source', [])):
            continue
        for output in cell.get('outputs', []):
            html = ''.join(output.get('data', {}).get('text/html', []))
            if '<th>dhash_distance</th>' in html:
                pairs = pd.read_html(StringIO(html), index_col=0)[0].to_dict('records')
    for pair in pairs:
        pair.update(decision='HOLD', reason='historical_dHash_candidate_requires_visual_and_source_review',
                    evidence_scope='first_20_displayed_pairs_only_not_complete_313_queue')
    artifacts = [write_csv('lvvo-id-ledger.csv', images), write_csv('lvvo-video-group-ledger.csv', groups),
                 write_csv('lvvo-historical-displayed-duplicate-pairs.csv', pairs),
                 {'path': str(probes_path.relative_to(ROOT)), 'sha256': sha(probes_path)}]
    design = {'status': 'HOLD_design_only_not_frozen', 'assigned_ids': 0,
              'group_key': 'author instructor/course/video token until authoritative source identity review',
              'must_link': 'confirmed shared source or overlapping content must remain in one split',
              'endpoint': 'four manually annotated classes; model-held-out, references previously inspected',
              'freeze_gates': ['finish source linkage and rights', 'review all 257 cross-token candidate pairs',
                               'sample frame-to-video alignment with declared sampling rule',
                               'declare video/course/instructor generalization target and class coverage',
                               'freeze seed, roles, metrics and denominators before inference']}
    artifacts.append(write_json('lvvo-provisional-split-design.json', design))
    result = receipt('lvvo', {'selected': len(images), 'observed': len(images), 'label_valid': len(images),
                             'media_valid': len(images), 'evaluated': 0, 'failed': 0}, artifacts,
                     status='HOLD_formal_benchmark', evidence_reused=verified,
                     source_video_groups=len(groups), public_HTML_source_token_matches=mapped,
                     public_HTML_linked_frames=sum(bool(image['source_video_url']) for image in images),
                     source_video_media_valid=0, source_frame_alignment_verified=0,
                     media_valid_scope='1000 released JPG frames decoded in prior executed EDA; not videos',
                     historical_duplicate_candidate_pairs=313, historical_cross_token_pairs=257,
                     historical_pairs_recovered_from_display=len(pairs),
                     duplicate_review_status='HOLD_full_pair_queue_and_visual_review_missing',
                     source_group_leakage_status='HOLD_no_split_and_incomplete_verified_source_identity',
                     archive_or_images_decoded_this_run=False, assigned_split_count=0,
                     rights='author CC BY 4.0 release statement verified at pinned commit; underlying video scope unverified',
                     author_repository_revision='d53418d8846c5c08abf9cfa7380da8a4f16626ce',
                     decision_counts=dict(Counter(image['decision'] for image in images)),
                     blockers=['underlying video rights and frame alignment',
                               f'{len(groups)-mapped} groups without observed public source-token match',
                               '257 cross-token candidate pairs unadjudicated; only first20 retained',
                               'all labels previously observed; no unseen-reference final test'])
    print(json.dumps({k: result[k] for k in ['counts', 'public_HTML_source_token_matches',
                                           'public_HTML_linked_frames', 'blockers']}, indent=2))


if __name__ == '__main__':
    main()
