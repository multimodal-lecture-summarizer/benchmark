"""Descriptive TIB reference screening, embedded verbatim in the Colab notebook.

Lexical matches and cue phrases are review signals, never factuality judgments.
Only empty and reused abstracts are excluded by the broad-pool policy.
"""

import hashlib
import re
from collections import Counter

STOP_WORDS = frozenset("""a an the and or but if then than of to in on at by for
with without from as is are was were be been being this that these those it its
we our you your they their he she his her i me my not no can could will would
should may might have has had do does did also about into over under through
which who what when where how such each all some any both more most other
der die das den dem des ein eine einer eines und oder im in am an auf zu mit
von für ist sind wird werden als auch sich es wir sie er nicht einer einem
""".split())
CUE_PATTERNS = {
    "course_scope_cue": r"\b(?:this|the|entire|whole)\s+(?:course|lecture series)\b|\b(?:kurs|vorlesungsreihe)\b",
    "event_scope_cue": r"\b(?:welcome to|conference programme|conference program|about the speaker)\b",
}


def normalized_text(value):
    return " ".join(str(value or "").casefold().split())


def text_hash(value):
    text = normalized_text(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def content_tokens(value):
    return {token for token in re.findall(r"\b\w+\b", str(value or "").casefold())
            if len(token) > 2 and token not in STOP_WORDS}


def screen_reference(record, window_words=160, stride_words=80):
    """Use the FULL transcript; retain matched excerpts, not the whole corpus.

    Coverage = distinct non-stopword abstract tokens found anywhere in source /
    distinct non-stopword abstract tokens. No stemming or semantic inference.
    Windows overlap; the final tail is included. Low overlap is not an exclusion.
    """
    if window_words <= 0 or stride_words <= 0 or stride_words > window_words:
        raise ValueError("Require 0 < stride_words <= window_words")
    transcript = str(record.get("transcript") or "")
    abstract = str(record.get("abstract") or "")
    reference_tokens = content_tokens(abstract)
    source_tokens = content_tokens(transcript)
    matched = reference_tokens & source_tokens
    words = transcript.split()
    offsets = sorted(set(range(0, len(words), stride_words)) |
                     ({max(0, len(words) - window_words)} if words else set()))
    candidates = []
    for offset in offsets:
        excerpt = " ".join(words[offset:offset + window_words])
        hits = len(reference_tokens & content_tokens(excerpt))
        candidates.append((hits, offset, excerpt))
    # Earliest window breaks ties; avoid displaying overlapping excerpts twice.
    excerpts = []
    for hits, offset, excerpt in sorted(candidates, key=lambda row: (-row[0], row[1])):
        if hits and all(abs(offset - item["start_word"]) >= window_words for item in excerpts):
            excerpts.append({"start_word": offset, "matched_distinct_tokens": hits, "text": excerpt})
            if len(excerpts) == 2:
                break
    cues = [name for name, pattern in CUE_PATTERNS.items()
            if re.search(pattern, abstract, flags=re.IGNORECASE)]
    return {
        "normalized_abstract_sha256": text_hash(abstract),
        "abstract_prefix_sha256": text_hash(" ".join(abstract.split()[:30]))
        if len(abstract.split()) >= 40 else "",
        "normalized_transcript_sha256": text_hash(transcript),
        "reference_content_token_count": len(reference_tokens),
        "reference_token_coverage": len(matched) / len(reference_tokens) if reference_tokens else None,
        "unmatched_reference_tokens": sorted(reference_tokens - source_tokens),
        "matched_source_excerpts": excerpts,
        "reference_cues": cues,
        "full_transcript_screened": bool(words),
    }


def annotate_reference_pool(rows, low_coverage=0.25):
    """Flag only within structurally usable rows; preserve every input ID.

    The configurable 0.25 threshold is a heuristic, not a validated cutoff.
    Empty/reused references are excluded; other signals stay in the review pool.
    """
    if not 0 <= low_coverage <= 1:
        raise ValueError("Coverage threshold must be between zero and one")
    keys = [(row["split"], row["source_index"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate split/source_index")
    valid = [row for row in rows if row.get("status") == "ok"]
    abstracts = Counter(row.get("normalized_abstract_sha256") for row in valid
                        if row.get("normalized_abstract_sha256"))
    transcripts = Counter(row.get("normalized_transcript_sha256") for row in valid
                          if row.get("normalized_transcript_sha256"))
    prefixes = Counter(row.get("abstract_prefix_sha256") for row in valid
                       if row.get("abstract_prefix_sha256"))
    result = []
    for row in rows:
        abstract_hash = row.get("normalized_abstract_sha256", "")
        transcript_hash = row.get("normalized_transcript_sha256", "")
        prefix_hash = row.get("abstract_prefix_sha256", "")
        exclusions, flags = [], list(row.get("reference_cues") or [])
        if row.get("status") != "ok":
            exclusions.append("detail_scan_failed")
        if not abstract_hash:
            exclusions.append("empty_abstract")
        if abstract_hash and abstracts[abstract_hash] > 1:
            exclusions.append("reused_abstract")
        if transcript_hash and transcripts[transcript_hash] > 1:
            flags.append("exact_normalized_transcript_duplicate")
        if prefix_hash and prefixes[prefix_hash] >= 3:
            flags.append("shared_30_word_prefix_template_cue")
        if row.get("abstract_words", 0) < 30:
            flags.append("short_abstract")
        coverage = row.get("reference_token_coverage")
        if abstract_hash and not row.get("reference_content_token_count"):
            flags.append("no_informative_reference_tokens")
        if coverage is not None and coverage < low_coverage:
            flags.append("low_lexical_coverage")
        if not row.get("full_transcript_screened"):
            flags.append("full_transcript_not_screened")
        result.append({**row, "abstract_group_size": abstracts[abstract_hash] if abstract_hash else 0,
                       "transcript_group_size": transcripts[transcript_hash] if transcript_hash else 0,
                       "reference_exclusion_reasons": exclusions, "reference_review_flags": flags,
                       "broad_pool_candidate": not exclusions,
                       "screen_action": "exclude" if exclusions else "review" if flags else "keep_candidate"})
    return result


def diverse_review_sample(rows, limit=100):
    """Deterministic audit sample, never a benchmark-size cap.

    Greedily cover rare marginal split/genre/subject/duration labels first.
    Tie-break by ID. Not random or representative for prevalence estimates.
    """
    if limit < 0:
        raise ValueError("Sample limit must be nonnegative")
    def labels(row):
        minutes = row.get("duration_minutes")
        band = ("missing" if minutes is None else "<15" if minutes < 15 else
                "15-30" if minutes < 30 else "30-60" if minutes < 60 else
                "60-90" if minutes < 90 else ">=90")
        return {(field, str(row.get(field) or "(missing)")) for field in
                ("split", "genre", "subject")} | {("duration_band", band)}
    remaining = sorted(rows, key=lambda row: (row["split"], row["source_index"]))
    frequencies = Counter(label for row in remaining for label in labels(row))
    selected, covered = [], set()
    while remaining and len(selected) < limit:
        index = max(range(len(remaining)), key=lambda i: (
            sum(1 / frequencies[label] for label in labels(remaining[i]) - covered),
            bool(remaining[i].get("reference_review_flags")), -i))
        row = remaining.pop(index)
        selected.append(row)
        covered.update(labels(row))
    return selected
