"""Read-only source inventory; derived ledgers do not freeze an evaluation cohort."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
from experiments.scripts.spotting_metrics import normalize_text
from experiments.scripts.qualification_visual_pairs import dhash

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'research-data/iiit-cvid-source/IIIT-CVid.zip'
OUT = ROOT/'experiments/outputs/cvid-all-split-inventory-261014'
EXPECTED = 'b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_csv(name, rows):
    path = OUT/name
    with path.open('w', newline='', encoding='utf-8') as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return {'path':path.relative_to(ROOT).as_posix(), 'rows':len(rows), 'sha256':sha(path)}


def main():
    archive_sha = sha(SOURCE)
    if archive_sha != EXPECTED:
        raise ValueError('source archive identity differs')
    OUT.mkdir(parents=True, exist_ok=True)
    rows, issues, courses, splits, index_checks = [], [], [], {}, {}
    text_by_group, crop_text_by_group = defaultdict(Counter), defaultdict(Counter)
    pixel_groups, byte_groups, hashes = defaultdict(list), defaultdict(list), {}
    with zipfile.ZipFile(SOURCE) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate archive member names')
        members = set(names)
        for split in ('train','val','test'):
            prefix = f'IIIT-CVid/Frames/{split}/'
            images = sorted(n for n in names if n.startswith(prefix) and n.endswith('.png'))
            xmls = {n for n in names if n.startswith(prefix) and n.endswith('.xml')}
            crops = [n for n in names if n.startswith(f'IIIT-CVid/Crops/{split}/') and n.endswith('.png')]
            counts = Counter(frames=len(images), xmls=len(xmls), crop_pngs=len(crops))
            orphan_xml = xmls - {n[:-4]+'.xml' for n in images}
            counts['orphan_xmls'] = len(orphan_xml)
            for n in images:
                ident = n.removeprefix('IIIT-CVid/Frames/')
                _, course, video, _ = ident.split('/')
                raw = archive.read(n)
                with Image.open(io.BytesIO(raw)) as source:
                    image = source.convert('RGB'); image.load()
                width, height = image.size
                xml_name = n[:-4]+'.xml'
                if xml_name not in members:
                    raise ValueError(f'missing annotation: {ident}')
                xml_raw = archive.read(xml_name)
                xml = ET.fromstring(xml_raw)
                declared = [int(xml.findtext('size/'+key)) for key in ('width','height')]
                objects, invalid = xml.findall('object'), 0
                for i, obj in enumerate(objects):
                    text = obj.findtext('name') or ''
                    box = [int(obj.findtext('bndbox/'+key)) for key in ('xmin','ymin','xmax','ymax')]
                    a,b,c,d = box
                    reasons = []
                    if not normalize_text(text): reasons.append('blank_transcription')
                    if not (0 <= a < c <= width and 0 <= b < d <= height): reasons.append('outside_or_nonpositive_box')
                    if obj.findtext('difficult') != '0': reasons.append('unresolved_difficult_flag')
                    counts['boxes'] += 1
                    counts['nonblank_transcriptions'] += bool(normalize_text(text))
                    counts['invalid_boxes'] += 'outside_or_nonpositive_box' in reasons
                    counts['blank_transcriptions'] += 'blank_transcription' in reasons
                    counts['unresolved_difficult_flags'] += 'unresolved_difficult_flag' in reasons
                    text_by_group[(split,course,video)][normalize_text(text)] += 1
                    if reasons:
                        invalid += 1
                        issues.append(dict(frame_id=ident, object_index=i, box=box, reasons=';'.join(reasons)))
                mismatch = declared != [width,height]
                decision = 'HOLD' if invalid else 'REPAIR_METADATA_DERIVED' if mismatch else 'KEEP'
                counts[decision] += 1
                counts['xml_size_mismatches'] += mismatch
                counts['empty_frames'] += not objects
                counts['eligible_frames'] += not invalid
                counts['eligible_objects'] += len(objects) if not invalid else 0
                byte_hash = hashlib.sha256(raw).hexdigest()
                pixel_hash = hashlib.sha256(image.tobytes()).hexdigest()
                row = dict(frame_id=ident, split=split, course=course, source_group=course+'/'+video,
                           width=width, height=height, xml_width=declared[0], xml_height=declared[1],
                           objects=len(objects), invalid_objects=invalid, decision=decision,
                           image_sha256=byte_hash, xml_sha256=hashlib.sha256(xml_raw).hexdigest())
                rows.append(row)
                byte_groups[byte_hash].append(ident)
                pixel_groups[(width,height,pixel_hash)].append(ident)
                hashes[ident] = dhash(image)
                if len(rows)%1000 == 0: print('Decoded frames:',len(rows),flush=True)
            frame_list = f'IIIT-CVid/frames-{split}-img.txt'
            if frame_list in members:
                listed = archive.read(frame_list).decode('utf-8-sig').splitlines()
                expected = {n.removeprefix('IIIT-CVid/Frames/') for n in xmls}
                index_checks[split] = dict(frame_index_present=True, rows=len(listed),
                    duplicate_rows=len(listed)-len(set(listed)), missing=len(expected-set(listed)), extra=len(set(listed)-expected))
            else:
                index_checks[split] = dict(frame_index_present=False, derived_from_paired_png_xml=True)
            labels = archive.read(f'IIIT-CVid/{split}.txt').decode('utf-8-sig').splitlines()
            crop_paths = []
            for line in labels:
                path, text = line.split(maxsplit=1)
                path = str(Path(path).as_posix()).replace('//','/')
                crop_paths.append('IIIT-CVid/'+path)
                _, _, course, video, _ = path.split('/')
                crop_text_by_group[(split,course,video)][normalize_text(text)] += 1
            counts['crop_label_rows'] = len(labels)
            counts['crop_index_missing_images'] = len(set(crop_paths)-set(crops))
            counts['crop_images_missing_index'] = len(set(crops)-set(crop_paths))
            counts['duplicate_crop_index_paths'] = len(crop_paths)-len(set(crop_paths))
            splits[split] = dict(counts)
        for n in sorted(names):
            if n.startswith('IIIT-CVid/Frames/') and len(n.split('/'))==5 and n.endswith('/metadata.txt'):
                _,_,split,course,_ = n.split('/')
                data = dict(line.split(':',1) for line in archive.read(n).decode('utf-8-sig').splitlines() if ':' in line)
                courses.append(dict(split=split,course=course,**data))
        readme_sha = hashlib.sha256(archive.read('IIIT-CVid/Readme.txt')).hexdigest()
    overlaps = {}
    for left,right in itertools.combinations(splits,2):
        a,b = [r for r in rows if r['split']==left], [r for r in rows if r['split']==right]
        overlaps[left+'__'+right] = dict(
            course_ids=sorted({r['course'] for r in a}&{r['course'] for r in b}),
            source_group_ids=sorted({r['source_group'] for r in a}&{r['source_group'] for r in b}),
            declared_course_urls=sorted({r.get('VideoURL','').strip().rstrip('/') for r in courses if r['split']==left}&
                                       {r.get('VideoURL','').strip().rstrip('/') for r in courses if r['split']==right}))
    duplicates = [dict(kind=kind, frames=ids, cross_split=len({n.split('/')[0] for n in ids})>1)
                  for kind,groups in [('bytes',byte_groups),('decoded_rgb',pixel_groups)] for ids in groups.values() if len(ids)>1]
    pairs = [dict(left=a['frame_id'],right=b['frame_id'],distance=(hashes[a['frame_id']]^hashes[b['frame_id']]).bit_count())
             for i,a in enumerate(rows) for b in rows[i+1:] if a['split']!=b['split'] and
             (hashes[a['frame_id']]^hashes[b['frame_id']]).bit_count()<=6]
    mismatched_groups = []
    for k in sorted(text_by_group.keys()|crop_text_by_group.keys()):
        a, b = text_by_group[k], crop_text_by_group[k]
        if a != b:
            rewritten = Counter()
            for text, count in a.items(): rewritten[text.replace('/','-')] += count
            mismatched_groups.append(dict(split=k[0],course=k[1],video=k[2],xml_objects=sum(a.values()),
                crop_labels=sum(b.values()),unmatched_xml_observations=sum((a-b).values()),
                slash_to_hyphen_explains_group=rewritten==b))
    for split in splits:
        splits[split]['courses'] = sorted({r['course'] for r in rows if r['split']==split},key=int)
        splits[split]['source_groups'] = len({r['source_group'] for r in rows if r['split']==split})
        splits[split]['crop_xml_mismatched_label_groups'] = sum(g['split']==split for g in mismatched_groups)
        splits[split]['crop_xml_unmatched_observations'] = sum(g['unmatched_xml_observations'] for g in mismatched_groups if g['split']==split)
    artifacts = [write_csv('frames.csv',rows),write_csv('annotation-issues.csv',issues),write_csv('courses.csv',courses),
                 write_csv('cross-split-dhash-candidates.csv',pairs)]
    result = dict(schema='cvid_all_split_inventory_v1',observed_at_utc=datetime.now(timezone.utc).isoformat(),
        source_archive=str(SOURCE),source_archive_sha256=archive_sha,source_bytes=SOURCE.stat().st_size,
        readme_sha256=readme_sha,splits=splits,frame_index_checks=index_checks,cross_split_identifiers=overlaps,
        exact_duplicate_groups=duplicates,crop_xml_transcription_group_mismatches=mismatched_groups,
        perceptual_screen=dict(method='64bit grayscale dHash, Hamming<=6; candidates only, no exclusion',
            pairs=len(pairs),frames=len({p[k] for p in pairs for k in ('left','right')})),
        inference_executed=False,cohort_frozen=False,transcription_semantic_accuracy_verified=False,
        transcription_policy='XML object/name is spotting GT; crop indexes replace slash with hyphen; this audit never rewrites XML labels',
        script_sha256=sha(Path(__file__)),artifacts=artifacts)
    data = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (OUT/'inventory.json').write_text(data,encoding='utf-8')
    (ROOT/'experiments/registry/datasets/iiit-cvid-all-split-inventory-261014.json').write_text(data,encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('splits','perceptual_screen','inference_executed','cohort_frozen')},indent=2))


if __name__=='__main__':
    main()
