"""Post-analysis full-text GT/prediction review for any frozen test frame."""
import hashlib
import json
import math
from pathlib import Path

from experiments.scripts.spotting_colab_data import GT, verify_bundle
from experiments.scripts.spotting_colab_review import table, verified_exports
from experiments.scripts.spotting_colab_state import checkpoint_path, digest, read, require, validate_record


def review_record(output, candidate_id, frame, completion):
    item = read(checkpoint_path(output,candidate_id,frame['frame_id']))
    require(item['binding']==completion['binding'] and item['image_sha256']==frame['image_sha256'], 'review checkpoint identity changed')
    require(item['record_sha256']==digest(item['record']), 'review checkpoint altered')
    validate_record(item['record'],frame['frame_id'])
    return item['record']


def inspect_frame(output, bundle_root, work, frame_id):
    from PIL import Image, ImageDraw
    from IPython.display import display
    root = Path(output)
    summary = verified_exports(root)
    data = read(root/'prepared-data.json')
    require(verify_bundle(bundle_root)==data['bundle_sha256'], 'review bundle/GT changed')
    frames = {r['frame_id']:r for r in data['frames']}
    require(frame_id in frames, 'choose a frame ID from the frozen cohort')
    frame = frames[frame_id]
    path = Path(work)/'inputs'/frame_id
    require(hashlib.sha256(path.read_bytes()).hexdigest()==frame['image_sha256'], 'review pixels changed')
    gt = next(json.loads(line) for line in (Path(bundle_root)/GT).read_text(encoding='utf-8').splitlines()
              if json.loads(line)['frame_id']==frame_id)
    original = Image.open(path).convert('RGB')
    print(frame_id,'—',len(gt['objects']),'released GT; GREEN=GT, BLUE=prediction. Colors do not denote TP/FP matches.')
    table([dict(object_id=r['object_id'],text=r['text'],bbox=r['bbox_xyxy']) for r in gt['objects']], 'All released GT text / boxes')
    # Verify/view original native records, not reconstructed or grouped OCR text.
    for cid in summary['candidate_order']:
        complete = read(root/cid/'candidate-complete.json')
        require(hashlib.sha256((root/cid/'candidate-complete.json').read_bytes()).hexdigest()==summary['binding']['candidates'][cid]['completion_sha256'],
                'review completion no longer matches analysis')
        record = review_record(root,cid,frame,complete)
        overlay = original.copy()
        draw = ImageDraw.Draw(overlay)
        for obj in gt['objects']:
            draw.rectangle(obj['bbox_xyxy'],outline='#00b050',width=2)
        rows = []
        for index,pred in enumerate(record['predictions'],1):
            polygon = pred.get('polygon')
            drawable = isinstance(polygon,list) and len(polygon)>=3 and all(isinstance(p,list) and len(p)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) for p in polygon)
            if drawable:
                xy = [tuple(p) for p in polygon]
                draw.line(xy+[xy[0]],fill='#008bff',width=3)
                draw.text(xy[0],str(index),fill='red',stroke_width=1,stroke_fill='white')
            rows.append(dict(region=index,text=pred['text'],polygon=json.dumps(polygon),
                             native_confidence=pred.get('recognition_confidence','not supplied'),overlay='drawn; geometry validity not inferred' if drawable else 'not drawable; retained'))
        print(cid,'status=',record['status'],'error=',record.get('error'),'regions=',len(rows))
        overlay.thumbnail((1200,1000))
        display(overlay)
        table(rows,cid+' — all native predictions, no text truncation')
    print('Viewer is descriptive: selective labels mean unmatched visible text may be unannotated; do not tune/filter test outputs.')
