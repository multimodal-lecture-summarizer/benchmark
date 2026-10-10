"""Offline numerical and coverage contracts for semantic scoring."""

import numpy as np
import pytest

from experiments.scripts.rq2_tib_benchmark_metrics import (
    SemanticScorer, BERT_REVISION, SBERT_REVISION, sentences, token_alignment_f1,
)


class Tokenizer:
    def encode(self, text, add_special_tokens=True, truncation=False):
        assert truncation is False
        return list(range(len(text))) + ([100, 101] if add_special_tokens else [])

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, **kwargs):
        assert kwargs["truncation"] is False
        return {"offset_mapping": [(i, i+1) for i in range(len(text))]}


class BertAdapter:
    _tokenizer = Tokenizer()

    def score(self, candidates, references, **kwargs):
        assert len(candidates) == len(references) == 1
        return None, None, [1.0 if candidates[0] == references[0] else .25]


class SentenceAdapter:
    tokenizer = Tokenizer()
    max_seq_length = 7

    def __init__(self):
        self.encoded = []

    def encode(self, parts, **kwargs):
        self.encoded.extend(parts)
        return np.array([[part.count("a"), part.count("b")] for part in parts], dtype=float)


def scorer(batch_size=2):
    encoder = SentenceAdapter()
    return SemanticScorer(batch_size=batch_size, bert_adapter=BertAdapter(), sentence_adapter=encoder), encoder


def test_token_alignment_known_precision_recall_and_scale():
    candidate = [[2, 0], [0, 3]]
    reference = [[4, 0]]
    # P=.5, R=1, F1=2/3; scaling embeddings must not affect cosine.
    assert token_alignment_f1(candidate, reference, block_size=1) == pytest.approx(2/3)
    assert token_alignment_f1(reference, reference) == pytest.approx(1)
    assert token_alignment_f1([], reference) == 0


def test_sbert_mean_of_sentence_max_not_doc_mean():
    metric, encoder = scorer()
    scores = metric.score_pair({"S1": {"summary": "a.\nb."}, "S3": {"summary": "a."}}, "a.", "a.")
    assert scores["sbertscore"] == pytest.approx({"S1": .5, "S3": 1, "S3_minus_S1": .5})
    assert scores["bertscore"] == pytest.approx({"S1": .25, "S3": 1, "S3_minus_S1": .75})


def test_every_source_sentence_and_long_sentence_window_is_consumed():
    metric, encoder = scorer()
    transcript = "a.\nb.\naaaaaaaaaaa.\nbbbbbbbbbb."
    scores = metric.score_pair({"S1": {"summary": "b."}, "S3": {"summary": "a."}}, "a.", transcript)
    # Both matches occur in different source sentences and batches.
    assert scores["sbertscore"]["S1"] == pytest.approx(1)
    assert scores["sbertscore"]["S3"] == pytest.approx(1)
    assert "".join(encoder.encoded[2:]) == "".join(sentences(transcript))
    assert all(len(part) <= 5 for part in encoder.encoded)


@pytest.mark.parametrize("transcript,summary", [("", "a."), ("a.", ""), ("", "")])
def test_empty_inputs_have_defined_zero_scores(transcript, summary):
    metric, _ = scorer()
    scores = metric.score_pair({arm: {"summary": summary} for arm in ("S1", "S3")}, "", transcript)
    assert scores == {name: {"S1": 0, "S3": 0, "S3_minus_S1": 0}
                      for name in ("bertscore", "sbertscore")}


def test_metadata_is_stable_before_after_load_and_identifies_test_adapters():
    metric, _ = scorer()
    before = metric.metadata
    metric.score_pair({arm: {"summary": "a."} for arm in ("S1", "S3")}, "a.", "a.")
    assert metric.metadata == before
    assert before["test_adapters"] is True
    assert len(BERT_REVISION) == len(SBERT_REVISION) == 40
    assert before["bertscore"]["layer"] == 17
    assert before["sbertscore"]["source_coverage"].startswith("all_sentences")


def test_splitter_preserves_multilingual_nonempty_content():
    assert sentences("Hello! Next.\n中文。日本語！\nDeutsch?") == ["Hello!", "Next.", "中文。", "日本語！", "Deutsch?"]


def test_long_bertscore_uses_all_content_not_official_truncation():
    metric, _ = scorer()
    seen = []

    def vectors(text, *, include_special=False):
        seen.append(text)
        result = np.array([[1., 0.] for _ in text])
        return (result, [1] * len(result)) if include_special else result

    metric._bert_tokens = vectors
    long_reference = "a" * 1200
    assert metric._bertscore("a.", long_reference) == pytest.approx(1)
    assert seen == ["a.", long_reference]


def test_batch_size_validation():
    with pytest.raises(ValueError, match="positive"):
        SemanticScorer(batch_size=0)


def test_actual_fast_tokenizer_long_windows_keep_all_content_exclude_special_aggregation():
    """Exercise real fast-tokenizer API and real torch tensors without downloading anything."""
    from types import SimpleNamespace
    import torch
    from tokenizers import Tokenizer as CoreTokenizer, models, pre_tokenizers, processors
    from transformers import XLMRobertaTokenizerFast

    core = CoreTokenizer(models.WordLevel({"[CLS]": 0, "[SEP]": 1, "[UNK]": 2, "a": 3, "b": 4}, unk_token="[UNK]"))
    core.pre_tokenizer = pre_tokenizers.Whitespace()
    core.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]",
                                                         special_tokens=[("[CLS]", 0), ("[SEP]", 1)])
    tokenizer = XLMRobertaTokenizerFast(tokenizer_object=core, cls_token="[CLS]", sep_token="[SEP]",
                                       bos_token="[CLS]", eos_token="[SEP]",
                                       unk_token="[UNK]", model_max_length=512)
    calls = []

    class Encoder:
        def __call__(self, input_ids, **kwargs):
            calls.append(input_ids[0].tolist())
            return SimpleNamespace(last_hidden_state=torch.stack((input_ids.float(), torch.ones_like(input_ids)), dim=-1))

    adapter = SimpleNamespace(_tokenizer=tokenizer, _model=Encoder())
    metric = SemanticScorer(bert_adapter=adapter, sentence_adapter=SentenceAdapter())
    text = " ".join(["a"] * 510 + ["b"] * 519 + ["unknown"])
    content = metric._bert_tokens(text)
    assert [len(ids) for ids in calls] == [512, 512, 12]
    assert content[:, 0].tolist() == [3] * 510 + [4] * 519 + [2]
    full, weights = metric._bert_tokens(text, include_special=True)
    assert len(full) == 1036 and sum(weights) == 1030
    assert all(weight == 0 for vector, weight in zip(full, weights) if vector[0] in (0, 1))


def test_special_tokens_are_zero_weight_but_available_for_alignment_like_official_bertscore():
    candidate = [[1, 0], [0, 1]]
    reference = [[0, 1], [1, 0]]
    # Official greedy_cos_idf masks padding, not special alignment targets;
    # special IDF=0 excludes their OWN contribution, not their possible matches.
    assert token_alignment_f1(candidate, reference, candidate_weights=[1, 0],
                              reference_weights=[1, 0]) == pytest.approx(1)
    assert token_alignment_f1(candidate[:1], reference[:1]) == pytest.approx(0)
