"""Export/scoring accounting on small explicit oracle cases, never run evidence."""
import csv
import gzip
import io
import json

from experiments.scripts import spotting_comparison_analysis as analysis


def source_cases():
    gt = analysis.read_lines(analysis.GT)[:3]
    records = []
    for frame in gt:
        predictions = []
        for obj in frame['objects']:
            x0, y0, x1, y1 = obj['bbox_xyxy']
            predictions.append(dict(text=obj['text'].upper(), polygon=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]))
        records.append(dict(frame_id=frame['frame_id'], status='ok', error=None, predictions=predictions,
                            wall_seconds=.25, origin='test_oracle'))
    return gt, records


def test_export_variant_failure_denominators_and_case_sensitivity():
    gt, records = source_cases()
    records[1].update(status='error', error='test_explicit_failure', predictions=[])
    total = sum(len(f['objects']) for f in gt)
    excluded = [gt[-1]['frame_id']]
    variants = [dict(id=name, iou_threshold=threshold, case_sensitive=case,
                     frames=2 if name == 'observed_flag_frame_influence' else 3,
                     objects=total-len(gt[-1]['objects']) if name == 'observed_flag_frame_influence' else total)
                for name, threshold, case in (('primary',.5,False), ('iou_075',.75,False),
                    ('case_sensitive',.5,True), ('observed_flag_frame_influence',.5,False))]
    scores = dict(analysis.score_variants(gt, records, variants, excluded))
    assert scores['primary']['overall']['detection']['recall'] < 1
    assert scores['primary']['overall']['spotting'] == scores['iou_075']['overall']['spotting']
    assert scores['case_sensitive']['overall']['spotting']['tp'] < scores['primary']['overall']['spotting']['tp']
    assert scores['primary']['failed_frames'] == scores['observed_flag_frame_influence']['failed_frames'] == 1
    refs = {f['frame_id']: f for f in gt}; raw = {r['frame_id']: r for r in records}
    rows = analysis.enriched_rows(scores['primary'], raw, refs)
    exports = analysis.summarize(rows, 'primary', 'explicit_oracle')
    for row in exports:
        assert row['gt_objects'] == total
        assert row['tp']+row['fn'] == total
        assert row['tp']+row['fp'] == row['predicted_objects']
        assert row['successful_frames']+row['failed_frames'] == 3
    failure = next(r for r in rows if r['status'] == 'error')
    assert failure['spotting']['fn'] == len(gt[1]['objects']) and failure['predictions_count'] == 0


def test_full_text_csv_preserves_literal_strings_ids_and_newlines():
    gt, records = source_cases()
    literal = 'NA, * \\" full\ntext K'
    gt[0]['objects'][0]['text'] = literal
    records[0]['predictions'][0]['text'] = literal
    frames = [dict(frame_id=f['frame_id']) for f in gt]
    refs = {f['frame_id']: f for f in gt}; raw = {r['frame_id']: r for r in records}
    rows = analysis.full_text_rows(frames, refs, dict(a=raw,b=raw), ['a','b'])
    data = analysis.csv_bytes(rows, tuple(rows[0]), compressed=True)
    assert data == analysis.csv_bytes(rows, tuple(rows[0]), compressed=True)
    decoded = list(csv.DictReader(io.StringIO(gzip.decompress(data).decode('utf-8'))))
    assert len(decoded) == len(gt)
    assert json.loads(decoded[0]['gt_texts'])[0] == literal
    assert json.loads(decoded[0]['easyocr_texts'])[0] == literal
    assert json.loads(decoded[0]['gt_object_ids'])[0] == gt[0]['objects'][0]['object_id']
    assert [r['frame_id'] for r in decoded] == [f['frame_id'] for f in gt]


def test_zero_failure_csv_retains_complete_schema():
    fields = ('candidate_id','frame_id','error')
    assert analysis.csv_bytes([],fields).decode() == 'candidate_id,frame_id,error\n'
