"""Study-specific one-to-one spotting metrics; not the official ICDAR scorer."""
import math
import unicodedata

from shapely.geometry import Polygon, box


def normalize_text(text, case_sensitive=False):
    if not isinstance(text, str):
        raise ValueError('transcription must be a string')
    text = unicodedata.normalize('NFKC', text)
    return ' '.join((text if case_sensitive else text.casefold()).split())


def maximum_matching(adjacency):
    """Augmenting paths maximize cardinality; sorted edges make ties deterministic."""
    owners = {}

    def augment(left, visited):
        for right in adjacency[left]:
            if right in visited:
                continue
            visited.add(right)
            if right not in owners or augment(owners[right], visited):
                owners[right] = left
                return True
        return False

    for left in range(len(adjacency)):
        augment(left, set())
    return sorted((left, right) for right, left in owners.items())


def prediction_polygon(points, width, height):
    """Invalid geometry is an FP, never silently clipped or repaired."""
    try:
        if not isinstance(points, list) or len(points) < 3:
            return None
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                return None
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
                return None
            if not (0 <= point[0] <= width and 0 <= point[1] <= height):
                return None
        shape = Polygon(points)
        return shape if shape.is_valid and shape.area > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def count_metrics(tp, predicted, reference):
    return dict(tp=tp, fp=predicted-tp, fn=reference-tp,
                precision=tp/predicted if predicted else 0.0,
                recall=tp/reference if reference else 0.0,
                hmean=2*tp/(predicted+reference) if predicted+reference else 0.0)


def score_frame(gt, record, iou_threshold=0.5, case_sensitive=False):
    """An error frame has no retained partial predictions and all GT are FN."""
    if record['frame_id'] != gt['frame_id']:
        raise ValueError('frame ID mismatch')
    if record.get('status') not in ('ok', 'error') or not isinstance(record.get('predictions'), list):
        raise ValueError('invalid frame prediction schema')
    if record['status'] == 'error' and (record['predictions'] or not isinstance(record.get('error'), str) or not record['error'].strip()):
        raise ValueError('error frame needs a reason and no partial predictions')
    if record['status'] == 'ok' and record.get('error') is not None:
        raise ValueError('successful frame cannot carry an error')
    predictions = record['predictions']
    for pred in predictions:
        if not isinstance(pred, dict) or not isinstance(pred.get('text'), str):
            raise ValueError('each prediction needs text; use empty string for recognition failure')
    # Canonical order removes sensitivity to engine output order for valid schema.
    predictions = sorted(predictions, key=lambda p: (str(p.get('polygon')), p['text']))
    polygons = [prediction_polygon(p.get('polygon'), gt['width'], gt['height']) for p in predictions]
    geometric, textual = [], []
    for obj in sorted(gt['objects'], key=lambda o: o['object_id']):
        target = box(*obj['bbox_xyxy'])
        edges = []
        for j, poly in enumerate(polygons):
            if poly is None:
                continue
            intersection = target.intersection(poly).area
            iou = intersection/(target.area+poly.area-intersection)
            if iou > iou_threshold:
                edges.append((j, iou))
        edges.sort(key=lambda e: (-e[1], e[0]))
        geometric.append([j for j, _ in edges])
        textual.append([j for j, _ in edges if normalize_text(obj['text'], case_sensitive)==normalize_text(predictions[j]['text'], case_sensitive)])
    n_gt, n_pred = len(gt['objects']), len(predictions)
    return dict(frame_id=gt['frame_id'], source_group=gt['source_group'], course=gt['course'],
                status=record['status'], error=record.get('error'),
                invalid_predictions=sum(p is None for p in polygons),
                empty_transcriptions=sum(not normalize_text(p['text']) for p in predictions),
                detection=count_metrics(len(maximum_matching(geometric)), n_pred, n_gt),
                spotting=count_metrics(len(maximum_matching(textual)), n_pred, n_gt))


def score_cohort(ground_truth, records, **kwargs):
    """Missing IDs count as unavailable; duplicates and extra IDs reject the run."""
    refs = {r['frame_id']: r for r in ground_truth}
    predictions = {r['frame_id']: r for r in records}
    if len(refs) != len(ground_truth) or len(predictions) != len(records):
        raise ValueError('duplicate frame ID')
    if predictions.keys()-refs.keys():
        raise ValueError('extra frame IDs outside frozen cohort')
    rows = []
    for ident in sorted(refs):
        record = predictions.get(ident, dict(frame_id=ident, status='error', error='missing_record', predictions=[]))
        rows.append(score_frame(refs[ident], record, **kwargs))
    overall = {}
    for metric in ('detection', 'spotting'):
        tp, fp, fn = (sum(r[metric][k] for r in rows) for k in ('tp', 'fp', 'fn'))
        overall[metric] = count_metrics(tp, tp+fp, tp+fn)
    return dict(selected_frames=len(rows), successful_frames=sum(r['status']=='ok' for r in rows),
                failed_frames=sum(r['status']=='error' for r in rows),
                failure_ledger=[dict(frame_id=r['frame_id'], error=r['error']) for r in rows if r['status']=='error'],
                overall=overall, frames=rows)
