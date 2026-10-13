"""Offline real-model tests of token coverage and SentenceTransformer pooling."""

import numpy as np
import pytest

from experiments.scripts.rq2_tib_semantic_v2 import SemanticScorerV2


@pytest.fixture
def encoder(tmp_path):
    """Construct a tiny real transformer locally; no checkpoint is downloaded."""
    import torch
    from transformers import BertConfig, BertModel, BertTokenizerFast
    from sentence_transformers import SentenceTransformer, models

    torch.manual_seed(24)
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]",
             "hello", "world", "cafe", ".", "中", "文", "a", "b"]
    (tmp_path / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    tokenizer = BertTokenizerFast(vocab_file=str(tmp_path / "vocab.txt"), do_lower_case=True)
    tokenizer.save_pretrained(tmp_path)
    model = BertModel(BertConfig(vocab_size=len(vocab), hidden_size=12,
                                num_hidden_layers=1, num_attention_heads=3,
                                intermediate_size=24, max_position_embeddings=32))
    model.save_pretrained(tmp_path)
    transformer = models.Transformer(str(tmp_path), max_seq_length=8, do_lower_case=False)
    return SentenceTransformer(modules=[transformer, models.Pooling(12),
                                        models.Dense(12, 7), models.Normalize()], device="cpu")


def scorer(encoder, batch_size=2):
    return SemanticScorerV2(sentence_adapter=encoder, bert_adapter=object(), batch_size=batch_size)


def test_short_inputs_match_real_encode_including_dense_normalize(encoder):
    texts = ["  HELLO world.  ", "café 中文", "unknown [MASK]"]
    expected = encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    actual = scorer(encoder)._sentence_vectors(texts)
    np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-5)


def test_long_unicode_unknown_and_special_ids_preserved_once(encoder):
    import torch
    text = "HELLO café 中文 [UNK] [MASK] unknown " * 7
    tokenizer = encoder.tokenizer
    original = tokenizer.encode(text.strip(), add_special_tokens=False, truncation=False)
    observed = []

    def record(module, args):
        features = args[0]
        assert features["input_ids"].shape[1] <= encoder.max_seq_length
        assert not torch.is_grad_enabled()
        assert module.training is False
        for ids, mask in zip(features["input_ids"], features["attention_mask"]):
            real = ids[mask.bool()].tolist()
            assert real[0] == tokenizer.cls_token_id and real[-1] == tokenizer.sep_token_id
            observed.extend(real[1:-1])

    handle = encoder.register_forward_pre_hook(record)
    try:
        vector = scorer(encoder)._sentence_vectors([text])
    finally:
        handle.remove()
    assert observed == original
    assert tokenizer.unk_token_id in observed and tokenizer.mask_token_id in observed
    assert vector.shape == (1, 7)
    assert np.linalg.norm(vector[0]) == pytest.approx(1)


def test_weighted_windows_match_real_pipeline_and_batch_size_independent(encoder):
    import torch
    texts = ["hello " * 13 + "world", "world " * 8]
    expected = []
    for text in texts:
        ids = encoder.tokenizer.encode(text.strip(), add_special_tokens=False, truncation=False)
        total = 0
        for start in range(0, len(ids), 6):
            part = ids[start:start + 6]
            prepared = encoder.tokenizer.prepare_for_model(part, truncation=False)
            features = encoder.tokenizer.pad([prepared], return_tensors="pt")
            encoder.eval()
            with torch.inference_mode():
                total = total + encoder(features)["sentence_embedding"][0].numpy() * len(part)
        mean = total / len(ids)
        expected.append(mean / np.linalg.norm(mean))
    for batch_size in (1, 2, 32):
        np.testing.assert_allclose(scorer(encoder, batch_size)._sentence_vectors(texts),
                                   expected, atol=1e-6, rtol=1e-5)


def test_empty_and_impossible_capacity(encoder):
    metric = scorer(encoder)
    assert metric._sentence_vectors([]).shape == (0, 1)
    with pytest.raises(ValueError, match="no encoder tokens"):
        metric._sentence_vectors(["   "])
    encoder.max_seq_length = 2
    with pytest.raises(ValueError, match="no content-token capacity"):
        metric._sentence_vectors(["hello"])


def test_metadata_changes_only_sentence_window_method(encoder):
    from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
    old = SemanticScorer(sentence_adapter=encoder, bert_adapter=object()).metadata
    new = scorer(encoder).metadata
    assert new["version"] == "tib_semantic_v2"
    assert old["version"] == "tib_semantic_v1"
    assert new["bertscore"] == old["bertscore"]
    assert new["sbertscore"]["model"] == old["sbertscore"]["model"]
    assert new["sbertscore"]["revision"] == old["sbertscore"]["revision"]
    assert new["test_adapters"] is True
    assert "direct_content_token_ids" in new["sbertscore"]["window_encoding"]
