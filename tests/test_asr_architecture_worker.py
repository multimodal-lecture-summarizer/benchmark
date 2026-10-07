"""Checks the pinned Paraformer checkpoint's model-vocabulary decoder."""

import pytest

from experiments.evaluation.asr_architecture_worker import _use_paraformer_vocabulary


def test_paraformer_decodes_ids_from_model_token_list() -> None:
    class Tokenizer:
        def ids2tokens(self, ids):
            raise AssertionError("stale SentencePiece decoder used")

        def tokens2text(self, tokens):
            raise AssertionError("stale SentencePiece text decoder used")

    pieces = [f"piece{i}" for i in range(10020)]
    pieces[10007] = "▁zip"
    pieces[41] = "per"
    _use_paraformer_vocabulary(Tokenizer, pieces)

    tokenizer = Tokenizer()
    tokens = tokenizer.ids2tokens([10007, 41])
    assert tokens == ["▁zip", "per"]
    assert tokenizer.tokens2text(tokens) == "zipper"
    with pytest.raises(RuntimeError, match="outside_model_vocabulary"):
        tokenizer.ids2tokens([10020])


def test_paraformer_rejects_unexpected_token_list() -> None:
    with pytest.raises(RuntimeError, match="unexpected Paraformer token list"):
        _use_paraformer_vocabulary(type("Tokenizer", (), {}), ["only one"])
    with pytest.raises(RuntimeError, match="unexpected Paraformer token list"):
        _use_paraformer_vocabulary(type("Tokenizer", (), {}), {"0": "<blank>"})
