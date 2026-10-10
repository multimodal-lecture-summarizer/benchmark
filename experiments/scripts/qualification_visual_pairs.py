"""Record perceptual candidates and source dependence; never auto-exclude."""
from collections import defaultdict
import numpy as np
from PIL import ImageOps

def dhash(image):
    pixels = np.asarray(ImageOps.grayscale(image).resize((9, 8)))
    value = 0
    for bit in (pixels[:, :-1] > pixels[:, 1:]).ravel():
        value = (value << 1) | int(bit)
    return value

def pair_queue(rows, threshold=6):
    pairs = []
    for i, left in enumerate(rows):
        for right in rows[i+1:]:
            if left['split'] == right['split']:
                continue
            distance = (left['dhash'] ^ right['dhash']).bit_count()
            if distance > threshold:
                continue
            a, b = left['tokens'], right['tokens']
            union = a | b
            pairs.append({'left':left['id'], 'right':right['id'], 'distance':distance,
                          'left_source_group':left['source_group'], 'right_source_group':right['source_group'],
                          'exact_bytes':left['image_sha256']==right['image_sha256'],
                          'text_jaccard':len(a & b)/len(union) if union else 0,
                          'decision':'HOLD', 'reason':'perceptual_candidate_not_a_duplicate_decision',
                          'source_group_same':left['source_group']==right['source_group']})
    return pairs

def source_groups(rows):
    groups = defaultdict(list)
    for row in rows: groups[row['source_group']].append(row)
    return [{'source_group':key, 'records':len(group), 'splits':sorted({x['split'] for x in group}),
             'cross_split':len({x['split'] for x in group})>1,
             'identity_status':'release_path_group_not_independently_verified_video_url'}
            for key,group in sorted(groups.items())]
