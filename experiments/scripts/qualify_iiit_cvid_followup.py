"""Restore train/test review from the hash-pinned local ZIP, preserving labels."""
import hashlib
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from PIL import Image, ImageDraw, ImageOps
from experiments.scripts.dataset_qualification_io import ROOT, OUT, sha, write_csv, receipt
from experiments.scripts.qualification_visual_pairs import dhash, pair_queue, source_groups

EXPECTED = 'b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489'

def main():
    path = ROOT/'research-data/iiit-cvid-source/IIIT-CVid.zip'
    archive_sha = sha(path)
    assert archive_sha == EXPECTED, 'Recovered ZIP identity differs'
    rows, box_issues, metadata_repairs, review_images, failed = [], [], [], [], []
    with zipfile.ZipFile(path) as archive:
        names=set(archive.namelist())
        selected=sorted(n for n in names if n.startswith('IIIT-CVid/Frames/') and n.endswith('.png'))
        for index,name in enumerate(selected,1):
            ident=name.removeprefix('IIIT-CVid/Frames/')
            split,course,lecture,_=ident.split('/')
            try:
                raw=archive.read(name)
                xml_path=name[:-4]+'.xml'; xml_bytes=archive.read(xml_path); xml=ET.fromstring(xml_bytes)
                image=Image.open(io.BytesIO(raw)).convert('RGB'); image.load(); width,height=image.size
                declared=(int(xml.findtext('size/width')),int(xml.findtext('size/height')))
                issues=[]; texts=[]
                for ordinal,obj in enumerate(xml.findall('object')):
                    label=(obj.findtext('name') or '').strip();texts.append(label)
                    coords=[int(float(obj.findtext('bndbox/'+key))) for key in ['xmin','ymin','xmax','ymax']]
                    x1,y1,x2,y2=coords
                    reason=[]
                    if not label: reason.append('blank_label')
                    if not (0<=x1<x2<=width and 0<=y1<y2<=height): reason.append('outside_or_nonpositive_geometry')
                    if reason:
                        issue={'id':ident,'object_index':ordinal,'label':label,'box':coords,'actual_size':[width,height],
                               'decision':'HOLD','reason':reason,'source_xml_sha256':hashlib.sha256(xml_bytes).hexdigest()}
                        box_issues.append(issue);issues.append(issue)
                mismatch=declared!=(width,height)
                decision='HOLD' if issues else 'REPAIR' if mismatch else 'KEEP'
                if mismatch:
                    metadata_repairs.append({'id':ident,'original_size':list(declared),'derived_size':[width,height],
                                             'decision':decision,'scope':'derived_dimensions_only_original_XML_preserved',
                                             'all_boxes_within_image':not bool(issues)})
                if issues:
                    preview=image.copy();draw=ImageDraw.Draw(preview)
                    for issue in issues: draw.rectangle(issue['box'],outline='red',width=3)
                    preview.thumbnail((320,210));review_images.append((ident,preview))
                rows.append({'id':ident,'split':split,'source_group':course+'/'+lecture,
                             'image_sha256':hashlib.sha256(raw).hexdigest(),'xml_sha256':hashlib.sha256(xml_bytes).hexdigest(),
                             'width':width,'height':height,'xml_width':declared[0],'xml_height':declared[1],
                             'xml_size_mismatch':mismatch,'objects':len(texts),'invalid_objects':len(issues),
                             'label_valid_geometry':not bool(issues),'media_valid':True,'decision':decision,
                             'reason':'geometry_or_blank_label_needs_author_adjudication' if issues else
                                      'decoded_dimensions_override_only_in_derived_metadata' if mismatch else 'frame_XML_geometry_pass',
                             'tokens':set(re.findall(r'[a-z0-9]+',' '.join(texts).casefold())), 'dhash':dhash(image)})
            except Exception as exc:
                failed.append({'id':ident,'decision':'HOLD','reason':str(exc)[:200]})
            if index%1000==0: print('Frames read',index,flush=True)
    pairs=pair_queue(rows)
    implicated={p[key] for p in pairs for key in ('left','right')}
    for row in rows:
        row['duplicate_review_pending']=row['id'] in implicated
        row['scientific_endpoint_status']='HOLD_duplicate_and_source_review' if row['id'] in implicated else 'provisional_not_frozen'
    groups=source_groups(rows)
    artifacts=[write_csv('iiit-cvid-frame-ledger.csv',({k:v for k,v in r.items() if k not in {'tokens','dhash'}} for r in rows)),
               write_csv('iiit-cvid-box-issue-ledger.csv',box_issues),
               write_csv('iiit-cvid-derived-metadata-ledger.csv',metadata_repairs),
               write_csv('iiit-cvid-cross-split-pairs.csv',pairs),write_csv('iiit-cvid-source-groups.csv',groups),
               write_csv('iiit-cvid-read-failures.csv',failed)]
    if review_images:
        canvas=Image.new('RGB',(1280,250*((len(review_images)+3)//4)),'white');draw=ImageDraw.Draw(canvas)
        for i,(ident,image) in enumerate(review_images):
            x=(i%4)*320;y=(i//4)*250;canvas.paste(image,(x,y+35));draw.text((x+3,y+3),ident,fill='black')
        target=OUT/'iiit-cvid-geometry-contact-sheet.png';canvas.save(target)
        artifacts.append({'path':str(target.relative_to(ROOT)),'sha256':sha(target)})
    result=receipt('iiit-cvid',{'selected':len(selected),'observed':len(rows),'label_valid':sum(r['label_valid_geometry'] for r in rows),
                    'media_valid':len(rows),'evaluated':0,'failed':len(failed)},artifacts,
                    source_archive_sha256=archive_sha,archive_restored_locally=True,
                    split_counts=dict(Counter(r['split'] for r in rows)),decisions=dict(Counter(r['decision'] for r in rows)),
                    invalid_boxes=len(box_issues),invalid_frames=sum(bool(r['invalid_objects']) for r in rows),
                    XML_size_mismatches=len(metadata_repairs),cross_split_candidate_pairs=len(pairs),
                    cross_split_source_groups=[g for g in groups if g['cross_split']],
                    status='full_frame_geometry_review_complete_duplicate_content_and_source_mapping_HOLD',
                    label_valid_scope='geometry_and_nonblank_names_not_independent_text_correctness')
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},ensure_ascii=True),flush=True)

if __name__=='__main__': main()
