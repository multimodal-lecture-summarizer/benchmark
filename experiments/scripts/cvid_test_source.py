"""Re-read pinned native test pixels/XML; compare every object with executed EDA."""
from collections import Counter
import hashlib
import xml.etree.ElementTree as ET
import zipfile

from experiments.scripts.cvid_eda_common import decoded, pixel_key
from experiments.scripts.spotting_metrics import normalize_text


def require(condition, message):
    if not condition:
        raise ValueError(message)


def annotation_issues(text, coords, difficult, width, height):
    """Mechanical eligibility only; semantic opinions never enter this decision."""
    a, b, c, d = coords
    issues = []
    if not (0 <= a < c <= width and 0 <= b < d <= height):
        issues.append('outside_or_nonpositive_box')
    if not normalize_text(text):
        issues.append('blank_transcription')
    if difficult != '0':
        issues.append('unresolved_difficult_flag')
    return issues


def scan_test(archive_path, eda_frames, eda_objects):
    """Changed identity or unreadable source stops freeze, never shrinks the pool."""
    expected = eda_frames[eda_frames.split.eq('test')].set_index('frame_id').to_dict('index')
    object_rows = eda_objects[eda_objects.split.eq('test')].set_index('object_id').to_dict('index')
    require(len(expected) == 1755 and len(object_rows) == 40103, 'EDA test coverage changed')
    frames, gt, holds, observed_objects = [], [], [], set()
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate ZIP members')
        images = sorted(n for n in names if n.startswith('IIIT-CVid/Frames/test/') and n.endswith('.png'))
        xmls = {n for n in names if n.startswith('IIIT-CVid/Frames/test/') and n.endswith('.xml')}
        require(xmls == {n[:-4]+'.xml' for n in images}, 'test PNG/XML pairing changed')
        require({n.removeprefix('IIIT-CVid/Frames/') for n in images} == set(expected), 'EDA/source frame ID mismatch')
        for index, member in enumerate(images, 1):
            raw, xml_raw = archive.read(member), archive.read(member[:-4]+'.xml')
            image, xml = decoded(raw), ET.fromstring(xml_raw)
            width, height = image.size
            eda_id = member.removeprefix('IIIT-CVid/Frames/')
            frame_id = 'Frames/'+eda_id
            original = expected[eda_id]
            image_sha, xml_sha = (hashlib.sha256(v).hexdigest() for v in (raw, xml_raw))
            require(image_sha == original['image_sha256'] and xml_sha == original['xml_sha256'], 'source frame/XML hash mismatch: '+eda_id)
            require(pixel_key(image) == original['pixel_key'], 'decoded RGB mismatch: '+eda_id)
            require([width, height] == [original['width'], original['height']], 'decoded dimension mismatch')
            declared = [int(xml.findtext('size/'+k)) for k in ('width', 'height')]
            require(declared == [original['xml_width'], original['xml_height']], 'XML metadata changed')
            objects, issues = [], []
            for ordinal, obj in enumerate(xml.findall('object')):
                text, difficult = obj.findtext('name') or '', obj.findtext('difficult')
                coords = [int(obj.findtext('bndbox/'+k)) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
                object_id = f'{eda_id}#object-{ordinal:04d}'
                require(object_id in object_rows, 'unexpected XML object ID')
                observed_objects.add(object_id)
                prior = object_rows[object_id]
                require(text == prior['text'] and coords == [prior[k] for k in ('xmin','ymin','xmax','ymax')], 'EDA/XML text or geometry changed')
                require((difficult == '0') == prior['difficult_resolved'], 'EDA/XML difficult changed')
                reasons = annotation_issues(text, coords, difficult, width, height)
                objects.append(dict(object_id='Frames/'+object_id, eda_object_id=object_id,
                                    source_object_index=ordinal, bbox_xyxy=coords, text=text))
                if reasons:
                    issues.append(dict(object_id='Frames/'+object_id, bbox_xyxy=coords, text=text, reasons=reasons))
            decision = 'HOLD' if issues else 'REPAIR_METADATA_DERIVED' if declared != [width, height] else 'KEEP'
            require(decision == original['decision'] and len(objects) == original['objects'] and len(issues) == original['invalid_objects'], 'EDA/source decision changed')
            reasons = sorted({r for issue in issues for r in issue['reasons']}) if issues else [
                'decoded_png_dimensions_override_xml_only' if decision == 'REPAIR_METADATA_DERIVED' else 'all_released_objects_mechanically_valid']
            _, course, video, _ = eda_id.split('/')
            row = dict(frame_id=frame_id, eda_frame_id=eda_id, archive_image_member=member,
                       archive_xml_member=member[:-4]+'.xml', split='test', course=course,
                       source_group=course+'/'+video, width=width, height=height,
                       xml_declared_size=declared, image_sha256=image_sha, xml_sha256=xml_sha,
                       decoded_rgb_key=original['pixel_key'], object_count=len(objects),
                       decision=decision, selected=not issues, reasons=reasons, invalid_object_count=len(issues))
            frames.append(row)
            if issues:
                holds.append(dict(frame_id=frame_id, excluded_objects=len(objects), issues=issues))
            else:
                gt.append(dict(frame_id=frame_id, course=course, source_group=course+'/'+video,
                               width=width, height=height, objects=objects))
            if index % 500 == 0:
                print(f'Test frame/XML verified: {index}/{len(images)}', flush=True)
    require(observed_objects == set(object_rows), 'XML object coverage changed')
    require(Counter(f['decision'] for f in frames) == {'KEEP':1657,'REPAIR_METADATA_DERIVED':97,'HOLD':1}, 'test eligibility counts changed')
    require(len(gt) == 1754 and sum(len(r['objects']) for r in gt) == 40063, 'primary test denominator changed')
    return frames, gt, holds
