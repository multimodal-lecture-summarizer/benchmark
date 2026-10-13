"""Evaluation-only amendment: encode sentence windows without re-tokenizing text.

The original scorer and its frozen hash remain unchanged. BERTScore, sentence
splitting, sentence aggregation and document matching inherit the v1 contract.
"""

from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer, _normalize


class SemanticScorerV2(SemanticScorer):
    """Keep every content token exactly once before contextual window pooling."""

    @property
    def metadata(self):
        result = super().metadata
        result["version"] = "tib_semantic_v2"
        result["sbertscore"]["window_encoding"] = (
            "direct_content_token_ids_prepare_pad_sentence_transformer_forward_v2"
        )
        result["sbertscore"]["content_coverage"] = "each_original_token_id_once_no_truncation"
        result["sbertscore"]["preprocessing"] = "sentence_transformer_strip_and_configured_lowercase"
        return result

    def _sentence_vectors(self, texts, *, arm=None, input_kind=None, sentence_offset=0):
        import numpy as np
        import torch

        if not texts:
            return np.empty((0, 1))
        encoder = self._sentence
        tokenizer = encoder.tokenizer
        maximum = encoder.max_seq_length
        special_count = tokenizer.num_special_tokens_to_add(pair=False)
        capacity = maximum - special_count
        if capacity < 1:
            raise ValueError("Sentence encoder has no content-token capacity")
        # Mirror SentenceTransformer's Transformer.tokenize preprocessing. The
        # content IDs themselves are never decoded or fed back through tokenize.
        first_module = encoder._first_module()
        lowercase = getattr(first_module, "do_lower_case", False)
        windows, owners, weights = [], [], []
        for owner, text in enumerate(texts):
            prepared_text = text.strip()
            if lowercase:
                prepared_text = prepared_text.lower()
            ids = tokenizer.encode(prepared_text, add_special_tokens=False, truncation=False)
            if not ids:
                raise ValueError("Nonempty sentence produced no encoder tokens")
            count = (len(ids) + capacity - 1) // capacity
            if count > 1:
                self._emit(stage="sentence_windows", status="started", arm=arm,
                           input_kind=input_kind, sentence_index=sentence_offset + owner + 1,
                           token_count=len(ids), window_count=count)
            for start in range(0, len(ids), capacity):
                content = ids[start:start + capacity]
                window = tokenizer.prepare_for_model(
                    content, add_special_tokens=True, truncation=False,
                    return_attention_mask=True,
                )
                if len(window["input_ids"]) != len(content) + special_count:
                    raise ValueError("Unexpected sentence-encoder special-token layout")
                if len(window["input_ids"]) > maximum:
                    raise ValueError("Sentence token-ID window exceeds encoder capacity")
                windows.append(window)
                owners.append(owner)
                weights.append(len(content))
        encoder.eval()
        encoder.to(self.device)
        totals, counts = {}, {}
        for start in range(0, len(windows), self.batch_size):
            features = tokenizer.pad(windows[start:start + self.batch_size],
                                     padding=True, return_tensors="pt")
            if features["input_ids"].shape[1] > maximum:
                raise ValueError("Padded sentence window exceeds encoder capacity")
            features = {key: value.to(self.device) for key, value in features.items()}
            # Calling the entire pipeline preserves Pooling, Dense and Normalize
            # modules, rather than substituting transformer hidden-state pooling.
            with torch.inference_mode():
                vectors = encoder(features)["sentence_embedding"].float().cpu().numpy()
            if len(vectors) != len(windows[start:start + self.batch_size]):
                raise ValueError("Sentence encoder returned unexpected window count")
            for index, vector in enumerate(vectors, start):
                owner, weight = owners[index], weights[index]
                totals[owner] = totals.get(owner, 0) + vector * weight
                counts[owner] = counts.get(owner, 0) + weight
        return _normalize([totals[i] / counts[i] for i in range(len(texts))])
