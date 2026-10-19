import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_scorer_colab_backend as backend
from experiments.scripts.tib_benchmark_scorer import LocalSemanticScorer, METRICS, PACKAGE_PINS


def test_runtime_pins_are_explicit_amendment_without_mutating_frozen_pins():
    values = backend.runtime_pins()
    assert values == {**PACKAGE_PINS, "torch": "2.11.0+cu130", "numpy": "2.1.3"}
    assert PACKAGE_PINS["torch"] == "2.6.0+cu124"
    assert PACKAGE_PINS["numpy"] == "2.4.6"
    assert backend.RuntimeSemanticScorer.score_one is LocalSemanticScorer.score_one
    assert backend.RuntimeSemanticScorer._bert_tokens is LocalSemanticScorer._bert_tokens
    assert backend.RuntimeSemanticScorer._sentence_vectors is LocalSemanticScorer._sentence_vectors


def fake_runtime(monkeypatch, tmp_path, gpu="Tesla T4", autocast=False):
    class Model:
        training = True
        dtype = "float32"
        config = SimpleNamespace(max_position_embeddings=514)
        encoder = SimpleNamespace(layer=list(range(17)))

        def to(self, **kwargs):
            self.placement = kwargs
            return self

        def eval(self):
            self.training = False
            return self

        def parameters(self):
            return iter([SimpleNamespace(dtype=self.dtype)])

    class Bert:
        def __init__(self, **kwargs):
            self._model, self._tokenizer = Model(), SimpleNamespace(model_max_length=512, is_fast=True)
            self.arguments = kwargs
            self.idf, self.num_layers = kwargs["idf"], kwargs["num_layers"]
            self.rescale_with_baseline = kwargs["rescale_with_baseline"]
            self.use_fast_tokenizer, self._idf_dict = kwargs["use_fast_tokenizer"], None

    class Sentence(Model):
        max_seq_length = 128

        def __init__(self, path, **kwargs):
            self.path, self.arguments = path, kwargs

    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, get_device_name=lambda i: gpu),
        is_autocast_enabled=lambda: autocast, float32="float32",
        backends=SimpleNamespace(cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)),
                                 cudnn=SimpleNamespace(allow_tf32=True)),
        set_float32_matmul_precision=lambda value: None)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "bert_score", SimpleNamespace(BERTScorer=Bert))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Sentence))
    monkeypatch.setattr(backend, "package_versions", backend.runtime_pins)
    paths = []
    for name, model, revision in (("bert", backend.BERT_MODEL, backend.BERT_REVISION),
                                  ("sentence", backend.SBERT_MODEL, backend.SBERT_REVISION)):
        root = tmp_path / name
        root.mkdir()
        raw = b"small fixture asset; never loaded as model"
        (root / "model.safetensors").write_bytes(raw)
        (root / "asset_manifest.json").write_text(json.dumps({"model": model, "revision": revision,
            "files": {"model.safetensors": hashlib.sha256(raw).hexdigest()}}))
        paths.append(root)
    return backend.RuntimeSemanticScorer(*paths), torch


def test_load_enforces_fp32_eval_t4_capacity_and_frozen_asset_hashes(monkeypatch, tmp_path):
    scorer, torch = fake_runtime(monkeypatch, tmp_path)
    scorer.load()
    profile = scorer.metadata["runtime_profile"]
    assert profile["device"] == "cuda:0" and profile["gpu_name"] == "Tesla T4"
    assert profile["dtype"] == "float32" and profile["batch_size"] == 1
    assert profile["bert_native_max_seq_length"] == 512
    assert profile["sentence_max_seq_length"] == 128
    assert profile["bert_config_max_position_embeddings"] == 514
    assert profile["eval"] is True and profile["idf"] is False
    assert profile["observed_bertscore_configuration"]["actual_encoder_layers"] == 17
    assert torch.backends.cuda.matmul.allow_tf32 is False
    assert torch.backends.cudnn.allow_tf32 is False
    assert scorer._bert.arguments["num_layers"] == 17
    assert scorer._bert.arguments["idf"] is False
    assert scorer._sentence.arguments["local_files_only"] is True
    assert profile["assets"]["bert"]["manifest"]["revision"] == backend.BERT_REVISION
    assert len(profile["assets"]["sentence"]["manifest_sha256"]) == 64


@pytest.mark.parametrize("gpu,autocast", [("NVIDIA A100", False), ("Tesla T4", True)])
def test_non_t4_or_autocast_is_hold_not_silent_substitution(monkeypatch, tmp_path, gpu, autocast):
    scorer, _ = fake_runtime(monkeypatch, tmp_path, gpu, autocast)
    assert backend.runtime_fixtures(scorer)["status"] == "hold"


def test_package_drift_and_corrupt_asset_fail_closed(monkeypatch, tmp_path):
    scorer, _ = fake_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(backend, "package_versions", lambda: {**backend.runtime_pins(), "numpy": "other"})
    with pytest.raises(ValueError, match="lock mismatch"):
        scorer.load()
    monkeypatch.setattr(backend, "package_versions", backend.runtime_pins)
    (tmp_path / "bert/model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        scorer.load()


def test_loaded_dtype_drift_and_sentence_capacity_fail_closed(monkeypatch, tmp_path):
    scorer, _ = fake_runtime(monkeypatch, tmp_path)
    scorer.load()
    scorer._bert._model.dtype = "float16"
    with pytest.raises(ValueError, match="runtime drifted"):
        scorer.load()
    scorer._bert._model.dtype = "float32"
    scorer._sentence.max_seq_length = 256
    with pytest.raises(ValueError, match="native capacities drifted"):
        scorer.load()
    scorer.runtime_profile = None
    # New construction of the sentence class is bounded by its native config.
    sentence_class = sys.modules["sentence_transformers"].SentenceTransformer
    sentence_class.max_seq_length = 256
    with pytest.raises(ValueError, match="native capacities"):
        scorer.load()


@pytest.mark.parametrize("field,value", [("idf", True), ("num_layers", 16),
                                          ("use_fast_tokenizer", False), ("_idf_dict", {1: 0.5})])
def test_observed_bert_settings_drift_fail_closed(monkeypatch, tmp_path, field, value):
    scorer, _ = fake_runtime(monkeypatch, tmp_path)
    scorer.load()
    setattr(scorer._bert, field, value)
    with pytest.raises(ValueError, match="Observed BERT"):
        scorer.load()


def test_actual_missing_input_contract_returns_all_null_without_encoder_call():
    class NoCall:
        def score_one(self, *args):
            raise AssertionError("Missing inputs must not reach neural encoders")

    for values in ((None, "Reference.", "Source."), ("Summary.", "", "Source."),
                   ("Summary.", "Reference.", None)):
        result = backend.score_record(*values, semantic=NoCall())
        assert set(result["metrics"]) == set(METRICS)
        assert all(value is None for value in result["metrics"].values())
        assert "record" in result["failures"]


def test_actual_metric_faults_retain_lexical_scores_and_all_denominators():
    pytest.importorskip("rouge_score")
    result = backend._metric_failure_fixtures("The lecture explains quantum states.")
    assert result["status"] == "pass"
    for case in result["cases"].values():
        assert set(case["metric_denominators"]) == set(METRICS)
        assert all(case["result"]["metrics"][name] is not None for name in METRICS[:3])
        assert all(case["result"]["metrics"][name] is None for name in METRICS[3:])
        assert all(counts["selected"] == 1 for counts in case["metric_denominators"].values())


def test_actual_bert_input_hook_proves_exact_ids_and_capacity_without_neural_model():
    content = list(range(1, 701))

    class Model:
        observer = None

        def register_forward_pre_hook(self, callback, with_kwargs):
            assert with_kwargs is True
            self.observer = callback
            return SimpleNamespace(remove=lambda: setattr(self, "observer", None))

    model = Model()

    class Row(list):
        def tolist(self):
            return list(self)

    class Scorer:
        _bert = SimpleNamespace(_model=model, _tokenizer=SimpleNamespace(encode=lambda *a, **k: content))

        def _bert_tokens(self, text, include_special):
            for start in range(0, len(content), 510):
                model.observer(model, (), {"input_ids": [Row([0] + content[start:start + 510] + [2])]})

    result = backend._bert_token_id_probe(Scorer())
    assert result["status"] == "pass" and result["window_count"] == 2
    assert result["observed_max_sequence_tokens"] == 512
    assert result["exact_token_ids_preserved"] is True
    assert model.observer is None


def test_fixtures_cover_identity_nulls_full_source_and_hold_on_mismatch(monkeypatch):
    class Scorer:
        runtime_profile = {"bert_native_max_seq_length": 512, "sentence_max_seq_length": 128}

        def load(self):
            return self

        def _sentence_vectors(self, texts):
            return [[1.0] for _ in texts]

    def score(hypothesis, reference, source, semantic):
        if any(not value for value in (hypothesis, reference, source)):
            return {"metrics": dict.fromkeys(METRICS), "failures": {"record": "missing"}}
        from experiments.scripts.rq2_tib_benchmark_metrics import sentences
        semantic._sentence_vectors(sentences(hypothesis))
        for part in sentences(source):
            semantic._sentence_vectors([part])
        return {"metrics": dict.fromkeys(METRICS, 1.0), "failures": {}}

    monkeypatch.setattr(backend, "score_record", score)
    monkeypatch.setattr(backend, "probe", lambda _: {"status": "pass", "bert_native_max_abs_error": 1e-6,
        "sentence_native_max_abs_error": 1e-6, "long_sentence_exact_token_ids_preserved": True,
        "long_sentence_content_tokens": 700})
    monkeypatch.setattr(backend, "_bert_token_id_probe", lambda _: {"status": "pass", "exact_token_ids_preserved": True})
    monkeypatch.setattr(backend, "_metric_failure_fixtures", lambda _: {"status": "pass"})
    result = backend.runtime_fixtures(Scorer())
    assert result["status"] == "pass"
    assert result["full_source_batching"]["expected_sentences"] == 12
    assert result["full_source_batching"]["all_source_sentences_preserved"] is True
    assert len(result["null_missing_fixtures"]) == 3
    assert result["formal_generation_executed"] is False
    monkeypatch.setattr(backend, "_metric_failure_fixtures", lambda _: {"status": "hold"})
    assert backend.runtime_fixtures(Scorer())["status"] == "hold"
    monkeypatch.setattr(backend, "_metric_failure_fixtures", lambda _: {"status": "pass"})
    monkeypatch.setattr(backend, "probe", lambda _: {"status": "fail"})
    assert backend.runtime_fixtures(Scorer())["status"] == "hold"
