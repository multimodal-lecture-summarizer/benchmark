"""Build the local, evidence-bound RQ2 sample-size EDA notebook."""

from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "experiments/notebooks/diagnostics/rq2-tib-valid-sample-size-eda.ipynb"


def main() -> None:
    cells = [
        nbformat.v4.new_markdown_cell(
            "# RQ2 TIB: sample-size and coverage EDA\n\n"
            "Historical 20/70 Lecture-cohort analysis. The current TIB scope is every pinned `train`, "
            "`valid`, and `test` record regardless of genre; do not extrapolate these scores or "
            "sample-size estimates to it.\n\n"
            "Executed locally on the pinned `valid` diagnostic cohort and the extracted "
            "Qwen v2 automatic-evaluation receipt (source ZIP SHA-256 "
            "`2b9c5a80f3c6b16eb72357f7bdb1a41c86f904ef9f11a9bf451fccea3d73ccc7`). "
            "This estimates **ROUGE-L precision for planning**, not statistical "
            "power for factuality or proof that S3 is better. No test split is read. "
            "The new chat-prompt recipe has different outputs, so v2 variance is provisional."
        ),
        nbformat.v4.new_code_cell(
            "import hashlib, json, math, statistics\n"
            "from collections import Counter\n"
            "from pathlib import Path\n"
            "import matplotlib.pyplot as plt\n"
            "import pandas as pd\n\n"
            "def find_repo(start):\n"
            "    for parent in (start, *start.parents):\n"
            "        if (parent / 'experiments/scripts/rq2-tib-valid-eda.py').exists():\n"
            "            return parent\n"
            "    raise FileNotFoundError('Run from inside the benchmark repository')\n\n"
            "ROOT = find_repo(Path.cwd().resolve())\n"
            "RECEIPT = ROOT / 'plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-diagnostic-receipt.json'\n"
            "ELIGIBLE = ROOT / 'plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-eligible-metadata.json'\n"
            "EVALUATION = ROOT / 'plans/261002-0946-rq2-controlled-summarization/rq2-v2-automatic-evaluation.json'\n"
            "receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))\n"
            "eligible_snapshot = json.loads(ELIGIBLE.read_text(encoding='utf-8'))\n"
            "evaluation_bytes = EVALUATION.read_bytes()\n"
            "assert hashlib.sha256(evaluation_bytes).hexdigest() == 'd65bf94ce198c52a093433bd62583542e3b96476f9587afb63ba843ce78552f9'\n"
            "evaluation = json.loads(evaluation_bytes)\n"
            "assert receipt['revision'] == evaluation['revision']\n"
            "assert receipt['selected_doi_sha256'] == evaluation['selection_sha256']\n"
            "assert eligible_snapshot['dataset'] == receipt['dataset']\n"
            "assert eligible_snapshot['revision'] == receipt['revision']\n"
            "assert eligible_snapshot['split'] == 'valid' and not eligible_snapshot['test_content_accessed']\n"
            "assert eligible_snapshot['selection_sha256'] == receipt['selected_doi_sha256']\n"
            "selected = pd.DataFrame(receipt['selected'])\n"
            "eligible = pd.DataFrame(eligible_snapshot['records'])\n"
            "scores = pd.DataFrame(evaluation['rows'])\n"
            "assert len(selected) == len(scores) == 20\n"
            "assert len(eligible) == eligible_snapshot['eligible_count'] == receipt['candidate_count'] == 70\n"
            "assert eligible.doi.is_unique and set(selected.doi) <= set(eligible.doi)\n"
            "assert set(selected.doi) == set(scores.doi)\n"
            "assert (scores.status == 'completed').all()\n"
            "eligible['author_key'] = eligible.author.map(lambda value: ' '.join(str(value).casefold().split()))\n"
            "assert eligible.author_key.ne('').all()\n"
            "eligible['doi_hash'] = eligible.doi.map(lambda value: hashlib.sha256(value.encode()).hexdigest())\n"
            "one_per_author = eligible.sort_values(['doi_hash', 'doi']).drop_duplicates('author_key').copy()\n"
            "assert len(one_per_author) == 52\n"
            "assert set(selected.doi) <= set(one_per_author.doi)\n"
            "print('Revision:', receipt['revision'], '| split:', receipt['split_read'])\n"
            "print('All valid:', receipt['source_count'], '| exact Lecture:', receipt['lecture_count'],\n"
            "      '| structurally eligible:', len(eligible), '| unique authors:', len(one_per_author),\n"
            "      '| selected:', len(selected))\n"
            "print('Selection:', receipt['selection'])\n"
            "print('V2 evaluation SHA-256:', hashlib.sha256(evaluation_bytes).hexdigest())"
        ),
        nbformat.v4.new_markdown_cell(
            "## What the 20 cases cover\n\n"
            "The original selector chose the first 20 eligible DOI hashes with one normalized "
            "author per item. It did not stratify by `subject`, length, or abstract quality. "
            "The executed export now includes metadata for all 70 structurally eligible talks. "
            "A deterministic one-per-author extension contains 52 talks and retains the original 20. "
            "This is a candidate cohort, not a frozen formal endpoint. "
            "The existing abstract screen is a provisional editorial screen, not verified ground truth."
        ),
        nbformat.v4.new_code_cell(
            "SCREEN = ROOT / 'plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-reference-screen.json'\n"
            "screen = json.loads(SCREEN.read_text(encoding='utf-8'))\n"
            "assert screen['revision'] == receipt['revision'] and screen['split'] == 'valid'\n"
            "selected['doi_id'] = selected.doi.str.extract(r'/(\\d+)')[0]\n"
            "selected['reference_screen'] = selected.doi_id.map(lambda d: screen['items'][d]['screen'])\n"
            "subjects = pd.concat([eligible.subject.value_counts().rename('eligible_70'),\n"
            "                      one_per_author.subject.value_counts().rename('one_author_52'),\n"
            "                      selected.subject.value_counts().rename('selected_20')], axis=1).fillna(0).astype(int)\n"
            "subjects.index.name = 'subject'\n"
            "subjects['eligible_pct'] = 100 * subjects.eligible_70 / len(eligible)\n"
            "subjects['selected_pct'] = 100 * subjects.selected_20 / len(selected)\n"
            "print('Subject distribution: eligible vs author-distinct extension vs original 20')\n"
            "display(subjects.round(1))\n"
            "print('Subject × provisional abstract screen:')\n"
            "display(pd.crosstab(selected.subject, selected.reference_screen))\n"
            "print('Abstract screen totals:', selected.reference_screen.value_counts().to_dict())\n"
            "for name, frame in [('eligible_70', eligible), ('one_author_52', one_per_author), ('selected_20', selected)]:\n"
            "    print(name, 'short abstracts', int((frame.abstract_words < 30).sum()), '/', len(frame),\n"
            "          '| words median', int(frame.transcript_words.median()),\n"
            "          '| words max', int(frame.transcript_words.max()),\n"
            "          '| duration median min', round(frame.duration_minutes.median(), 1))\n"
            "fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))\n"
            "subjects[['eligible_pct', 'selected_pct']].plot.barh(ax=axes[0], title='Subject share (%)')\n"
            "eligible.transcript_words.hist(ax=axes[1], bins=10, alpha=.55, label='eligible 70')\n"
            "selected.transcript_words.hist(ax=axes[1], bins=10, alpha=.65, label='selected 20')\n"
            "axes[1].legend(); axes[1].set(title='Transcript length', xlabel='Words')\n"
            "fig.tight_layout(); plt.show()"
        ),
        nbformat.v4.new_markdown_cell(
            "## Paired-score variability and precision scenarios\n\n"
            "The unit is a DOI pair, with delta = S3 minus S1 ROUGE-L. The table uses "
            "`1.96 × pilot SD / sqrt(n)` as a **planning approximation** to a 95% "
            "half-width. It assumes future independent talks have similar delta variance; "
            "that assumption has not been validated. It does not repair noisy abstracts."
        ),
        nbformat.v4.new_code_cell(
            "delta = scores.delta_S3_minus_S1.astype(float)\n"
            "sd = statistics.stdev(delta)\n"
            "mean = statistics.mean(delta)\n"
            "ci = evaluation['paired_rouge']['ci95']\n"
            "print('Observed n:', len(delta), '| mean delta:', round(mean, 5), '| SD:', round(sd, 5))\n"
            "print('Saved paired-bootstrap 95% CI:', [round(x, 5) for x in ci])\n"
            "print('S3 / S1 / tie:', int((delta > 0).sum()), '/', int((delta < 0).sum()), '/', int((delta == 0).sum()))\n"
            "scenarios = pd.DataFrame([{'n': n, 'approx_95pct_half_width': 1.96 * sd / math.sqrt(n)}\n"
            "                          for n in [20, 30, 40, 50, 52, 60, 70]])\n"
            "display(scenarios.round(5))\n"
            "for width in [0.01, 0.005]:\n"
            "    needed = math.ceil((1.96 * sd / width) ** 2)\n"
            "    print(f'Target ±{width:.3f} ROUGE-L -> about {needed} independent pairs under v2 variance')\n"
            "fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))\n"
            "delta.hist(ax=axes[0], bins=8); axes[0].axvline(0, color='black', linestyle='--')\n"
            "axes[0].set(title='20 paired ROUGE-L deltas', xlabel='S3 − S1')\n"
            "scenarios.plot(x='n', y='approx_95pct_half_width', marker='o', ax=axes[1], legend=False)\n"
            "axes[1].axhline(0.01, color='darkred', linestyle='--')\n"
            "axes[1].set(title='Illustrative precision', ylabel='Approx. 95% half-width')\n"
            "fig.tight_layout(); plt.show()"
        ),
        nbformat.v4.new_markdown_cell(
            "## Decision and missing evidence\n\n"
            "- **20** is justified as a deterministic development diagnostic, not a representative research sample. "
            "It misses Engineering entirely, includes only 2 of 15 Physics talks, and does not include "
            "the eligible set's longest talks (20,409 versus 12,131 words).\n"
            "- Under v2 ROUGE-L variability, **about 50 independent pairs** would give an approximate "
            "95% half-width of ±0.01. The deterministic **52 distinct-author** candidate set "
            "covers all eight observed subject tags and gives about ±0.0098; all **70 talks** "
            "would give about ±0.0084 only if they were independent. These are planning "
            "figures, not mandatory cutoffs. At ±0.005, the approximation needs about 200 "
            "pairs, more than the 70 structurally eligible exact-Lecture talks.\n"
            "- The selected 20 used a raw-prompt, 96/384-token recipe; the chat pilot changed "
            "prompt and budgets. Re-estimate variability after running the frozen recipe.\n"
            "- All 70 metadata rows are now available. The 52 unique-author items are a practical "
            "extension proposal, not guaranteed independent lectures: check cross-split series overlap, "
            "actual Qwen source-token limits, and reference mix before freezing or running all cases. "
            "Keep reference quality and "
            "source-grounded errors separate from ROUGE precision.\n"
            "- Do not use sealed test content to choose sample size or tune the recipe."
        ),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells, metadata={"kernelspec": {
        "display_name": "Python 3", "language": "python", "name": "python3"}})
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
