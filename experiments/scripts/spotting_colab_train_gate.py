"""Identical train-only warm-up and immutable runtime mismatch evidence."""
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid

from experiments.scripts.spotting_colab_state import require, sha, validate_record, write_once


def observe_train(rows, predictor, geometry_policy):
    """Replay inference, decoding and geometry checks in the same order in both phases."""
    require(rows and all(row['frame_id'].startswith('Frames/train/') for row in rows),
            'preflight/warm-up must use train only')
    observations = []
    for row in rows:
        require(sha(row['path']) == row['image_sha256'], 'train preflight input changed')
        start = time.perf_counter()
        predictions = predictor(Path(row['path']))
        record = dict(frame_id=row['frame_id'], status='ok', error=None, predictions=predictions)
        validate_record(record, row['frame_id'])
        # Image plugins and geometry libraries can be loaded lazily. These calls
        # must finish in both processes before hashing mapped native libraries.
        from PIL import Image
        from experiments.scripts.spotting_metrics import prediction_polygon
        with Image.open(row['path']) as image:
            width, height = image.size
        invalid = sum(prediction_polygon(p.get('polygon'), width, height) is None for p in predictions)
        if geometry_policy != 'retain_and_report_native_invalid_predictions':
            require(invalid == 0, 'preflight produced invalid geometry')
        observations.append(dict(frame_id=row['frame_id'], image_sha256=row['image_sha256'],
                                 predictions=predictions, invalid_predictions=invalid,
                                 wall_seconds=time.perf_counter() - start))
    require(any(len(row['predictions']) > row['invalid_predictions'] for row in observations),
            'preflight must demonstrate nonempty box + text output')
    return observations


def difference(expected, actual, path=''):
    """Keep added, removed and changed fields, including native library paths/hashes."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        rows = []
        for key in sorted(set(expected) | set(actual)):
            child = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in expected:
                rows.append(dict(path=child, change='added', actual=actual[key]))
            elif key not in actual:
                rows.append(dict(path=child, change='removed', expected=expected[key]))
            else:
                rows.extend(difference(expected[key], actual[key], child))
        return rows
    return [] if expected == actual else [dict(path=path, change='changed', expected=expected, actual=actual)]


def require_matching_runtime(target, phase, gate, binding, runtime, message):
    if gate.get('status') == 'passed' and gate['binding'] == binding:
        return
    changes = difference(gate.get('runtime', {}), runtime)
    evidence = dict(schema='cvid_runtime_mismatch_v1', phase=phase,
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    expected_status=gate.get('status'), expected_binding=gate['binding'],
                    actual_binding=binding, expected_runtime=gate.get('runtime', {}),
                    actual_runtime=runtime, binding_diff=difference(gate['binding'], binding),
                    runtime_diff=changes, test_inference_started=False)
    path = Path(target)/'diagnostics'/('runtime-mismatch-'+phase+'-'+uuid.uuid4().hex+'.json')
    write_once(path, evidence)
    print('Runtime mismatch evidence: '+str(path), flush=True)
    print('Changed runtime fields: '+', '.join(row['path'] for row in changes[:20]), flush=True)
    require(False, message+'; inspect '+str(path))
