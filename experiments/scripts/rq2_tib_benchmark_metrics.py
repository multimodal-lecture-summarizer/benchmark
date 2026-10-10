"""Pinned semantic evaluation, preserving every token of long inputs.

BERTScore uses its official implementation for encoder-sized inputs; longer
abstracts/summaries use the same token alignment over contextual windows.
SBERTScore is Ye et al. (2024) sentence precision, not a factuality percentage.
"""

import importlib.metadata
import re
import time

BERT_MODEL = "FacebookAI/xlm-roberta-large"
BERT_REVISION = "c23d21b0620b635a76227c604d44e43a9f0ee389"
SBERT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
SBERT_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"


def sentences(text):
    """Deterministic multilingual punctuation/newline splitter, no resource download."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*|[\r\n]+", text) if part.strip()]


def _normalize(vectors):
    import numpy as np
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-12)


def token_alignment_f1(candidate, reference, block_size=256, candidate_weights=None, reference_weights=None):
    """Unweighted BERTScore: greedy cosine alignment, then harmonic P/R."""
    import numpy as np
    if not len(candidate) or not len(reference):
        return 0.0
    candidate, reference = _normalize(candidate), _normalize(reference)
    precision = np.full(len(candidate), -np.inf)
    recall = np.full(len(reference), -np.inf)
    for i in range(0, len(candidate), block_size):
        for j in range(0, len(reference), block_size):
            similarity = candidate[i:i+block_size] @ reference[j:j+block_size].T
            precision[i:i+len(similarity)] = np.maximum(precision[i:i+len(similarity)], similarity.max(axis=1))
            recall[j:j+similarity.shape[1]] = np.maximum(recall[j:j+similarity.shape[1]], similarity.max(axis=0))
    p = float(np.average(precision, weights=candidate_weights))
    r = float(np.average(recall, weights=reference_weights))
    return 2*p*r/(p+r) if abs(p+r) > 1e-12 else 0.0


class SemanticScorer:
    """Reusable lazy encoders; test adapters expose the same tokenizer/encode interface."""

    def __init__(self, *, device="cpu", batch_size=16, bert_adapter=None, sentence_adapter=None,
                 on_event=None):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.device, self.batch_size = device, batch_size
        self._bert, self._sentence = bert_adapter, sentence_adapter
        self._injected = bert_adapter is not None or sentence_adapter is not None
        self.on_event = on_event

    def _emit(self, **event):
        if self.on_event is not None:
            self.on_event(event)

    def load(self):
        """Load the pinned encoders explicitly before evaluating records."""
        self._load()
        return self

    @property
    def metadata(self):
        versions = {}
        for package in ("bert-score", "sentence-transformers", "transformers", "torch", "numpy"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = "not_installed"
        return {"version": "tib_semantic_v1", "packages": versions, "device": self.device,
                "batch_size": self.batch_size, "test_adapters": self._injected,
                "bertscore": {"model": BERT_MODEL, "revision": BERT_REVISION,
                              "tokenizer_revision": BERT_REVISION, "layer": 17,
                              "idf": False, "rescale_with_baseline": False,
                              "long_input": "nonoverlapping_510_token_context_windows_global_alignment",
                              "implementation": "official_bert_score_short_custom_same_alignment_long",
                              "max_tokens": 512, "special_tokens_excluded": "aggregation_only_zero_weight_kept_as_alignment_targets"},
                "sbertscore": {"model": SBERT_MODEL, "revision": SBERT_REVISION,
                               "tokenizer_revision": SBERT_REVISION,
                               "formula": "mean_summary_sentence_max_source_sentence_cosine",
                               "sentence_splitter": "latin_punctuation_whitespace_cjk_punctuation_or_newline_v1",
                               "long_sentence": "token_weighted_mean_of_all_context_windows_then_l2",
                               "source_coverage": "all_sentences_batched_no_document_truncation"}}

    def _load(self):
        if self._bert is None:
            started = time.perf_counter()
            self._emit(stage="model_loading", status="started", model=BERT_MODEL)
            from bert_score import BERTScorer
            from huggingface_hub import snapshot_download
            path = snapshot_download(BERT_MODEL, revision=BERT_REVISION,
                                     allow_patterns=["*.json", "*.safetensors", "*.model"])
            self._bert = BERTScorer(model_type=path, num_layers=17, idf=False,
                                   rescale_with_baseline=False, device=self.device,
                                   batch_size=self.batch_size, use_fast_tokenizer=True)
            self._emit(stage="model_loading", status="completed", model=BERT_MODEL,
                       elapsed_seconds=time.perf_counter() - started)
        if self._sentence is None:
            started = time.perf_counter()
            self._emit(stage="model_loading", status="started", model=SBERT_MODEL)
            from sentence_transformers import SentenceTransformer
            self._sentence = SentenceTransformer(SBERT_MODEL, revision=SBERT_REVISION, device=self.device)
            self._emit(stage="model_loading", status="completed", model=SBERT_MODEL,
                       elapsed_seconds=time.perf_counter() - started)

    def _bert_tokens(self, text, *, include_special=False):
        """Contextualize all tokens; specials have zero aggregation weight."""
        import numpy as np
        import torch
        tokenizer = self._bert._tokenizer
        ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
        capacity = 512 - tokenizer.num_special_tokens_to_add(pair=False)
        vectors, weights = [], []
        for start in range(0, len(ids), capacity):
            encoded = tokenizer.prepare_for_model(ids[start:start+capacity], return_tensors="pt",
                                                  prepend_batch_axis=True, truncation=False)
            # Pinned XLM-R single sequences have one inserted token on each end.
            # Mask wrappers by position: content <unk>/<mask> IDs remain content.
            if len(encoded["input_ids"][0]) != len(ids[start:start+capacity]) + 2:
                raise ValueError("Expected pinned XLM-R single-sequence wrapper layout")
            special = torch.zeros(len(encoded["input_ids"][0]), dtype=torch.bool)
            special[0] = special[-1] = True
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with torch.inference_mode():
                hidden = self._bert._model(**encoded).last_hidden_state[0]
            vectors.append((hidden if include_special else hidden[~special.to(hidden.device)]).float().cpu().numpy())
            weights.extend((~special).tolist() if include_special else [1] * int((~special).sum()))
        embeddings = np.concatenate(vectors) if vectors else np.empty((0, 1))
        return (embeddings, weights) if include_special else embeddings

    def _bertscore(self, hypothesis, reference):
        if not hypothesis.strip() or not reference.strip():
            return 0.0
        tokenizer = self._bert._tokenizer
        lengths = [len(tokenizer.encode(text, add_special_tokens=True, truncation=False))
                   for text in (hypothesis, reference)]
        if max(lengths) <= 512:
            return float(self._bert.score([hypothesis], [reference], batch_size=self.batch_size)[2][0])
        candidate, candidate_weights = self._bert_tokens(hypothesis, include_special=True)
        target, reference_weights = self._bert_tokens(reference, include_special=True)
        return token_alignment_f1(candidate, target, candidate_weights=candidate_weights,
                                 reference_weights=reference_weights)

    def _sentence_vectors(self, texts, *, arm=None, input_kind=None, sentence_offset=0):
        """Batch all sentence windows, retaining one vector per original sentence."""
        import numpy as np
        tokenizer = self._sentence.tokenizer
        capacity = self._sentence.max_seq_length - tokenizer.num_special_tokens_to_add(pair=False)
        if capacity < 1:
            raise ValueError("Sentence encoder has no content-token capacity")
        parts, weights, owners = [], [], []
        for owner, text in enumerate(texts):
            offsets = tokenizer(text, add_special_tokens=False, truncation=False,
                                return_offsets_mapping=True)["offset_mapping"]
            if not offsets:
                raise ValueError("Nonempty sentence produced no encoder tokens")
            window_count = (len(offsets) + capacity - 1) // capacity
            if window_count > 1:
                self._emit(stage="sentence_windows", status="started", arm=arm,
                           input_kind=input_kind, sentence_index=sentence_offset + owner + 1,
                           token_count=len(offsets), window_count=window_count)
            for start in range(0, len(offsets), capacity):
                window = offsets[start:start+capacity]
                parts.append(text[window[0][0]:window[-1][1]])
                weights.append(len(window))
                owners.append(owner)
        # Bound GPU encode batches even for unusually long unpunctuated sentences.
        totals, counts = {}, {}
        for start in range(0, len(parts), self.batch_size):
            chunk = parts[start:start+self.batch_size]
            for part in chunk:
                if len(tokenizer.encode(part, truncation=False)) > self._sentence.max_seq_length:
                    raise ValueError("Retokenized sentence window exceeds capacity; no truncation allowed")
            vectors = self._sentence.encode(chunk, batch_size=self.batch_size,
                                            convert_to_numpy=True, normalize_embeddings=False,
                                            show_progress_bar=False)
            for i, vector in enumerate(vectors, start):
                owner, weight = owners[i], weights[i]
                totals[owner] = totals.get(owner, 0) + np.asarray(vector) * weight
                counts[owner] = counts.get(owner, 0) + weight
        return _normalize([totals[i] / counts[i] for i in range(len(texts))]) if texts else np.empty((0, 1))

    def score_pair(self, arms, reference, transcript):
        import numpy as np
        self._load()
        bert = {}
        for arm in ("S1", "S3"):
            started = time.perf_counter()
            self._emit(stage="bertscore", status="started", arm=arm)
            bert[arm] = self._bertscore(arms[arm]["summary"], reference)
            self._emit(stage="bertscore", status="completed", arm=arm, score=bert[arm],
                       elapsed_seconds=time.perf_counter() - started)
        sbert_started = time.perf_counter()
        summary_vectors = {arm: self._sentence_vectors(sentences(arms[arm]["summary"]),
                                                      arm=arm, input_kind="summary")
                           for arm in ("S1", "S3")}
        maxima = {arm: np.full(len(vectors), -np.inf) for arm, vectors in summary_vectors.items()}
        source = sentences(transcript)
        self._emit(stage="source_embedding", status="started", processed_sentences=0,
                   total_sentences=len(source))
        for start in range(0, len(source), self.batch_size):
            started = time.perf_counter()
            vectors = self._sentence_vectors(source[start:start+self.batch_size],
                                            input_kind="source", sentence_offset=start)
            for arm, summary in summary_vectors.items():
                if len(summary):
                    maxima[arm] = np.maximum(maxima[arm], (summary @ vectors.T).max(axis=1))
            self._emit(stage="source_embedding", status="completed",
                       processed_sentences=min(start + self.batch_size, len(source)),
                       total_sentences=len(source), elapsed_seconds=time.perf_counter() - started)
        sbert = {arm: float(values.mean()) if len(values) and source else 0.0
                 for arm, values in maxima.items()}
        for arm in ("S1", "S3"):
            self._emit(stage="sbertscore", status="completed", arm=arm, score=sbert[arm],
                       elapsed_seconds=time.perf_counter() - sbert_started)
        for metric in (bert, sbert):
            metric["S3_minus_S1"] = metric["S3"] - metric["S1"]
        return {"bertscore": bert, "sbertscore": sbert}
