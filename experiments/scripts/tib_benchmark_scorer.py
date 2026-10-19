"""New TIB scorer contract; historical 120-record scorers remain unchanged.

Neural loading is local-only. A fixture pass never grants scorer-ready status.
"""

import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np

from experiments.scripts.rq2_tib_benchmark_metrics import (
    BERT_MODEL, BERT_REVISION, SBERT_MODEL, SBERT_REVISION, sentences,
)
from experiments.scripts.rq2_tib_semantic_v2 import SemanticScorerV2

METRICS = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1", "source_sentence_similarity_v1")
PACKAGE_PINS = {"rouge-score": "0.1.2", "bert-score": "0.3.13", "sentence-transformers": "5.7.0",
                "transformers": "4.57.6", "torch": "2.6.0+cu124", "numpy": "2.4.6", "nltk": "3.9.4"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_versions():
    result = {}
    for name in ("rouge-score", "bert-score", "sentence-transformers", "transformers", "torch", "numpy", "nltk"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def validate_assets(path, *, model, revision):
    """Require independently acquired local assets and a complete hash manifest."""
    root = Path(path).resolve()
    receipt = json.loads((root / "asset_manifest.json").read_text(encoding="utf-8"))
    if receipt.get("model") != model or receipt.get("revision") != revision:
        raise ValueError("Neural asset model/revision mismatch")
    files = receipt.get("files", {})
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
              and p.name != "asset_manifest.json"}
    if not files or set(files) != actual or not any(p.endswith((".safetensors", ".bin")) for p in actual):
        raise ValueError("Neural assets need complete files and actual weights")
    for name, expected in files.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root) or sha256(target) != expected:
            raise ValueError("Neural asset hash mismatch")
    return root


def source_similarity(summary_vectors, source_batches):
    """Mean over summary sentences of their maximum source-sentence cosine."""
    summary = np.asarray(summary_vectors, dtype=np.float32)
    if not len(summary):
        raise ValueError("Empty summary vectors")
    norm = np.linalg.norm(summary, axis=1, keepdims=True)
    if np.any(norm == 0) or not np.isfinite(summary).all():
        raise ValueError("Invalid summary vectors")
    summary = summary / norm
    maxima = np.full(len(summary), -np.inf)
    for batch in source_batches:
        batch = np.asarray(batch, dtype=np.float32)
        if not len(batch):
            continue
        lengths = np.linalg.norm(batch, axis=1, keepdims=True)
        if np.any(lengths == 0) or not np.isfinite(batch).all():
            raise ValueError("Invalid source vectors")
        maxima = np.maximum(maxima, (summary @ (batch / lengths).T).max(axis=1))
    if not np.isfinite(maxima).all():
        raise ValueError("Empty source vectors")
    return float(maxima.mean())


class LocalSemanticScorer(SemanticScorerV2):
    """Reuse token-ID windowing; never implicitly download a neural checkpoint."""

    def __init__(self, *, bert_path=None, sentence_path=None, **kwargs):
        super().__init__(batch_size=1, device="cpu", **kwargs)
        self.bert_path, self.sentence_path = bert_path, sentence_path

    def _load(self):
        installed = package_versions()
        if any(installed[name] != pin for name, pin in PACKAGE_PINS.items()):
            raise ValueError("Scorer package lock mismatch; explicit preselection amendment required")
        if self._bert is None:
            from bert_score import BERTScorer
            path = validate_assets(self.bert_path, model=BERT_MODEL, revision=BERT_REVISION)
            self._bert = BERTScorer(model_type=str(path), num_layers=17, idf=False,
                                   rescale_with_baseline=False, device="cpu", batch_size=1,
                                   use_fast_tokenizer=True)
        if self._sentence is None:
            from sentence_transformers import SentenceTransformer
            path = validate_assets(self.sentence_path, model=SBERT_MODEL, revision=SBERT_REVISION)
            self._sentence = SentenceTransformer(str(path), device="cpu", local_files_only=True)

    @property
    def metadata(self):
        value = super().metadata
        value["version"] = "tib_model_benchmark_scorer_v1"
        value["source_similarity_metric_id"] = "source_sentence_similarity_v1"
        value["package_pins"] = PACKAGE_PINS
        value["scorer_ready"] = False
        return value

    def score_one(self, hypothesis, reference, source):
        self._load()
        bert = float(self._bertscore(hypothesis, reference))
        vectors = self._sentence_vectors(sentences(hypothesis))
        parts = sentences(source)
        batches = (self._sentence_vectors(parts[i:i + self.batch_size])
                   for i in range(0, len(parts), self.batch_size))
        return bert, source_similarity(vectors, batches)


def score_record(hypothesis, reference, source, *, semantic=None):
    """Technical/undefined failures are NULL, never imputed quality zero."""
    result = {"metrics": dict.fromkeys(METRICS), "failures": {}}
    for name, text in (("hypothesis", hypothesis), ("reference", reference), ("source", source)):
        if not isinstance(text, str) or not text.strip():
            result["failures"]["record"] = "empty_or_invalid_" + name
            return result
    try:
        from rouge_score.rouge_scorer import RougeScorer
        if importlib.metadata.version("rouge-score") != "0.1.2":
            raise ValueError("Expected rouge-score==0.1.2")
        scores = RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True).score(reference, hypothesis)
        result["metrics"].update({name + "_f1": float(value.fmeasure) for name, value in scores.items()})
    except Exception as error:
        result["failures"]["rouge"] = type(error).__name__ + ": " + str(error)
    try:
        if semantic is None:
            raise RuntimeError("Pinned local neural assets/backend probe required")
        bert, similarity = semantic.score_one(hypothesis, reference, source)
        if not np.isfinite([bert, similarity]).all():
            raise ValueError("Nonfinite semantic score")
        result["metrics"].update(bertscore_f1=float(bert), source_sentence_similarity_v1=float(similarity))
    except Exception as error:
        result["failures"]["semantic"] = type(error).__name__ + ": " + str(error)
    return result
