"""Prepare hash-bound pair contact sheets; decisions require actual visual review."""
import csv
import hashlib
import json
import textwrap
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from experiments.scripts.cvid_eda_common import OUT, ROOT, SOURCE, decoded, sha, write_csv, write_json


def font(size=16):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf',size)


def prepare_pairs():
    base = ROOT/'experiments/outputs/cvid-all-split-inventory-261014'
    receipt = json.loads((base/'inventory.json').read_text(encoding='utf-8'))
    if sha(SOURCE)!=receipt['source_archive_sha256']: raise ValueError('pair source archive changed')
    for artifact in receipt['artifacts']:
        if sha(ROOT/artifact['path'])!=artifact['sha256']: raise ValueError('pair inventory artifact changed')
    frames = {r['frame_id']:r for r in csv.DictReader((base/'frames.csv').open(encoding='utf-8'))}
    pairs = list(csv.DictReader((base/'cross-split-dhash-candidates.csv').open(encoding='utf-8')))
    pairs.sort(key=lambda p:('__'.join(sorted([p['left'].split('/')[0],p['right'].split('/')[0]])),p['left'],p['right']))
    plan = dict(method='direct visual inspection of every queued pair; full-resolution source PNGs available',
        taxonomy=['different_observed_content','shared_observed_content','uncertain'],
        limits='resolves this dHash<=6 queue only; no leakage-recall or source-video independence guarantee',
        excludes_source_records=False,reviewer='Codex assisted visual inspection; not author/human adjudication')
    write_json('pair-review-plan.json',plan)
    images = {}
    folder = OUT/'pair-source-frames'
    with zipfile.ZipFile(SOURCE) as archive:
        for ident in sorted({p[k] for p in pairs for k in ('left','right')}):
            raw = archive.read('IIIT-CVid/Frames/'+ident)
            if hashlib.sha256(raw).hexdigest()!=frames[ident]['image_sha256']: raise ValueError('pair PNG changed')
            target = folder/ident
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
            images[ident] = ImageOps.contain(decoded(raw),(580,245))
    sheets = OUT/'pair-contact-sheets'; sheets.mkdir(parents=True,exist_ok=True)
    prepared = []
    for page,start in enumerate(range(0,len(pairs),8),1):
        group = pairs[start:start+8]
        canvas = Image.new('RGB',(1200,45+300*len(group)),'white'); draw = ImageDraw.Draw(canvas)
        draw.text((8,6),f'CVID pair review: page {page}, actual source pixels; dHash is only a screen',font=font(20),fill='black')
        for j,pair in enumerate(group):
            ident = f'pair-{start+j:04d}'
            y = 45+j*300
            draw.text((8,y),ident+'   dHash='+pair['distance'],font=font(),fill='black')
            for x,key in [(8,'left'),(608,'right')]:
                name = pair[key]
                draw.text((x,y+23),name,font=font(14),fill='black')
                canvas.paste(images[name],(x,y+45))
            prepared.append(dict(pair_id=ident,left=pair['left'],right=pair['right'],distance=pair['distance'],
                left_image_sha256=frames[pair['left']]['image_sha256'],right_image_sha256=frames[pair['right']]['image_sha256'],
                page=page,contact_sheet=f'pair-contact-sheets/page-{page:03d}.jpg',
                left_source_png='pair-source-frames/'+pair['left'],right_source_png='pair-source-frames/'+pair['right']))
        target = sheets/f'page-{page:03d}.jpg'; canvas.save(target,quality=94)
    artifact = write_csv('pair-review-inputs.csv',prepared)
    write_json('pair-review-input-receipt.json',dict(pairs=len(prepared),pages=page,source_archive_sha256=receipt['source_archive_sha256'],
        inputs=artifact,contact_sheets=[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p)) for p in sorted(sheets.glob('*.jpg'))]))
    return artifact


def validate_pair_decisions(path=None):
    path = path or OUT/'pair-review-decisions.csv'
    inputs = list(csv.DictReader((OUT/'pair-review-inputs.csv').open(encoding='utf-8')))
    decisions = list(csv.DictReader(path.open(encoding='utf-8-sig')))
    by_id = {r['pair_id']:r for r in decisions}
    if len(by_id)!=len(decisions) or set(by_id)!={r['pair_id'] for r in inputs}:
        raise ValueError('pair review incomplete/duplicate IDs')
    allowed = set(json.loads((OUT/'pair-review-plan.json').read_text(encoding='utf-8'))['taxonomy'])
    for row in inputs:
        d = by_id[row['pair_id']]
        if d['decision'] not in allowed or not d.get('rationale') or not d.get('reviewer'):
            raise ValueError('invalid pair review decision')
        for k in ('left','right','left_image_sha256','right_image_sha256'):
            if d.get(k)!=row[k]: raise ValueError('pair decision identity changed')
    return decisions


if __name__=='__main__':
    print(prepare_pairs())
