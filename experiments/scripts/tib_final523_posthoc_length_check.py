"""Post-hoc, exploratory, descriptive: is the LED - BART ROUGE-L gap a length effect? Reads only word counts, statuses and scores."""
import json
import math
import random
import statistics
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\hung\Documents\GitHub\multimodal-lecture-summarizer\benchmark")
gen = zipfile.ZipFile(ROOT / "research-data/tib-final523-generation-261024-v1/results/tib-final523-evidence-20261025T143504Z.zip")
meta = {}
for p in ("led", "bart", "lead3", "lexrank"):
    rec = json.loads(gen.read(f"selection/{p}/candidate_receipt.json"))["records"]
    meta[p] = {i: (r["delivered_words"], r["status"], r["source_stratum"]) for i, r in rec.items() if "delivered_words" in r}
rows = [json.loads(l) for l in (ROOT / "research-data/tib-final523-scoring-261024-v1/results/extracted/evidence/metrics.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
score = {}
for r in rows:
    if r["scoring_status"] == "completed" and not r["failures"]:
        score[(r["profile_id"], r["record_id"])] = r["metrics"]["rougeL_f1"]
ids = sorted(i for i in meta["led"] if all((p, i) in score for p in ("led", "bart")))
print("C n", len(ids))
d = {i: score[("led", i)] - score[("bart", i)] for i in ids}
gap = {i: meta["led"][i][0] - meta["bart"][i][0] for i in ids}


def boot(values, b=5000, seed=1):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(b))
    return means[int(0.025 * b)], means[int(0.975 * b)]


def line(name, values):
    if len(values) < 5:
        print(name, "n", len(values)); return
    lo, hi = boot(values)
    print(f"{name:55s} n={len(values):3d} mean={statistics.fmean(values):+.4f} 95%[{lo:+.4f},{hi:+.4f}]")


line("all", list(d.values()))
# length bands of LED relative to BART
for name, cond in [("LED within +-15 words of BART", lambda g: abs(g) <= 15), ("LED 15..40 words longer", lambda g: 15 < g <= 40),
                   ("LED >40 words longer", lambda g: g > 40), ("LED shorter than BART by >15", lambda g: g < -15)]:
    line(name, [d[i] for i in ids if cond(gap[i])])
# correlation of the diff with the word gap
xs, ys = [gap[i] for i in ids], [d[i] for i in ids]
mx, my = statistics.fmean(xs), statistics.fmean(ys)
cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)
print("corr(diff, word gap)", round(cov / (statistics.stdev(xs) * statistics.stdev(ys)), 3), "| slope per +100 words", round(100 * cov / statistics.variance(xs), 4))
print("mean words LED", round(statistics.fmean(meta["led"][i][0] for i in ids), 1), "BART", round(statistics.fmean(meta["bart"][i][0] for i in ids), 1))
# by LED status
for status in ("completed", "completed_with_warning"):
    line(f"LED status {status}", [d[i] for i in ids if meta["led"][i][1] == status])
warn = [i for i in ids if meta["led"][i][1] == "completed_with_warning"]
# LED truncated outputs: words near cap or token budget warnings are recorded as events; use long outputs as proxy
line("LED vs BART where LED words >= 200", [d[i] for i in ids if meta["led"][i][0] >= 200])
for s in ("short", "medium", "long"):
    line(f"stratum {s}", [d[i] for i in ids if meta["led"][i][2] == s])
# LED vs lexrank at equal-ish length is not meaningful (lexrank always ~350 words); report words
print("mean words lexrank", round(statistics.fmean(meta["lexrank"][i][0] for i in ids), 1), "lead3", round(statistics.fmean(meta["lead3"][i][0] for i in ids), 1))
# creator abstract length is unknown here (references are not shipped); report share of LED outputs <= BART words +- 15
print("share LED within +-15 of BART", round(sum(abs(gap[i]) <= 15 for i in ids) / len(ids), 3))
