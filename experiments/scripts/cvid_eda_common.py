"""Shared immutable-source paths, identity and image statistics for CVID EDA."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from experiments.scripts.inventory_cvid_splits import EXPECTED, ROOT, SOURCE
from experiments.scripts.spotting_metrics import normalize_text

OUT = ROOT/'experiments/outputs/cvid-all-split-eda-261014'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def decoded(raw):
    with Image.open(io.BytesIO(raw)) as image:
        rgb = image.convert('RGB'); rgb.load()
    return rgb


def pixel_key(image):
    return f'{image.width}x{image.height}:'+hashlib.sha256(image.tobytes()).hexdigest()


def features(image):
    gray = np.asarray(image.convert('L'), dtype=np.float32)
    lap = (gray[1:-1, :-2]+gray[1:-1, 2:]+gray[:-2, 1:-1]+gray[2:, 1:-1]-4*gray[1:-1, 1:-1])
    return dict(width=image.width,height=image.height,gray_mean=float(gray.mean()),
                gray_std=float(gray.std()),laplacian_variance=float(lap.var()) if lap.size else 0.)


def write_csv(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT/name
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if name.endswith('.gz') else open
    with opener(target,'wt',encoding='utf-8',newline='') as stream:
        if rows:
            fields = list(dict.fromkeys(k for row in rows for k in row))
            writer = csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    return dict(path=target.relative_to(ROOT).as_posix(),rows=len(rows),sha256=sha(target),bytes=target.stat().st_size)


def write_json(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return dict(path=target.relative_to(ROOT).as_posix(),sha256=sha(target),bytes=target.stat().st_size)


def validate_artifacts(receipt):
    for item in receipt['artifacts']:
        if sha(ROOT/item['path']) != item['sha256']:
            raise ValueError('EDA artifact changed: '+item['path'])


SEMANTIC_SAMPLE_RULE = dict(version='course_stratified_box_height_quantiles_v1',
    selection='three objects per course nearest normalized box-height q10/q50/q90, ties by object_id; without replacement',
    scope='all 24 courses; sample is diagnostic, no population error-rate or all-label-correctness claim',
    review='inspect each sampled crop plus its full annotated frame; record exact/uncertain/disagreement and omissions',
    reviewer='Codex visual inspection, not author adjudication or independent human gold',
    source_edit_allowed=False,test_model_tuning_allowed=False)
