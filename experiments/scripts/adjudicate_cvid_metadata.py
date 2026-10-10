"""Record conservative frame adjudication from the completed full ZIP audit."""
import csv
import json
from collections import Counter
from experiments.scripts.dataset_qualification_io import OUT, write_csv, write_json


def main():
    def read(name):
        with (OUT/name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))

    issues = read('iiit-cvid-box-issue-ledger.csv')
    for row in issues:
        x1, y1, x2, y2 = json.loads(row['box'])
        width, height = json.loads(row['actual_size'])
        row['anomaly_class'] = ('negative_coordinate' if min(x1, y1, x2, y2) < 0 else
                                'right_edge_one_pixel' if x2 == width + 1 else 'other_overflow')
        row['review_evidence'] = 'full_resolution_decode_and_XML_check; 20_frame_contact_sheet_inspected'
        row['resolution'] = 'HOLD_frame_for_geometry_endpoint; original_labels_preserved'
        row['why_not_clip'] = 'image_edge_does_not_establish_author_coordinate_convention_or_missing_text'
    issue_artifact = write_csv('iiit-cvid-geometry-adjudication.csv', issues)
    metadata = read('iiit-cvid-derived-metadata-ledger.csv')
    frames = {r['id']: r for r in read('iiit-cvid-frame-ledger.csv')}
    overrides = []
    for row in metadata:
        if row['decision'] != 'REPAIR':
            continue
        source = frames[row['id']]
        overrides.append({'id':row['id'], 'source_xml_sha256':source['xml_sha256'],
                          'source_image_sha256':source['image_sha256'],
                          'width':int(source['width']), 'height':int(source['height']),
                          'rule':'decoded_PNG_dimensions_only; boxes_and_text_unchanged',
                          'decision':'REPAIR', 'cohort_frozen':False})
    override_artifact = write_json('iiit-cvid-derived-dimension-overrides.json', overrides)
    pairs = read('iiit-cvid-cross-split-pairs.csv')
    summary_artifact = write_json('iiit-cvid-adjudication-summary.json', {
        'geometry_classes':dict(Counter(r['anomaly_class'] for r in issues)),
        'geometry_resolution':'22 boxes / 20 frames HOLD; no label repair supported',
        'metadata_repairs':len(overrides), 'metadata_geometry_overlap_HOLD':len(metadata)-len(overrides),
        'duplicate_candidates':len(pairs), 'exact_byte_pairs':sum(r['exact_bytes']=='True' for r in pairs),
        'max_candidate_text_jaccard':max(float(r['text_jaccard']) for r in pairs),
        'duplicate_resolution':'469 pairs HOLD; low lexical overlap is not proof of source independence',
        'crop_endpoint':'existing 15379 validation-crop audit is separate from this full-frame review',
        'artifacts':[issue_artifact, override_artifact], 'cohort_frozen':False})
    receipt_path = OUT/'iiit-cvid-qualification-receipt.json'
    review = json.loads(receipt_path.read_text(encoding='utf-8'))
    additions = [issue_artifact, override_artifact, summary_artifact]
    new_paths = {item['path'] for item in additions}
    review['artifacts'] = [item for item in review['artifacts'] if item['path'] not in new_paths] + additions
    review['derived_dimension_overrides'] = len(overrides)
    review['geometry_adjudication'] = '22 boxes remain HOLD; no clipping without source-coordinate evidence'
    review['cohort_frozen'] = False
    write_json('iiit-cvid-qualification-receipt.json', review)


if __name__ == '__main__':
    main()
