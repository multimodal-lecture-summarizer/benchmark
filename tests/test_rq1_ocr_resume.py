"""Interrupted OCR resumes at the next verified chunk, with no frame substitution."""

import json

import cv2
import numpy as np
import pytest

from experiments.scripts import rq1_ocr_resume as worker
from experiments.scripts import rq1_source_feature_extraction as source


def test_interrupted_ocr_resumes_only_missing_frames_and_rejects_tampering(
    tmp_path, monkeypatch,
):
    seen = []
    fail_once = [True]

    class Capture:
        def __init__(self, path):
            self.second = 0

        def isOpened(self):
            return True

        def set(self, prop, value):
            self.second = round(value / 1000)

        def read(self):
            return True, np.full((2, 2, 3), self.second, dtype=np.uint8)

        def release(self):
            pass

    class OCR:
        def __init__(self, **kwargs):
            pass

        def ocr(self, frame, cls):
            second = int(frame[0, 0, 0])
            seen.append(second)
            if second == 100 and fail_once[0]:
                fail_once[0] = False
                raise KeyboardInterrupt
            return [[[None, (f"frame {second}", 0.99)]]]

    monkeypatch.setattr(cv2, "VideoCapture", Capture)
    monkeypatch.setattr(source, "_import_paddleocr", lambda: OCR)
    cache = tmp_path / "ocr"
    args = (tmp_path / "media.mp4", 101.0, "train-fixture", "media-hash",
            cache, tmp_path / "model", {"det/inference.pdmodel": "weight-hash"}, False)
    with pytest.raises(KeyboardInterrupt):
        worker.extract(*args)
    assert (cache / "000000.json").is_file()
    assert not (cache / "000100.json").exists()

    worker.extract(*args)
    texts, hashes, manifest_sha = worker.load_cache(
        cache, unit_id="train-fixture", media_sha256="media-hash",
        duration=101.0, weights=args[6], compute="cpu")
    assert len(texts) == len(hashes) == 101
    assert texts[0] == "frame 0" and texts[100] == "frame 100"
    assert len(seen) == 102  # Only the interrupted frame was retried.
    assert manifest_sha == worker.sha256_file(cache / "manifest.json")

    chunk = cache / "000000.json"
    payload = json.loads(chunk.read_text(encoding="utf-8"))
    payload["texts"][0] = "tampered"
    chunk.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="OCR chunk changed"):
        worker.load_cache(cache, unit_id="train-fixture", media_sha256="media-hash",
                          duration=101.0, weights=args[6], compute="cpu")
