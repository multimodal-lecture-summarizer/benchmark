"""Bounded-memory source text fingerprints and evidence-confirmed groups."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
from numba import njit

HASH_KEY = "tibsrcgroupv0001"


def canonical(value):
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split())


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def words(value):
    return re.findall(r"\b\w+\b", canonical(value).casefold())


def shingles(value):
    tokens = words(value)
    return {" ".join(tokens[i:i + 5]) for i in range(max(0, len(tokens) - 4))}


def fingerprints(value):
    # Only one record's string shingle set is resident during fingerprinting.
    grams = np.asarray(sorted(shingles(value)), dtype=object)
    return np.unique(pd.util.hash_array(grams, hash_key=HASH_KEY))


def url_key(value):
    parsed = urlsplit(str(value or "").strip())
    return parsed.netloc.casefold() + parsed.path.rstrip("/").casefold() if parsed.netloc else ""


@njit(cache=True)
def intersection_count(left, right):
    """Linear merge of sorted unique uint64 arrays; same count as intersect1d."""
    a, b, shared = 0, 0, 0
    while a < len(left) and b < len(right):
        if left[a] == right[b]:
            shared += 1
            a += 1
            b += 1
        elif left[a] < right[b]:
            a += 1
        else:
            b += 1
    return shared


def overlap(left, right):
    shared = int(intersection_count(left, right))
    return stats(shared, len(left), len(right))


def stats(shared, left, right):
    union = left + right - shared
    return {"shared_fivegrams": shared, "left_fivegrams": left,
            "right_fivegrams": right, "jaccard": shared / union if union else 0.,
            "containment_shorter": shared / min(left, right) if min(left, right) else 0.}


def near_pass(evidence, policy):
    return evidence["shared_fivegrams"] >= policy["minimum_shared_fivegrams"] and (
        evidence["jaccard"] >= policy["jaccard_threshold"] or
        evidence["containment_shorter"] >= policy["containment_threshold"])


def confirm_pair(left, right, left_fp, right_fp, policy):
    reasons = [field for field in ("doi", "source_url", "video_url")
               if left[field] and left[field] == right[field]]
    if left["source_normalized"] and left["source_normalized"] == right["source_normalized"]:
        reasons.append("exact_normalized_transcript")
    evidence = overlap(left_fp, right_fp)
    if near_pass(evidence, policy):
        a, b = shingles(left["source_normalized"]), shingles(right["source_normalized"])
        evidence = stats(len(a & b), len(a), len(b))
        if near_pass(evidence, policy):
            reasons.append("confirmed_near_transcript")
    return evidence | {"accepted": bool(reasons), "reasons": reasons}


def component_ledger(rows, edges):
    parent = {row["record_id"]: row["record_id"] for row in rows}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for left, right in edges:
        a, b = find(left), find(right)
        parent[max(a, b)] = min(a, b)
    members = {}
    for key in sorted(parent):
        members.setdefault(find(key), []).append(key)
    groups = {key: "tib-source-" + digest("\n".join(ids))[:24]
              for key, ids in members.items()}
    return [{k: v for k, v in row.items() if k != "source_normalized"} |
            {"group_id": groups[find(row["record_id"])],
             "group_size": len(members[find(row["record_id"])])}
            for row in sorted(rows, key=lambda item: item["record_id"])]
