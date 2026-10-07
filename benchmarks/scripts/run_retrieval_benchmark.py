"""Evidence retrieval bake-off runner for notebook 06a (smoke/full).

Candidates: BM25, dense (TF-IDF cosine as proxy), hybrid, reranked.
Primary metric: Recall@k.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
    mean,
    rank_shortlist,
    write_stage_quartet,
)


# ---------------------------------------------------------------------------
# Corpus building helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_corpus(multimodal_pkg: dict, unit_id: str) -> list[dict[str, str]]:
    """Build a passage list from the multimodal package for one unit."""
    for record in multimodal_pkg.get("records", []):
        if str(record.get("unit_id")) != str(unit_id):
            continue
        text = str(record.get("text_summary_10pct") or "")
        if not text.strip():
            return []
        # Split into overlapping windows of ~50 words as retrieval passages
        words = text.split()
        step = 25
        size = 50
        passages: list[dict[str, str]] = []
        for i in range(0, max(1, len(words) - size + 1), step):
            chunk = " ".join(words[i: i + size])
            passages.append({"passage_id": f"p{i}", "text": chunk})
        if not passages:
            passages = [{"passage_id": "p0", "text": text}]
        return passages
    return []


def _build_queries(unit: dict[str, Any]) -> list[dict[str, str]]:
    """Build query list from unit GT."""
    raw = unit.get("qa_questions") or unit.get("retrieval_queries") or []
    if raw:
        return [{"query_id": f"q{i}", "text": str(q)} for i, q in enumerate(raw)]
    # Fall back to unit transcript segments as queries
    transcript = str(unit.get("reference_text") or unit.get("transcript") or "")
    words = transcript.split()
    if not words:
        return [{"query_id": "q0", "text": str(unit.get("unit_id"))}]
    # Use first sentence fragment as the single smoke query
    first = " ".join(words[:min(10, len(words))])
    return [{"query_id": "q0", "text": first}]


def _relevant_passages(unit: dict[str, Any]) -> dict[str, set[str]]:
    """Return query_id -> set of relevant passage_ids from GT."""
    raw = unit.get("retrieval_gt") or {}
    return {str(qid): {str(p) for p in passages} for qid, passages in raw.items()}


# ---------------------------------------------------------------------------
# Retrieval algorithms
# ---------------------------------------------------------------------------


def _bm25_scores(
    query_tokens: list[str], passages: list[dict], k1: float = 1.5, b: float = 0.75
) -> list[tuple[str, float]]:
    if not passages:
        return []
    tf_map: list[Counter] = [Counter(_tokenize(p["text"])) for p in passages]
    avg_dl = mean(float(sum(c.values())) for c in tf_map)
    df: Counter = Counter()
    for c in tf_map:
        df.update(c.keys())
    n = len(passages)

    scores: list[tuple[str, float]] = []
    for idx, (passage, tf) in enumerate(zip(passages, tf_map)):
        dl = sum(tf.values())
        score = 0.0
        for term in query_tokens:
            if term not in df:
                continue
            idf = math.log((n - df[term] + 0.5) / (df[term] + 0.5) + 1)
            tf_val = tf[term]
            score += idf * (tf_val * (k1 + 1)) / (
                tf_val + k1 * (1 - b + b * dl / (avg_dl or 1))
            )
        scores.append((passage["passage_id"], score))
    return sorted(scores, key=lambda x: x[1], reverse=True)


def _tfidf_scores(
    query_tokens: list[str], passages: list[dict]
) -> list[tuple[str, float]]:
    """Dense proxy: TF-IDF cosine similarity."""
    if not passages:
        return []
    tf_map: list[Counter] = [Counter(_tokenize(p["text"])) for p in passages]
    df: Counter = Counter()
    for c in tf_map:
        df.update(c.keys())
    n = len(passages)

    def tfidf_vec(counter: Counter) -> dict[str, float]:
        total = sum(counter.values()) or 1
        return {
            t: (counter[t] / total) * math.log((n + 1) / (df.get(t, 0) + 1))
            for t in counter
        }

    def cosine(a: dict, b: dict) -> float:
        keys = set(a) & set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    q_vec = tfidf_vec(Counter(query_tokens))
    scores: list[tuple[str, float]] = []
    for passage, tf in zip(passages, tf_map):
        scores.append((passage["passage_id"], cosine(q_vec, tfidf_vec(tf))))
    return sorted(scores, key=lambda x: x[1], reverse=True)


def _hybrid_scores(
    query_tokens: list[str], passages: list[dict], alpha: float = 0.5
) -> list[tuple[str, float]]:
    """Linear interpolation of BM25 and TF-IDF."""
    bm25 = {pid: s for pid, s in _bm25_scores(query_tokens, passages)}
    dense = {pid: s for pid, s in _tfidf_scores(query_tokens, passages)}
    all_pids = {p["passage_id"] for p in passages}

    def norm(d: dict[str, float]) -> dict[str, float]:
        mx = max(d.values()) if d else 1.0
        return {k: v / (mx or 1.0) for k, v in d.items()}

    bm25_n = norm(bm25)
    dense_n = norm(dense)
    combined = {
        pid: alpha * bm25_n.get(pid, 0.0) + (1 - alpha) * dense_n.get(pid, 0.0)
        for pid in all_pids
    }
    return sorted(combined.items(), key=lambda x: x[1], reverse=True)


def _reranked_scores(
    query_tokens: list[str], passages: list[dict]
) -> list[tuple[str, float]]:
    """Hybrid first-stage then rerank by exact match count (cross-encoder proxy)."""
    first_stage = _hybrid_scores(query_tokens, passages)[:10]
    top_pids = {pid for pid, _ in first_stage}
    top_passages = [p for p in passages if p["passage_id"] in top_pids]
    reranked: list[tuple[str, float]] = []
    for passage in top_passages:
        exact = sum(1 for t in query_tokens if t in _tokenize(passage["text"]))
        base = dict(first_stage).get(passage["passage_id"], 0.0)
        reranked.append((passage["passage_id"], base + 0.1 * exact))
    return sorted(reranked, key=lambda x: x[1], reverse=True)


RETRIEVAL_CANDIDATES = {
    "bm25": _bm25_scores,
    "dense_tfidf": _tfidf_scores,
    "hybrid": _hybrid_scores,
    "reranked": _reranked_scores,
}


def _recall_at_k(
    ranked: list[tuple[str, float]], relevant: set[str], k: int
) -> float:
    if not relevant:
        return 1.0
    top_k = {pid for pid, _ in ranked[:k]}
    return len(top_k & relevant) / len(relevant)


def _ndcg_at_k(
    ranked: list[tuple[str, float]], relevant: set[str], k: int
) -> float:
    if not relevant:
        return 1.0
    dcg = sum(
        1.0 / math.log2(rank + 2)
        for rank, (pid, _) in enumerate(ranked[:k])
        if pid in relevant
    )
    idcg = sum(1.0 / math.log2(rank + 2) for rank in range(min(len(relevant), k)))
    return dcg / idcg if idcg else 0.0


def _candidates(profile: str) -> list[str]:
    if profile == "smoke":
        return ["bm25", "dense_tfidf"]
    return list(RETRIEVAL_CANDIDATES)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "06a_retrieval_benchmark", argv)
        units = load_eligible_units(context)
        multimodal_pkg = read_json_artifact(context, "summary.multimodal_package")

        k_values = [1, 3, 5] if context.profile == "smoke" else [1, 3, 5, 10]
        candidates = _candidates(context.profile)

        rankings: list[dict[str, Any]] = []
        per_query: list[dict[str, Any]] = []
        by_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            corpus = _build_corpus(multimodal_pkg, unit["unit_id"])
            queries = _build_queries(unit)
            gt_relevant = _relevant_passages(unit)

            if not corpus:
                raise RuntimeError(
                    f"unit {unit['unit_id']!r} has no passages in summary.multimodal_package"
                )

            for query in queries:
                qid = query["query_id"]
                qtokens = _tokenize(query["text"])
                relevant = gt_relevant.get(qid, set())
                # When no GT provided, treat first passage as relevant (smoke fallback)
                if not relevant:
                    relevant = {corpus[0]["passage_id"]}

                for candidate in candidates:
                    ranked = RETRIEVAL_CANDIDATES[candidate](qtokens, corpus)
                    metrics: dict[str, float] = {}
                    for k in k_values:
                        metrics[f"recall@{k}"] = _recall_at_k(ranked, relevant, k)
                        metrics[f"ndcg@{k}"] = _ndcg_at_k(ranked, relevant, k)

                    rankings.append(
                        {
                            "unit_id": unit["unit_id"],
                            "dataset_id": unit.get("dataset_id"),
                            "query_id": qid,
                            "candidate": candidate,
                            "rankings": [
                                {"passage_id": pid, "score": score}
                                for pid, score in ranked
                            ],
                            "execution_mode": "real",
                        }
                    )
                    per_query.append(
                        {
                            "unit_id": unit["unit_id"],
                            "query_id": qid,
                            "candidate": candidate,
                            "metrics": metrics,
                        }
                    )
                    by_candidate.setdefault(candidate, []).append(metrics)

        primary_k = k_values[-1]
        aggregate_metrics = {
            candidate: {
                f"recall@{k}": mean(row[f"recall@{k}"] for row in rows)
                for k in k_values
            }
            | {
                f"ndcg@{k}": mean(row[f"ndcg@{k}"] for row in rows)
                for k in k_values
            }
            for candidate, rows in by_candidate.items()
        }
        aggregate = [
            {
                "candidate": candidate,
                "metrics": metrics,
                "unit_count": len(by_candidate[candidate]),
            }
            for candidate, metrics in aggregate_metrics.items()
        ]
        shortlist_metrics = {
            candidate: {f"recall@{primary_k}": metrics[f"recall@{primary_k}"]}
            for candidate, metrics in aggregate_metrics.items()
        }
        shortlist = rank_shortlist(shortlist_metrics, f"recall@{primary_k}", higher_better=True)

        write_stage_quartet(
            context,
            "retrieval",
            predictions=rankings,
            per_unit_metrics=per_query,
            aggregate=aggregate,
            shortlist=shortlist,
        )
        write_run_manifest(context)
        print(
            f"[OK] retrieval benchmark: {len(units)} unit(s), "
            f"{len(aggregate)} candidate(s), k={primary_k}"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] retrieval benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
