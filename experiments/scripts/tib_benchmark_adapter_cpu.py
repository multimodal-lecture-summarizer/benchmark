"""CPU controls over every canonical sentence; no hidden sentence preselection."""
from .tib_benchmark_adapter_budget import AdapterFailure
from .tib_benchmark_output import sentence_spans, select_delivered


def _deliver(source, spans, selected, selector, word_cap, candidate):
    raw = " ".join(source[spans[i][0]:spans[i][1]] for i in sorted(selected))
    delivery = selector(raw, word_cap)
    delivered = delivery["text"]
    if not isinstance(delivered, str) or not delivered.strip() or len(delivered.split()) > word_cap:
        raise AdapterFailure("empty/over-cap delivered control output")
    return {"candidate_id": candidate, "raw_final": raw, "delivered_final": delivered,
            "sentence_count": len(spans), "selected_sentence_indices": sorted(selected),
            "selected_source_spans": [list(spans[i]) for i in sorted(selected)],
            "delivery": delivery,
            "generation_device": "cpu", "generation_gpu_memory": None}


def lead3(source, *, word_cap, selector=select_delivered, splitter=sentence_spans):
    spans = splitter(source)
    if not spans:
        raise AdapterFailure("no source sentences")
    return _deliver(source, spans, range(min(3, len(spans))), selector, word_cap, "lead3")


def lexrank(source, *, word_cap, selector=select_delivered, splitter=sentence_spans, threshold=0.1,
            damping=0.85, tolerance=1e-9, max_iterations=1000,
            graph_memory_limit_bytes=512 * 1024 * 1024):
    """Thresholded TF-IDF cosine graph, PageRank, source-order delivered text.

    All sentence units enter TF-IDF and the graph. Explicit resource failure is
    preferable to dropping tail sentences. Dense graph storage has O(n^2) cost.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not 0 <= threshold <= 1 or not 0 < damping < 1 or word_cap < 1:
        raise ValueError("invalid LexRank profile")
    spans = splitter(source)
    sentences = [source[a:b] for a, b in spans]
    n = len(sentences)
    if not n:
        raise AdapterFailure("no source sentences")
    # Conservative graph working-set allowance, not a measured peak RAM claim.
    if 4 * n * n * 8 > graph_memory_limit_bytes:
        raise AdapterFailure("LexRank declared dense graph memory limit")
    try:
        tfidf = TfidfVectorizer(lowercase=True, stop_words="english", norm="l2",
                                token_pattern=r"(?u)\b\w+\b").fit_transform(sentences)
    except ValueError as exc:
        raise AdapterFailure("LexRank empty TF-IDF vocabulary") from exc
    similarities = (tfidf @ tfidf.T).toarray()
    adjacency = (similarities >= threshold).astype(float)
    np.fill_diagonal(adjacency, 0)
    sums = adjacency.sum(axis=1)
    adjacency[sums == 0] = 1 / n
    sums[sums == 0] = 1
    transition = adjacency / sums[:, None]
    scores = np.full(n, 1 / n)
    for iteration in range(max_iterations):
        updated = (1 - damping) / n + damping * (transition.T @ scores)
        if np.abs(updated - scores).sum() <= tolerance:
            scores = updated
            break
        scores = updated
    else:
        raise AdapterFailure("LexRank PageRank failed to converge")
    ranked = sorted(range(n), key=lambda index: (-float(scores[index]), index))
    selected, words = [], 0
    for index in ranked:
        length = len(sentences[index].split())
        if words + length <= word_cap:
            selected.append(index)
            words += length
    if not selected:
        # One run-on sentence may exceed the word budget; the common selector
        # applies and explicitly records the same forced-boundary policy.
        selected = ranked[:1]
    result = _deliver(source, spans, selected, selector, word_cap, "lexrank")
    result.update({"pagerank_iterations": iteration + 1,
                   "sentence_scores": [float(x) for x in scores],
                   "graph_sentence_count": n, "tfidf_vocabulary_size": tfidf.shape[1]})
    return result
