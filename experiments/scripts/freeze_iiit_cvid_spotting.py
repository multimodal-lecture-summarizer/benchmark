"""Freeze released validation spotting units; preserve source labels/geometry."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import platform
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
from experiments.scripts.spotting_metrics import normalize_text

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SHA = 'b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489'
NAME = 'iiit-cvid-spotting-validation-261013'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def frozen_write(path, data):
    """A changed frozen artifact requires a new version, not an overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'frozen artifact differs; use a new version: {path}')
    else:
        path.write_bytes(data)
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(data), bytes=len(data))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def pixel_key(image):
    rgb = image.convert('RGB')
    return (rgb.size, digest(rgb.tobytes()))


def build(archive_path):
    assert file_sha(archive_path) == EXPECTED_SHA, 'source archive identity mismatch'
    frames, ground_truth, holds = [], [], []
    coordinate_checks, special = Counter(), Counter()
    with zipfile.ZipFile(archive_path) as z:
        names = z.namelist()
        assert len(names) == len(set(names)), 'duplicate ZIP members'
        images = sorted(n for n in names if n.startswith('IIIT-CVid/Frames/val/') and n.endswith('.png'))
        xmls = {n for n in names if n.startswith('IIIT-CVid/Frames/val/') and n.endswith('.xml')}
        assert len(images)==549 and xmls=={n[:-4]+'.xml' for n in images}
        crop_members = defaultdict(list)
        for n in names:
            if n.startswith('IIIT-CVid/Crops/val/') and n.endswith('.png'):
                crop_members['/'.join(n.split('/')[3:5])].append(n)
        current_group, crop_keys = None, None
        for name in images:
            raw, xml_raw = z.read(name), z.read(name[:-4]+'.xml')
            with Image.open(io.BytesIO(raw)) as source:
                image = source.convert('RGB'); image.load()
            width, height = image.size
            xml = ET.fromstring(xml_raw)
            ident = name.removeprefix('IIIT-CVid/')
            _, split, course, video, _ = ident.split('/')
            group = course+'/'+video
            if current_group != group:
                crop_keys = Counter()
                for n in crop_members[group]:
                    with Image.open(io.BytesIO(z.read(n))) as crop:
                        crop_keys[pixel_key(crop)] += 1
                current_group = group
            declared = [int(xml.findtext('size/'+k)) for k in ('width','height')]
            objects, issues = [], []
            for ordinal, obj in enumerate(xml.findall('object')):
                text = obj.findtext('name') or ''
                coords = [int(obj.findtext('bndbox/'+k)) for k in ('xmin','ymin','xmax','ymax')]
                a,b,c,d = coords
                reasons = []
                if not normalize_text(text): reasons.append('blank_transcription')
                if not (0<=a<c<=width and 0<=b<d<=height): reasons.append('outside_or_nonpositive_box')
                if obj.findtext('difficult') != '0': reasons.append('unresolved_difficult_flag')
                objects.append(dict(object_id=f'{ident}#object-{ordinal:04d}', source_object_index=ordinal, bbox_xyxy=coords, text=text))
                if reasons: issues.append(dict(object_index=ordinal, bbox_xyxy=coords, text=text, reasons=reasons))
                if c>a and d>b:
                    coordinate_checks['objects'] += 1
                    for label, bounds in [('raw_half_open',(a,b,c,d)),('voc_one_based_inclusive',(a-1,b-1,c,d)),('zero_based_inclusive',(a,b,c+1,d+1))]:
                        coordinate_checks[label] += pixel_key(image.crop(bounds)) in crop_keys
                if len(normalize_text(text))==1: special['one_character_objects'] += 1
                if text=='*': special['literal_asterisk_objects'] += 1
                if any(ch.isspace() for ch in text): special['whitespace_in_label'] += 1
            decision = 'HOLD' if issues else 'REPAIR_METADATA_DERIVED' if declared!=[width,height] else 'KEEP'
            frame = dict(frame_id=ident, archive_image_member=name, archive_xml_member=name[:-4]+'.xml',
                         split=split, course=course, source_group=group, width=width, height=height,
                         xml_declared_size=declared, image_sha256=digest(raw), xml_sha256=digest(xml_raw),
                         object_count=len(objects), decision=decision, invalid_object_count=len(issues))
            frames.append(frame)
            if issues:
                holds.append(dict(frame_id=ident, issues=issues, excluded_objects=len(objects)))
            else:
                ground_truth.append(dict(frame_id=ident, course=course, source_group=group,
                                         width=width,height=height,objects=objects))
    counts = Counter(f['decision'] for f in frames)
    assert counts=={'KEEP':543,'REPAIR_METADATA_DERIVED':3,'HOLD':3}, counts
    selected_hashes = Counter(f['image_sha256'] for f in frames if f['decision']!='HOLD')
    return frames, ground_truth, holds, dict(coordinate_checks), dict(special), sum(n-1 for n in selected_hashes.values() if n>1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'research-data/iiit-cvid-source/IIIT-CVid.zip')
    args=parser.parse_args()
    frames, gt, holds, coordinates, special, duplicate_images = build(args.archive)
    derived=ROOT/'experiments/outputs'/NAME
    registry=ROOT/'experiments/registry/datasets'
    artifacts=[frozen_write(derived/'ground-truth.jsonl',b''.join((json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n').encode() for r in gt)),
               frozen_write(derived/'annotation-holds.json',json_bytes(holds))]
    manifest=dict(schema='iiit_cvid_spotting_cohort_v1',source_zip_sha256=EXPECTED_SHA,
                  selected_split='val',selected_frames=len(gt),selected_objects=sum(len(f['objects']) for f in gt),
                  source_frames=len(frames),source_objects=sum(f['object_count'] for f in frames),
                  courses=sorted({f['course'] for f in gt}),source_groups=sorted({f['source_group'] for f in gt}),
                  exact_duplicate_selected_images=duplicate_images,frames=frames,derived_artifacts=artifacts)
    artifacts.append(frozen_write(registry/(NAME+'-cohort.json'),json_bytes(manifest)))
    protocol=registry/(NAME+'-protocol.json')
    assert protocol.exists(), 'protocol must be predeclared before freezing'
    artifacts.append(dict(path=protocol.relative_to(ROOT).as_posix(),sha256=file_sha(protocol),bytes=protocol.stat().st_size))
    receipt=dict(schema='iiit_cvid_spotting_freeze_v1',date='2026-10-14',cohort_frozen=True,
                 supersedes_receipt=(NAME+'-freeze.json'),
                 superseded_receipt_sha256=file_sha(registry/(NAME+'-freeze.json')),
                 implementation_note='Verified implementation handles overflowing invalid coordinates as FP; data and metric protocol unchanged',
                 spotting_inference_executed=False,claim='descriptive released exposed validation only',
                 artifacts=artifacts,coordinate_crop_checks=coordinates,source_label_inventory=special,
                 python=platform.python_version(),unicode_version=unicodedata.unidata_version,
                 implementation_sha256={n:file_sha(Path(__file__).with_name(n)) for n in ('freeze_iiit_cvid_spotting.py','spotting_metrics.py')})
    frozen_write(registry/(NAME+'-freeze-verified-261014.json'),json_bytes(receipt))
    print(json.dumps({k:v for k,v in manifest.items() if k!='frames'},indent=2))
    print('Coordinate pixel checks:',coordinates,'Special labels:',special)


if __name__=='__main__':
    main()
