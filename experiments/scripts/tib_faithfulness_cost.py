"""Choose a published faithfulness metric and measure its scoring cost (train sources only).

Only published packages are used (AlignScore, MiniCheck, SummaC) through their
documented interfaces. The loaders install nothing; a family that cannot load is
reported as unavailable with its error. The analysis functions are pure and
tested without any model.
"""
from __future__ import annotations

import json
import random
import statistics
from importlib import metadata
from pathlib import Path

from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from experiments.scripts import tib_summary_constructors as build

CRITERIA_PATH = Path(__file__).resolve().parents[1] / (
    "registry/protocols/tib-reference-free-multilength-261022-v1/crossfamily_criteria.json")
EXTRACT_GROUPS = ("lead", "uniform", "random")
ALL_GROUPS = EXTRACT_GROUPS + ("offtopic", "corrupted")
PROJECTION_SUMMARIES = 12000


def load_criteria() -> dict:
    return json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))


# ---- summaries -------------------------------------------------------------------

def select_subset(sample: list[dict], per_tertile: int) -> list[dict]:
    """First records of each tertile in the sample ordering."""
    seen: dict[str, int] = {}
    chosen = []
    for rec in sample:
        if seen.get(rec["tertile"], 0) < per_tertile:
            chosen.append(rec)
            seen[rec["tertile"]] = seen.get(rec["tertile"], 0) + 1
    return chosen


def build_rows(subset: list[dict], full_sample: list[dict], budget: int, seed: int) -> list[dict]:
    """One row per (record, group). Off-topic partners follow the sample ordering."""
    position = {rec["id"]: i for i, rec in enumerate(full_sample)}
    rows = []
    for rec in subset:
        partner = full_sample[(position[rec["id"]] + 1) % len(full_sample)]
        sentences = build.split_sentences(rec["text"])
        lead = build.lead(rec["text"], budget)
        groups = {
            "lead": lead,
            "uniform": build.uniform(sentences, budget),
            "random": build.random_pick(sentences, budget, random.Random(f"{seed}:{rec['id']}:faith")),
            "offtopic": build.lead(partner["text"], budget),
            "corrupted": (lead + " " + build.foreign_sentences(
                build.split_sentences(partner["text"]), 3)).strip(),
        }
        for name, summary in groups.items():
            rows.append({"record_id": rec["id"], "group": name, "summary": summary, "source": rec["text"]})
    return rows


# ---- analysis (pure) ---------------------------------------------------------------

def _pairs(rows, scores):
    return [(r, s) for r, s in zip(rows, scores) if s is not None]


def known_group_auroc(rows, scores) -> float | None:
    usable = [(r, s) for r, s in _pairs(rows, scores) if r["group"] in EXTRACT_GROUPS + ("offtopic",)]
    labels = [1 if r["group"] in EXTRACT_GROUPS else 0 for r, _ in usable]
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, [s for _, s in usable]))


def corruption_share(rows, scores) -> float | None:
    by_record: dict[str, dict] = {}
    for row, score in _pairs(rows, scores):
        by_record.setdefault(row["record_id"], {})[row["group"]] = score
    both = [g for g in by_record.values() if "lead" in g and "corrupted" in g]
    if not both:
        return None
    return sum(1 for g in both if g["lead"] > g["corrupted"]) / len(both)


def _spearman(xs, ys) -> float | None:
    if len(xs) < 3:
        return None
    rho = spearmanr(xs, ys)[0]
    return None if rho != rho else float(rho)


def pairwise_spearman(scores_by_family: dict[str, list]) -> dict[str, float | None]:
    names = sorted(scores_by_family)
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs = [(x, y) for x, y in zip(scores_by_family[a], scores_by_family[b])
                     if x is not None and y is not None]
            out[f"{a}|{b}"] = _spearman([p[0] for p in pairs], [p[1] for p in pairs])
    return out


def project_cost(seconds_per_summary: float, summaries: int = PROJECTION_SUMMARIES) -> dict:
    return {"summaries": summaries, "seconds_per_summary": seconds_per_summary,
            "projected_gpu_hours": seconds_per_summary * summaries / 3600}


def analyze(rows, scores_by_family: dict[str, list], criteria: dict, timing: dict | None = None) -> dict:
    per_family = {}
    for name, scores in scores_by_family.items():
        auroc = known_group_auroc(rows, scores)
        share = corruption_share(rows, scores)
        per_family[name] = {
            "G1_auroc": auroc, "G1_pass": auroc is not None and auroc >= 0.95,
            "G2_share": share, "G2_pass": share is not None and share >= 0.90,
            "scored": sum(1 for s in scores if s is not None), "total": len(scores),
        }
        if timing and name in timing:
            per_family[name]["cost"] = project_cost(timing[name]["seconds_per_summary"])
            per_family[name]["timing"] = timing[name]
    tests = {"per_family": per_family}
    if len(scores_by_family) >= 2:
        pair = pairwise_spearman(scores_by_family)
        values = [v for v in pair.values() if v is not None]
        median = statistics.median(values) if values else None
        tests["G3_cross_family"] = {"pairwise_spearman": pair, "median": median,
                                    "pass": median is not None and median >= 0.60}
    else:
        tests["G3_cross_family"] = {"pass": None, "note": "fewer than two families ran"}
    tests["admissible_pending_cost_approval"] = [
        name for name, result in per_family.items() if result["G1_pass"] and result["G2_pass"]]
    return tests


# ---- published families (installed by the notebook) ------------------------------------

def _version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def load_alignscore(device: str = "cuda:0"):
    from alignscore import AlignScore
    from huggingface_hub import hf_hub_download
    checkpoint = "AlignScore-base.ckpt"
    path = hf_hub_download("yzha/AlignScore", checkpoint)
    scorer = AlignScore(model="roberta-base", batch_size=16, device=device,
                        ckpt_path=path, evaluation_mode="nli_sp")
    info = {"package": _version("alignscore"), "checkpoint": f"yzha/AlignScore/{checkpoint}"}
    return (lambda source, summary: float(scorer.score(contexts=[source], claims=[summary])[0])), info


def load_minicheck(device: str = "cuda:0"):
    from minicheck.minicheck import MiniCheck
    name = "roberta-large"
    try:
        scorer = MiniCheck(model_name=name, cache_dir="./ckpts")
    except TypeError:
        scorer = MiniCheck(model_name=name, device=device, cache_dir="./ckpts")
    info = {"package": _version("minicheck"), "model_name": name}

    def score(source, summary):
        claims = build.split_sentences(summary) or [summary]
        _, probs, _, _ = scorer.score(docs=[source] * len(claims), claims=claims)
        return float(sum(probs) / len(probs))

    return score, info


def load_summac(device: str = "cuda"):
    from summac.model_summac import SummaCZS
    model = SummaCZS(granularity="sentence", model_name="vitc", device=device)
    info = {"package": _version("summac"), "model_name": "vitc", "granularity": "sentence"}
    return (lambda source, summary: float(model.score([source], [summary])["scores"][0])), info


LOADERS = {"AlignScore": load_alignscore, "MiniCheck": load_minicheck, "SummaC": load_summac}


def load_families(names=None):
    """Return (available {name: (score_fn, info)}, errors {name: message})."""
    available, errors = {}, {}
    for name in names or LOADERS:
        try:
            available[name] = LOADERS[name]()
        except Exception as exc:  # report, never substitute another family
            errors[name] = f"{type(exc).__name__}: {exc}"
    return available, errors
