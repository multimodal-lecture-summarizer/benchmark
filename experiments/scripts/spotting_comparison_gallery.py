"""Original-pixel GT/A/B diagnostic overlays with explicit selection ledgers."""
import json
import io
import math
from pathlib import Path

from IPython.display import Image as NotebookImage, Markdown, display
from PIL import Image, ImageDraw

from experiments.scripts.spotting_candidate_contract import ROOT, sha
from experiments.scripts.spotting_comparison_io_v2 import write_bytes_once, write_once
from experiments.scripts.spotting_runtime_binding import read_json, require

CANDIDATES=('easyocr_craft_english_g2','paddle_db_v3_rec_v4_keep_all')


def _jsonl(path):
    return {row['frame_id']:row for row in map(json.loads,path.read_text(encoding='utf-8').splitlines())}


def _panel(source, objects, label, ground_truth=False):
    image=source.copy().convert('RGB');draw=ImageDraw.Draw(image)
    for index, obj in enumerate(objects):
        points = ([(obj['bbox_xyxy'][0],obj['bbox_xyxy'][1]),
                   (obj['bbox_xyxy'][2],obj['bbox_xyxy'][1]),
                   (obj['bbox_xyxy'][2],obj['bbox_xyxy'][3]),
                   (obj['bbox_xyxy'][0],obj['bbox_xyxy'][3])] if ground_truth else obj.get('polygon'))
        if not isinstance(points,list) or len(points)<3:
            continue
        valid=all(isinstance(p,(list,tuple)) and len(p)==2 and
                  all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) for p in points)
        if not valid: continue
        color='#16864b' if ground_truth else '#d47813'
        draw.line([tuple(p) for p in points]+[tuple(points[0])],fill=color,width=max(1,source.width//600))
        # Indices refer to the complete escaped text table below, avoiding glyph loss.
        draw.text(tuple(points[0]),str(index),fill=color)
    scale=min(1000/image.width,700/image.height)
    size=(max(1,round(image.width*scale)),max(1,round(image.height*scale)))
    image=image.resize(size,Image.Resampling.NEAREST if scale>1 else Image.Resampling.LANCZOS)
    panel=Image.new('RGB',(1000,730),'white')
    panel.paste(image,((1000-image.width)//2,30))
    ImageDraw.Draw(panel).text((10,8),label,fill='black')
    return panel


def render_galleries(data, output):
    output=Path(output);plan=read_json(output/'gallery-plan.json')
    truth=_jsonl(ROOT/'experiments/outputs/iiit-cvid-spotting-test-261014/ground-truth.jsonl')
    records={cid:_jsonl(output/cid/'predictions.jsonl') for cid in CANDIDATES}
    manifest={r['frame_id']:r for r in read_json(output/'input-manifest.json')}
    primary=data['frame_scores'].query('variant == "primary"')
    pairs=primary.pivot(index='frame_id',columns='candidate_id',values='spotting_hmean')
    diagnostic=sorted(pairs.index,key=lambda ident:(-abs(float(pairs.loc[ident,CANDIDATES[1]])-
                    float(pairs.loc[ident,CANDIDATES[0]])),ident))[:6]
    chosen=list(dict.fromkeys(plan['frame_ids']+diagnostic))
    folder=output/'galleries';folder.mkdir(parents=True,exist_ok=True)
    artifacts=[];decisions=[]
    from experiments.scripts.spotting_comparison_notebook import table
    for ordinal,ident in enumerate(chosen):
        frame=manifest[ident];path=output/frame['input_relative_path']
        require(sha(path)==frame['image_sha256'],'gallery input differs from inference pixels')
        with Image.open(path) as original:
            original.load()
            panels=[_panel(original,truth[ident]['objects'],'Released GT (green); object ordinals',True)]
            for cid,label in zip(CANDIDATES,('A EasyOCR','B PaddleOCR')):
                rec=records[cid][ident]
                panels.append(_panel(original,rec['predictions'],label+' (orange); '+rec['status']))
        canvas=Image.new('RGB',(3000,730),'white')
        for index,panel in enumerate(panels): canvas.paste(panel,(index*1000,0))
        target=folder/(f'{ordinal:02d}-'+ident.replace('/','--').removesuffix('.png')+'.jpg')
        stream=io.BytesIO();canvas.save(stream,format='JPEG',quality=92,subsampling=0)
        write_bytes_once(target,stream.getvalue())
        reasons=[]
        if ident in plan['frame_ids']: reasons.append('predeclared geometry/semantic-flag gallery')
        if ident in diagnostic: reasons.append('post-outcome top-six absolute frame Hmean difference; diagnostic only')
        decision=dict(frame_id=ident,selection_reasons=reasons,input_sha256=frame['image_sha256'],
                      a_frame_hmean=float(pairs.loc[ident,CANDIDATES[0]]),
                      b_frame_hmean=float(pairs.loc[ident,CANDIDATES[1]]))
        decisions.append(decision)
        display(Markdown('**'+ident+'** — '+'; '.join(reasons)))
        display(NotebookImage(filename=str(target)))
        table(data['all_frame_text'][data['all_frame_text'].frame_id.eq(ident)],f'gallery-{ordinal:02d}-full-text')
        artifacts.append(dict(path=target.relative_to(ROOT).as_posix(),sha256=sha(target),bytes=target.stat().st_size))
    result=dict(schema='iiit_cvid_spotting_gallery_v1',predeclared_frames=len(plan['frame_ids']),
        gallery_count=len(chosen),diagnostic_frames=diagnostic,decisions=decisions,artifacts=artifacts,
        color_semantics='GT green; native prediction orange; colors do not encode matches or correctness',
        display_scaling='Panel-only resize: nearest-neighbor enlargement or Lanczos reduction. Native inference input PNG bytes remain unchanged.',
        invalid_geometry='nonfinite or malformed polygons cannot be drawn; all remain in raw/scored diagnostics',
        implementation_sha256=sha(Path(__file__)))
    write_once(output/'gallery-receipt.json',result)
    return result
