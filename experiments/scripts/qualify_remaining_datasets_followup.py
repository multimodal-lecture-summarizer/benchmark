"""Add metadata-only qualification ledgers; never change released labels or decode media."""
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET

from dataset_qualification_io import ROOT, OUT, sha, write_csv, write_json, receipt


def verified(path, expected):
    actual = sha(path)
    assert actual == expected, (path, actual)
    return {'path': str(path.relative_to(ROOT)), 'sha256': actual}


def counts(n, valid, unit):
    return dict(selected=n, observed=n, label_valid=valid, media_valid=0,
                evaluated=0, failed=0, unit=unit,
                label_valid_definition='structural annotation only; not independent task GT',
                media_valid_definition='original source videos verified for target endpoint',
                failed_definition='record read/parse failures; HOLD is not a processing failure')


def mlp():
    path = ROOT / 'experiments/outputs/mlp_eda_source/mlp_anon.zip'
    source = verified(path, 'dbd07ef37de603a22abb7be7d81245034b3c487f4878227cbef36ae3d451cfa7')
    rows, boundaries, errors = [], [], []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        raw = list(csv.DictReader(io.StringIO(z.read('data/raw_video_links.csv').decode('utf-8-sig'))))
        metadata = {r['video_id'].removesuffix('.mp4'): r for r in raw}
        matched = set()
        for name in sorted(n for n in names if n.endswith('/segments.txt')):
            folder = str(PurePosixPath(name).parent)
            transcripts = [n for n in names if str(PurePosixPath(n).parent) == folder and n.endswith('_transcripts.csv')]
            vid = PurePosixPath(transcripts[0]).name.removesuffix('_transcripts.csv') if len(transcripts) == 1 else None
            matched.add(vid)
            times = []
            for line, value in enumerate(z.read(name).decode('utf-8-sig').splitlines(), 1):
                if value.strip():
                    try:
                        time = float(value)
                        if not math.isfinite(time):
                            raise ValueError('non-finite timestamp')
                        times.append((line, time))
                    except ValueError as exc:
                        errors.append(dict(id=vid, member=name, line=line, value=value, reason=str(exc)))
            meta = metadata.get(vid, {})
            duration = float(meta['seconds']) if meta else None
            flags = []
            if not times:
                flags.append('empty_boundaries')
            for index, (line, time) in enumerate(times):
                reasons = []
                if index and time <= times[index - 1][1]:
                    reasons.append('nonincreasing_original_order')
                if time < 0 or duration is not None and time > duration + .05:
                    reasons.append('outside_declared_duration')
                flags.extend(reasons)
                boundaries.append(dict(id=f'{vid}:{line}', video_id=vid, member=name, line=line,
                                       time_s=time, source_group=vid, decision='HOLD',
                                       reason=';'.join(reasons + ['media_alignment_not_observed']),
                                       annotation_structurally_valid=not reasons))
            rows.append(dict(id=vid or folder, annotation_member=name,
                             annotation_sha256=hashlib.sha256(z.read(name)).hexdigest(),
                             source_url=meta.get('youtube_url'), source_group=vid,
                             split='unassigned', boundary_count=len(times),
                             annotation_structurally_valid=bool(times) and not flags,
                             decision='HOLD', reason=';'.join(sorted(set(flags)) +
                                      ['source_media_alignment_and_rights_unverified', 'no_official_split'])))
        for vid in sorted(set(metadata) - matched):
            rows.append(dict(id=vid, source_url=metadata[vid]['youtube_url'], source_group=vid,
                             split='unassigned', annotation_structurally_valid=False,
                             decision='HOLD', reason='missing_annotation_folder'))
        json_issues = []
        for name in sorted(n for n in names if n.endswith('.json')):
            try:
                json.loads(z.read(name))
            except (ValueError, UnicodeError) as exc:
                json_issues.append(dict(member=name, decision='HOLD', reason=str(exc)))
    artifacts = [write_csv('mlpdataset-id-ledger.csv', rows),
                 write_csv('mlpdataset-boundary-ledger.csv', boundaries),
                 write_csv('mlpdataset-parse-failures.csv', errors),
                 write_csv('mlpdataset-json-anomalies.csv', json_issues)]
    result = receipt('mlpdataset', counts(len(rows), sum(r['annotation_structurally_valid'] for r in rows), 'source video'),
                     artifacts, source=source, boundary_records=len(boundaries),
                     nonincreasing_boundaries=sum('nonincreasing' in r['reason'] for r in boundaries),
                     empty_boundary_files=sum(r.get('boundary_count') == 0 for r in rows),
                     json_parse_failures=json_issues, frozen=False,
                     media_probe_rule='first source video in sorted ID order; additional anomaly source if distinct',
                     endpoint='slide transition: annotation-only diagnostics; no transition F1 permitted',
                     blocker='Original frames, rights and boundary alignment not verified; do not sort annotations as GT.')
    return result


def board(dataset):
    is_access = dataset == 'accessmath'
    archive_name = 'accessmath-official-2017.zip' if is_access else 'lecturemath-official-annotations.zip'
    expected = ('7bffabf04ecf5ee5c03fb36089dba81bbef8c6a0f310002207df6ed51bfd9fee' if is_access else
                'cf0129f4d71a21d7be9b43f71d184e6b711d76375855d873e75636472ca72f45')
    path = ROOT / 'experiments/outputs/board_eda_downloads' / archive_name
    source = verified(path, expected)
    notebook = ROOT / 'experiments/notebooks/diagnostics' / ('accessmath-board-annotations-eda.ipynb' if is_access else 'lecturemath-keyframe-annotations-eda.ipynb')
    cell = ''.join(json.loads(notebook.read_text(encoding='utf-8'))['cells'][2]['source'])
    # Reuse the metadata parser only. No acquisition, image decode, plots or inference cells execute.
    import pandas as pd
    with zipfile.ZipFile(path) as z:
        env = dict(ZIP=z, NAMES=set(z.namelist()), ET=ET, PurePosixPath=PurePosixPath,
                   pd=pd, display=lambda *args: None)
        if not is_access:
            cache = ROOT / 'experiments/outputs/board_eda_downloads'
            verified(cache / 'lecturemath-db.xml', 'e67d3e90b8d06658af09cacf1c022560d8bb0d83550a534c02f22bfda7cad834')
            verified(cache / 'lecturemath-edited.json', '136568963e657f1b206e8136e8a7263e40390b9374c00ec6b8112e7009c10d15')
            cell = cell[cell.index('def is_primary_xml'):]
            env.update(DB=ET.fromstring((cache / 'lecturemath-db.xml').read_bytes()),
                       EDITED=json.loads((cache / 'lecturemath-edited.json').read_text()))
        exec(compile(cell, str(notebook) + ':metadata-cell', 'exec'), env)
        rows, keyframes = env['rows'], []
        for row in rows:
            prefix = env['annotation_prefix'](row['id'])
            member = prefix + '/segments.xml'
            root = ET.fromstring(z.read(member))
            for key in root.findall('.//VideoKeyFrames/VideoKeyFrame'):
                keyframes.append(dict(id=f"{row['id']}:{key.findtext('Index')}", video_id=row['id'],
                                      split=row['split'], frame_index=key.findtext('Index'),
                                      abs_time_raw=key.findtext('AbsTime'),
                                      abs_time_unit='unverified; do not assume seconds',
                                      decision='HOLD', reason='source_media_timebase_and_required_state_semantics_unverified'))
            structural = (row['metadata_present'] and row['primary_xml'] and row['segments_xml'] and
                          not row['missing_keyframe_png'] and not row['orphan_keyframe_png'] and
                          not row['bad_interval_indices'])
            row.update(annotation_structurally_valid=structural, decision='HOLD',
                       annotation_sha256=hashlib.sha256(z.read(member)).hexdigest(),
                       reason=('orphan_or_missing_keyframe;' if not structural else '') +
                       'original_video_alignment_and_required_state_semantics_unverified',
                       source_group_identity='released SourceID; course/channel grouping signal, not exact video identity',
                       original_media_valid=False)
        overlap = defaultdict(set)
        for row in rows:
            if row['source_id']:
                overlap[row['source_id']].add(row['split'])
        overlap_rows = [dict(source_group=k, splits=sorted(v), cross_split=len(v) > 1,
                             decision='HOLD' if len(v) > 1 else 'KEEP',
                             reason='source-level dependence requires review; exact source URL separately checked')
                        for k, v in sorted(overlap.items())]
        artifacts = [write_csv(dataset + '-id-ledger.csv', rows),
                     write_csv(dataset + '-keyframe-ledger.csv', keyframes),
                     write_csv(dataset + '-segment-ledger.csv', env['segment_rows']),
                     write_csv(dataset + '-source-group-ledger.csv', overlap_rows)]
    historical = []
    for c in json.loads(notebook.read_text(encoding='utf-8'))['cells']:
        for output in c.get('outputs', []):
            text = ''.join(output.get('text', []))
            if '"decision"' in text and 'original_videos_decoded' in text:
                try:
                    historical.append(json.loads(text[text.index('{'):]))
                except ValueError:
                    pass
    artifacts.append(write_json(dataset + '-historical-notebook-decision.json', historical))
    return receipt(dataset, counts(len(rows), sum(r['annotation_structurally_valid'] for r in rows), 'annotated video'),
                   artifacts, source=source, keyframe_records=len(keyframes),
                   released_pngs=sum(r['png_keyframes'] for r in rows),
                   original_media_decoded_this_followup=0, image_decoding_rerun=False,
                   historical_evidence=historical, frozen=False,
                   endpoint='released keyframe/summary annotation diagnostics; required board-state endpoint HOLD',
                   blocker='Original video, edit/multipart timebase, source dependence and required-state label semantics unresolved.')


def eduvidqa():
    files = {
        'synthetic_train': ('3c6471d5c01b92a8092a8dcff367f701fbdd80b34f8b02f5c55e0e8ba0a971f5', ('vid_id', 'vid_url', 'final_question', 'final_answer')),
        'synthetic_test': ('0c44b89987ea1f112e5a46843036320132cebd111b37c1203591d31110c2bbaf', ('vid_id', 'vid_url', 'question', 'answer')),
        'real_world_test': ('2b8553dd454cb7038c914809a9c4e3908161955b243de97dc490493c8c092055', ('id', 'url', 'question', 'answer')),
    }
    rows, sources = [], []
    for split, (expected, columns) in files.items():
        path = ROOT / 'research-data/eduvidqa-official/data' / (split + '.csv')
        sources.append(verified(path, expected))
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for index, raw in enumerate(csv.DictReader(stream), 1):
                vid, url, question, answer = (raw.get(c, '').strip() for c in columns)
                timestamp = raw.get('timestamp', '').strip()
                parts = timestamp.split(':')
                syntax = ('blank' if not timestamp else 'three_part_unresolved' if len(parts) == 3 and all(p.isdigit() for p in parts)
                          else 'two_part_syntax_only' if len(parts) == 2 and all(p.isdigit() for p in parts) and int(parts[1]) < 60 else 'invalid')
                rows.append(dict(id=f'{split}:{index}', split=split, physical_csv_row=index, video_id=vid,
                                 source_url=url, source_group=vid, timestamp_raw=timestamp, timestamp_status=syntax,
                                 annotation_structurally_valid=bool(vid and url and question and answer),
                                 question_hash=hashlib.sha256(re.sub(r'\s+', ' ', question.casefold()).strip().encode()).hexdigest(),
                                 decision='HOLD', reason='media_transcript_and_timestamp_alignment_unverified;no_independent_retrieval_evidence_GT'))
    groups = defaultdict(list)
    for row in rows:
        groups[row['video_id']].append(row)
    videos = [dict(id=vid, source_url=part[0]['source_url'], splits=sorted({r['split'] for r in part}),
                   qa_rows=len(part), cross_split=len({r['split'] for r in part}) > 1,
                   decision='HOLD', reason='source_context_not_restored;course_dependence_unverified')
              for vid, part in sorted(groups.items())]
    artifacts = [write_csv('eduvidqa-id-ledger.csv', rows), write_csv('eduvidqa-source-group-ledger.csv', videos)]
    return receipt('eduvidqa', counts(len(rows), sum(r['annotation_structurally_valid'] for r in rows), 'QA CSV row'),
                   artifacts, sources=sources, source_videos=len(videos), frozen=False,
                   three_part_timestamps=sum(r['timestamp_status'] == 'three_part_unresolved' for r in rows),
                   blank_synthetic_test_timestamps=sum(r['split'] == 'synthetic_test' and r['timestamp_status'] == 'blank' for r in rows),
                   cross_split_video_groups=sum(r['cross_split'] for r in videos),
                   endpoint='released-answer agreement diagnostic only after source-context qualification; retrieval relevance HOLD',
                   blocker='Official release has no independent evidence spans; media/transcripts and timestamp semantics unverified.')


if __name__ == '__main__':
    # Requested priority, moving on when a source-media qualification gate remains HOLD.
    for name, function in [('mlpdataset', mlp), ('accessmath', lambda: board('accessmath')),
                           ('lecturemath', lambda: board('lecturemath')), ('eduvidqa', eduvidqa)]:
        result = function()
        print(name, result['counts'], flush=True)
