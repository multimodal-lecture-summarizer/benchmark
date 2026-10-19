"""Explicit T4 runtime amendment; frozen scoring and aggregation math are inherited."""
import json
import math

from .tib_benchmark_scorer import (
    LocalSemanticScorer, PACKAGE_PINS, METRICS, BERT_MODEL, BERT_REVISION,
    SBERT_MODEL, SBERT_REVISION, package_versions, validate_assets, sha256, score_record,
)
from .tib_benchmark_scorer_probe import probe


def runtime_pins():
    return {**PACKAGE_PINS, "torch": "2.11.0+cu130", "numpy": "2.1.3"}


def _observed_bert_configuration(bert):
    observed = {"idf": bert.idf, "num_layers": bert.num_layers,
                "rescale_with_baseline": bert.rescale_with_baseline,
                "use_fast_tokenizer": bert.use_fast_tokenizer,
                "tokenizer_is_fast": bert._tokenizer.is_fast,
                "actual_encoder_layers": len(bert._model.encoder.layer),
                "idf_dictionary_fitted": bert._idf_dict is not None}
    if observed != {"idf": False, "num_layers": 17, "rescale_with_baseline": False,
                    "use_fast_tokenizer": True, "tokenizer_is_fast": True,
                    "actual_encoder_layers": 17, "idf_dictionary_fitted": False}:
        raise ValueError("Observed BERT layer/IDF/tokenizer configuration drift")
    return observed


class RuntimeSemanticScorer(LocalSemanticScorer):
    def __init__(self, bert_path, sentence_path):
        super().__init__(bert_path=bert_path, sentence_path=sentence_path)
        self.device = "cuda:0"
        self.runtime_profile = None

    def _load(self):
        import torch
        if package_versions() != runtime_pins():
            raise ValueError("Formal runtime scorer package lock mismatch")
        if not torch.cuda.is_available() or "T4" not in torch.cuda.get_device_name(0):
            raise ValueError("Formal runtime scorer requires actual CUDA T4")
        if torch.is_autocast_enabled():
            raise ValueError("Formal runtime scorer forbids active CUDA autocast")
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.set_float32_matmul_precision("highest")
        if self.runtime_profile is not None:
            _observed_bert_configuration(self._bert)
            for model in (self._bert._model, self._sentence):
                if model.training or any(p.dtype != torch.float32 for p in model.parameters()):
                    raise ValueError("Loaded scorer runtime drifted from FP32/eval")
            if self._bert._tokenizer.model_max_length != 512 or self._sentence.max_seq_length != 128:
                raise ValueError("Loaded scorer native capacities drifted")
            return
        from bert_score import BERTScorer
        from sentence_transformers import SentenceTransformer
        assets = {}
        for key, path, model, revision in (
                ("bert", self.bert_path, BERT_MODEL, BERT_REVISION),
                ("sentence", self.sentence_path, SBERT_MODEL, SBERT_REVISION)):
            root = validate_assets(path, model=model, revision=revision)
            assets[key] = {"root": str(root), "manifest_sha256": sha256(root / "asset_manifest.json"),
                           "manifest": json.loads((root / "asset_manifest.json").read_text())}
        self._bert = BERTScorer(model_type=assets["bert"]["root"], num_layers=17,
                               idf=False, rescale_with_baseline=False, device=self.device,
                               batch_size=1, use_fast_tokenizer=True)
        self._sentence = SentenceTransformer(assets["sentence"]["root"], device=self.device,
                                             local_files_only=True)
        for model in (self._bert._model, self._sentence):
            model.to(device=self.device, dtype=torch.float32).eval()
            if model.training or any(p.dtype != torch.float32 for p in model.parameters()):
                raise ValueError("Scorer must remain FP32/eval")
        bert_max = self._bert._tokenizer.model_max_length
        sentence_max = self._sentence.max_seq_length
        if bert_max != 512 or sentence_max != 128:
            raise ValueError("Pinned scorer native capacities must be BERT512/sentence128")
        bert_observed = _observed_bert_configuration(self._bert)
        self.runtime_profile = {
            "device": self.device, "gpu_name": torch.cuda.get_device_name(0), "dtype": "float32",
            "batch_size": self.batch_size, "idf": False, "idf_fit_ids": [], "eval": True,
            "autocast": False, "TF32": False, "bert_native_max_seq_length": bert_max,
            "bert_config_max_position_embeddings": self._bert._model.config.max_position_embeddings,
            "sentence_max_seq_length": sentence_max,
            "observed_bertscore_configuration": bert_observed,
            "model_parameter_dtypes": {"bert": sorted({str(p.dtype) for p in self._bert._model.parameters()}),
                                       "sentence": sorted({str(p.dtype) for p in self._sentence.parameters()})},
            "assets": assets, "package_pins": runtime_pins(),
        }

    @property
    def metadata(self):
        result = super().metadata
        result.update(version="tib_formal_runtime_scorer_amendment_v1", package_pins=runtime_pins(),
                      runtime_profile=self.runtime_profile, scorer_ready=False)
        return result


def _bert_token_id_probe(scorer):
    tokenizer = scorer._bert._tokenizer
    text = "Quantum states café unknown [MASK]. " * 150
    expected = tokenizer.encode(text, add_special_tokens=False, truncation=False)
    observed, lengths = [], []

    def observe(module, args, kwargs):
        ids = kwargs.get("input_ids", args[0] if args else None)
        if ids is None or len(ids) != 1:
            raise ValueError("BERT probe requires actual input IDs and batch1")
        row = ids[0].tolist()
        lengths.append(len(row))
        observed.extend(row[1:-1])

    hook = scorer._bert._model.register_forward_pre_hook(observe, with_kwargs=True)
    try:
        scorer._bert_tokens(text, include_special=True)
    finally:
        hook.remove()
    passed = bool(lengths) and len(expected) > 510 and max(lengths) <= 512 and observed == expected
    return {"status": "pass" if passed else "hold", "content_tokens": len(expected),
            "exact_token_ids_preserved": observed == expected, "native_capacity": 512,
            "observed_max_sequence_tokens": max(lengths, default=0), "window_count": len(lengths)}


def _metric_failure_fixtures(text):
    """Controlled backend faults verify NULL policy, separate from neural probes."""
    class ControlledFault:
        def __init__(self, mode):
            self.mode = mode

        def score_one(self, *args):
            if self.mode == "raises":
                raise RuntimeError("Controlled semantic fixture failure")
            return float("nan"), 0.0

    cases = {}
    passed = True
    for mode in ("raises", "nonfinite"):
        value = score_record(text, text, text, semantic=ControlledFault(mode))
        metrics = value["metrics"]
        valid = (set(metrics) == set(METRICS) and "semantic" in value["failures"]
                 and "rouge" not in value["failures"]
                 and all(type(metrics[name]) in (int, float) and math.isfinite(metrics[name])
                         for name in METRICS[:3]) and all(metrics[name] is None for name in METRICS[3:]))
        cases[mode] = {"result": value, "status": "pass" if valid else "hold",
                      "metric_denominators": {name: {"selected": 1, "scoreable": int(metrics.get(name) is not None),
                                                     "null": int(metrics.get(name) is None)} for name in METRICS}}
        passed = passed and valid
    return {"status": "pass" if passed else "hold", "scope": "controlled_faults_not_neural_quality_scores",
            "cases": cases}


def runtime_fixtures(scorer):
    """Execute real runtime probes on supplied scorer; this never starts generation."""
    result = {"status": "hold", "selection_start_authorized": False,
              "formal_generation_executed": False, "absolute_tolerance": 1e-5}
    try:
        scorer.load()
        result["native_long_probe"] = native = probe(scorer)
        result["bert_exact_id_probe"] = direct = _bert_token_id_probe(scorer)
        text = "The lecture explains quantum states. Electrons occupy discrete energy levels."
        identity = score_record(text, text, text, semantic=scorer)
        result["identity_e2e"] = identity
        nulls = [score_record(*values, semantic=scorer) for values in
                 ((None, text, text), (text, "", text), (text, text, None))]
        result["null_missing_fixtures"] = nulls
        result["metric_failure_fixtures"] = metric_failures = _metric_failure_fixtures(text)
        # Observe the inherited source batching without replacing its mathematics.
        source = " ".join(f"Source sentence number {i} explains quantum states." for i in range(12))
        from .rq2_tib_benchmark_metrics import sentences
        source_parts = sentences(source)
        batches = []
        original = scorer._sentence_vectors

        def observe(texts, **kwargs):
            batches.append(list(texts))
            return original(texts, **kwargs)

        scorer._sentence_vectors = observe
        try:
            source_fixture = score_record(text, text, source, semantic=scorer)
        finally:
            del scorer._sentence_vectors
        source_observed = [part for batch in batches[1:] for part in batch]
        source_ok = source_observed == source_parts and all(len(batch) <= 1 for batch in batches[1:])
        result["full_source_batching"] = {"status": "pass" if source_ok else "hold",
            "expected_sentences": len(source_parts), "observed_sentences": len(source_observed),
            "batch_size": 1, "all_source_sentences_preserved": source_observed == source_parts,
            "fixture_result": source_fixture}
        profile = scorer.runtime_profile or {}
        native_errors = [native.get(key) for key in
                         ("bert_native_max_abs_error", "sentence_native_max_abs_error")]
        equivalence_ok = all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1e-5
                             for v in native_errors)
        passed = (metric_failures["status"] == "pass"
                  and native.get("status") == "pass" and equivalence_ok and direct["status"] == "pass"
                  and direct.get("exact_token_ids_preserved") is True
                  and native.get("long_sentence_exact_token_ids_preserved") is True
                  and type(native.get("long_sentence_content_tokens")) is int
                  and native["long_sentence_content_tokens"] > 126
                  and not identity["failures"] and set(identity["metrics"]) == set(METRICS)
                  and all(type(v) in (int, float) and math.isfinite(v) and abs(v - 1) <= 1e-5
                          for v in identity["metrics"].values())
                  and all(v["failures"] and all(x is None for x in v["metrics"].values()) for v in nulls)
                  and source_ok and not source_fixture["failures"]
                  and profile.get("bert_native_max_seq_length") == 512
                  and profile.get("sentence_max_seq_length") == 128)
        result.update(status="pass" if passed else "hold", runtime_profile=profile)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result
