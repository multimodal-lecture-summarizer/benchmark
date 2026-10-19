"""Deterministic annotation-QC samples and complete geometry anomaly galleries."""
import json
import textwrap
import zipfile

import pandas as pd
from PIL import Image, ImageDraw, ImageOps

from experiments.scripts.cvid_eda_common import OUT, SOURCE, SEMANTIC_SAMPLE_RULE, decoded, sha, write_csv, write_json
from experiments.scripts.cvid_eda_pair_review import font


def prepare_galleries():
    objects = pd.read_csv(OUT/'objects.csv.gz',keep_default_na=False,dtype={'course':str})
    frames = pd.read_csv(OUT/'frames.csv.gz',keep_default_na=False,dtype={'course':str})
    courses = pd.read_csv(OUT/'courses.csv',keep_default_na=False,dtype={'course':str}).set_index('course')
    selected = []
    for course,group in objects[objects.geometry_valid].groupby('course',sort=True):
        used = set()
        for q in (.1,.5,.9):
            target = group.box_height_rel.quantile(q)
            ranked = group[~group.object_id.isin(used)].assign(distance=lambda d:abs(d.box_height_rel-target))
            row = ranked.sort_values(['distance','object_id']).iloc[0].to_dict()
            used.add(row['object_id'])
            selected.append(dict(sample_id=f'sem-{len(selected):03d}',anchor_quantile=q,medium=courses.loc[course,'Medium'],**row))
    sample = pd.DataFrame(selected)
    write_csv('semantic-sample.csv',sample.to_dict('records'))
    folder = OUT/'semantic-source'; folder.mkdir(parents=True,exist_ok=True)
    cards = []
    with zipfile.ZipFile(SOURCE) as archive:
        for row in sample.to_dict('records'):
            image = decoded(archive.read('IIIT-CVid/Frames/'+row['frame_id']))
            patch = image.crop(tuple(row[k] for k in ('xmin','ymin','xmax','ymax')))
            annotated = image.copy(); drawing = ImageDraw.Draw(annotated)
            for obj in objects[objects.frame_id==row['frame_id']].to_dict('records'):
                bounds = tuple(obj[k] for k in ('xmin','ymin','xmax','ymax'))
                drawing.rectangle(bounds,outline='#e04040',width=1)
            drawing.rectangle(tuple(row[k] for k in ('xmin','ymin','xmax','ymax')),outline='#005dff',width=3)
            annotated.save(folder/(row['sample_id']+'-context.png'))
            patch.save(folder/(row['sample_id']+'-crop.png'))
            card = Image.new('RGB',(600,330),'white'); draw = ImageDraw.Draw(card)
            title = f"{row['sample_id']}  {row['split']}/course {row['course']}  XML: {row['text']}"
            for j,line in enumerate(textwrap.wrap(title,62)):
                draw.text((5,5+j*22),line,font=font(18),fill='black')
            draw.text((5,58),row['object_id'],font=font(11),fill='black')
            context = ImageOps.contain(annotated,(350,245))
            crop = ImageOps.contain(patch,(225,205))
            card.paste(context,(5,80)); card.paste(crop,(370,100))
            cards.append(card)
    semantic_sheets = OUT/'semantic-contact-sheets'; semantic_sheets.mkdir(exist_ok=True)
    for page,start in enumerate(range(0,len(cards),6),1):
        sheet = Image.new('RGB',(1200,990),'#e9edf2')
        for j,card in enumerate(cards[start:start+6]): sheet.paste(card,((j%2)*600,(j//2)*330))
        sheet.save(semantic_sheets/f'page-{page:03d}.jpg',quality=96)
    anomaly_sheets = OUT/'geometry-contact-sheets'; anomaly_sheets.mkdir(exist_ok=True)
    held = frames[frames.decision=='HOLD'].sort_values('frame_id')
    bad_cards = []
    with zipfile.ZipFile(SOURCE) as archive:
        for row in held.to_dict('records'):
            image = decoded(archive.read(row['archive_member'])); draw = ImageDraw.Draw(image)
            bad = objects[(objects.frame_id==row['frame_id']) & ~objects.geometry_valid]
            for obj in bad.to_dict('records'):
                draw.rectangle(tuple(obj[k] for k in ('xmin','ymin','xmax','ymax')),outline='magenta',width=4)
            card = Image.new('RGB',(600,410),'white'); d = ImageDraw.Draw(card)
            d.text((6,5),row['frame_id'],font=font(16),fill='black')
            detail = 'Box(es): '+str(bad[['xmin','ymin','xmax','ymax']].values.tolist())
            d.text((6,28),detail,font=font(14),fill='black')
            d.text((6,48),f"PNG {row['width']}x{row['height']} / XML {row['xml_width']}x{row['xml_height']}",font=font(14),fill='black')
            card.paste(ImageOps.contain(image,(590,340)),(5,68)); bad_cards.append(card)
    for page,start in enumerate(range(0,len(bad_cards),6),1):
        sheet = Image.new('RGB',(1200,1230),'#e9edf2')
        for j,card in enumerate(bad_cards[start:start+6]): sheet.paste(card,((j%2)*600,(j//2)*410))
        sheet.save(anomaly_sheets/f'page-{page:03d}.jpg',quality=96)
    receipt = dict(sample_count=len(sample),sample_rule=SEMANTIC_SAMPLE_RULE,
        sample_csv_sha256=sha(OUT/'semantic-sample.csv'),held_frames=len(held),
        galleries=[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p)) for folder in
                   (semantic_sheets,anomaly_sheets) for p in sorted(folder.glob('*.jpg'))])
    write_json('gallery-receipt.json',receipt)
    return receipt


if __name__=='__main__':
    print(json.dumps(prepare_galleries(),indent=2))
