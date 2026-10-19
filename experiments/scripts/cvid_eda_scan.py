"""Full frame/object/crop decode and multiplicity-aware correspondence; no OCR."""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import importlib.metadata
from pathlib import Path
import platform
import time
import xml.etree.ElementTree as ET
import zipfile

from experiments.scripts.cvid_eda_common import (
    EXPECTED, OUT, ROOT, SOURCE, SEMANTIC_SAMPLE_RULE, decoded, features, normalize_text,
    pixel_key, sha, write_csv, write_json,
)
from experiments.scripts.qualification_visual_pairs import dhash


def course_metadata(archive, names):
    result = []
    for name in sorted(names):
        if name.startswith('IIIT-CVid/Frames/') and name.endswith('/metadata.txt') and len(name.split('/'))==5:
            _,_,split,course,_ = name.split('/')
            values = dict(line.split(':',1) for line in archive.read(name).decode('utf-8-sig').splitlines() if ':' in line)
            result.append(dict(split=split,course=course,**{k:v.strip() for k,v in values.items()}))
    return result


def scan():
    started = time.perf_counter()
    source_sha = sha(SOURCE)
    if source_sha != EXPECTED: raise ValueError('source hash mismatch')
    write_json('semantic-sample-rule.json',SEMANTIC_SAMPLE_RULE)
    frames, objects, crops, failures = [], [], [], []
    source_buckets = defaultdict(list)
    with zipfile.ZipFile(SOURCE) as archive:
        names = archive.namelist()
        if len(names)!=len(set(names)): raise ValueError('duplicate ZIP member paths')
        members = set(names)
        courses = course_metadata(archive,names)
        image_names = sorted(n for n in names if n.startswith('IIIT-CVid/Frames/') and n.endswith('.png'))
        xml_names = {n for n in names if n.startswith('IIIT-CVid/Frames/') and n.endswith('.xml')}
        if xml_names!={n[:-4]+'.xml' for n in image_names}: raise ValueError('frame/XML pairing differs')
        for index,name in enumerate(image_names,1):
            raw, xml_raw = archive.read(name), archive.read(name[:-4]+'.xml')
            image = decoded(raw)
            xml = ET.fromstring(xml_raw)
            _,_,split,course,video,filename = name.split('/')
            frame_id = '/'.join((split,course,video,filename))
            group = '/'.join((split,course,video))
            width,height = image.size
            declared = [int(xml.findtext('size/'+key)) for key in ('width','height')]
            frame_objects = []
            for ordinal,obj in enumerate(xml.findall('object')):
                text = obj.findtext('name') or ''
                norm = normalize_text(text)
                a,b,c,d = [int(obj.findtext('bndbox/'+key)) for key in ('xmin','ymin','xmax','ymax')]
                geometry_ok = 0<=a<c<=width and 0<=b<d<=height
                difficult_ok = obj.findtext('difficult')=='0'
                # Out-of-frame patches use PIL padding only for comparison to supplied crops;
                # source geometry remains invalid and is never clipped/repaired.
                patch = image.crop((a,b,c,d)) if a<c and b<d else None
                key = pixel_key(patch) if patch else ''
                item = dict(object_id=f'{frame_id}#object-{ordinal:04d}',frame_id=frame_id,split=split,course=course,
                    source_group=course+'/'+video,object_index=ordinal,text=text,normalized_text=norm,
                    xmin=a,ymin=b,xmax=c,ymax=d,box_width=c-a,box_height=d-b,box_height_rel=(d-b)/height,
                    area_rel=(c-a)*(d-b)/(width*height),aspect_ratio=(c-a)/(d-b) if d>b else 0,
                    characters=len(norm),one_character=len(norm)==1,has_digit=any(ch.isdigit() for ch in text),
                    has_punctuation=any(not ch.isalnum() and not ch.isspace() for ch in text),
                    slash_in_xml='/' in text,normalization_changed=text!=norm,geometry_valid=geometry_ok,
                    transcription_nonblank=bool(norm),difficult_resolved=difficult_ok,pixel_key=key,
                    gray_std=features(patch)['gray_std'] if patch else 0)
                objects.append(item); frame_objects.append(item)
                source_buckets[(group,key,norm.replace('/','-'))].append(item)
            invalid = sum(not (o['geometry_valid'] and o['transcription_nonblank'] and o['difficult_resolved']) for o in frame_objects)
            mismatch = declared!=[width,height]
            decision = 'HOLD' if invalid else 'REPAIR_METADATA_DERIVED' if mismatch else 'KEEP'
            frames.append(dict(frame_id=frame_id,split=split,course=course,source_group=course+'/'+video,
                archive_member=name,objects=len(frame_objects),invalid_objects=invalid,decision=decision,
                xml_width=declared[0],xml_height=declared[1],xml_size_mismatch=mismatch,
                image_sha256=hashlib.sha256(raw).hexdigest(),xml_sha256=hashlib.sha256(xml_raw).hexdigest(),
                pixel_key=pixel_key(image),dhash=f'{dhash(image):016x}',
                transcription=' | '.join(o['text'] for o in frame_objects),**features(image)))
            if index%1000==0: print('Frames decoded:',index,flush=True)
        original_sizes = {key:len(value) for key,value in source_buckets.items()}
        unmatched = {key:deque(value) for key,value in source_buckets.items()}
        indexed = set()
        for split in ('train','val','test'):
            for line in archive.read(f'IIIT-CVid/{split}.txt').decode('utf-8-sig').splitlines():
                parts = line.split(maxsplit=1)
                if len(parts)!=2: raise ValueError('crop label row missing transcription')
                path,text = parts
                path = path.replace('//','/')
                name = 'IIIT-CVid/'+path
                if name in indexed or name not in members: raise ValueError('crop index duplicated/missing path')
                indexed.add(name)
                _,_,course,video,_ = path.split('/')
                group = '/'.join((split,course,video))
                try:
                    raw = archive.read(name); crop = decoded(raw); key = pixel_key(crop)
                    bucket_key = (group,key,normalize_text(text))
                    bucket = unmatched.get(bucket_key)
                    matched = bucket.popleft() if bucket else None
                    equivalence_size = original_sizes.get(bucket_key,0)
                    crops.append(dict(crop_id=path,split=split,course=course,source_group=course+'/'+video,
                        text=text,normalized_text=normalize_text(text),characters=len(normalize_text(text)),
                        image_sha256=hashlib.sha256(raw).hexdigest(),pixel_key=key,
                        correspondence='unique' if equivalence_size==1 and matched else 'equivalent_ambiguous' if matched else 'unmatched',
                        equivalence_class_size=equivalence_size,
                        assigned_object_id=matched['object_id'] if matched else '',
                        assignment_rule='deterministic equivalence allocation; not author object-ID proof',
                        xml_text=matched['text'] if matched else '',
                        raw_label_differs=matched['text']!=text if matched else None,**features(crop)))
                except Exception as exc:
                    failures.append(dict(kind='crop_decode',id=path,error=f'{type(exc).__name__}: {exc}'))
            print('Crops decoded:',len(crops),'after',split,flush=True)
        source_crop_names = {n for n in names if n.startswith('IIIT-CVid/Crops/') and n.endswith('.png')}
        if indexed!=source_crop_names: raise ValueError('crop index/source coverage mismatch')
        unmatched_objects = [dict(object_id=o['object_id'],reason='no corresponding crop allocation')
                             for bucket in unmatched.values() for o in bucket]
    artifacts = [write_csv('frames.csv.gz',frames),write_csv('objects.csv.gz',objects),write_csv('crops.csv.gz',crops),
                 write_csv('courses.csv',courses),write_csv('read-failures.csv',failures),
                 write_csv('unmatched-objects.csv',unmatched_objects)]
    result = dict(schema='cvid_all_split_eda_scan_v1',observed_at_utc=datetime.now(timezone.utc).isoformat(),
        source_archive_sha256=source_sha,frames=len(frames),objects=len(objects),decoded_crops=len(crops),
        indexed_crops=len(indexed),read_failures=len(failures),unmatched_objects=len(unmatched_objects),
        crop_correspondence=dict(Counter(c['correspondence'] for c in crops)),
        raw_crop_xml_label_differences=sum(c['raw_label_differs'] is True for c in crops),
        wall_seconds=time.perf_counter()-started,
        runtime=dict(python=platform.python_version(),packages={p:importlib.metadata.version(p) for p in ['numpy','pandas','Pillow']}),
        artifacts=artifacts,inference_executed=False,cohort_frozen=False,
        scripts={name:sha(Path(__file__).with_name(name)) for name in ('cvid_eda_scan.py','cvid_eda_common.py')})
    write_json('scan-receipt.json',result)
    return result


if __name__=='__main__':
    import json
    print(json.dumps(scan(),indent=2))
