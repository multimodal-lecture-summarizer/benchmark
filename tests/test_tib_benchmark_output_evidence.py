import hashlib

import pytest

from experiments.scripts.tib_benchmark_output_evidence import validate_tokenizers


def test_token_proxy_rejects_mutated_pinned_tokenizer(tmp_path):
    directory = tmp_path / 'bart'
    directory.mkdir()
    path = directory / 'config.json'
    path.write_bytes(b'original')
    receipt = {'tokenizers': {'bart': {'files': [{'file': 'config.json', 'sha256': hashlib.sha256(b'original').hexdigest()}]}}}
    validate_tokenizers(tmp_path, receipt)
    path.write_bytes(b'mutated')
    with pytest.raises(ValueError, match='hash mismatch'):
        validate_tokenizers(tmp_path, receipt)


def test_tokenizer_receipt_cannot_escape_asset_root(tmp_path):
    receipt = {'tokenizers': {'bart': {'files': [{'file': '../../outside', 'sha256': '0'*64}]}}}
    with pytest.raises(ValueError, match='hash mismatch'):
        validate_tokenizers(tmp_path, receipt)
