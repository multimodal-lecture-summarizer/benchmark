---
title: One notebook workspace and in-place results
status: complete
---

# Outcome

Keep every active `.ipynb` under the nested application's `experiments/notebooks/`. Running a notebook through the benchmark executor saves outputs in that same notebook, so the file opened in the editor displays the result. Do not silently relabel an old run as current.

## Scope

1. The official executor defaults to in-place output. Preserve an explicit separate `--output-root` compatibility option for existing callers and tests. Its source identity is based on stable notebook code and contract metadata, independent of output cells. Resume checks both that identity and the saved notebook bytes; new runs clear prior output cells and save errors for inspection without promoting failed evidence.
2. The generator compares only generated code/contract structure; if code is unchanged it retains saved outputs. If code changes it refreshes the notebook, dropping stale outputs. Add focused regressions for generation, execution, resume, code drift and failure persistence.
3. Diagnostic notebook executor also saves to its source by default and retains a separate-output compatibility option. Migrate the three latest verified diagnostic runs into their source files only when code cells match exactly. Expose one obvious run entrypoint in `experiments/notebooks/` or documented command for VS Code.
4. Inventory duplicate notebooks by normalized code and output identity. Remove byte-identical legacy copies. Preserve unique historical notebooks and receipt-backed execution evidence in a single archive outside the active `.ipynb` tree before deleting prior `.ipynb` copies. Keep archive manifest with original path, SHA-256 and status. Do not remove data/artifacts, alter earlier result values, or touch unrelated dirty files.
5. Update repo README and benchmark docs to name the canonical folder and explain how to run and find outputs. Existing links to historical executed copies must point to the archive manifest or new canonical notebook as appropriate.
6. Verify the selected active notebook (00b) by a fresh scoped diagnostic run if inputs permit; never copy old output into changed code. Verify every remaining `.ipynb` lives under the canonical tree, or explicitly retain a justified exception. Check final notebook displays and run focused tests.

## Plan review additions

- Add a single `experiments/notebooks/run_experiments.ipynb` launcher for VS Code `Run All`. It invokes the manifest executor with frozen local defaults and shows the exact canonical result paths. The 22 generated stage notebooks continue to require executor context; their overview points to the launcher. Test the launcher in a fresh diagnostic smoke namespace.
- Each canonical stage file shows the latest run only; its visible run context includes profile, namespace, dataset filter and run ID. Earlier variant results are kept in a verified archive and do not become fresh official evidence.
- The cleanup is manifest-driven. The archive index records original path, byte SHA-256, status and archive member; verify full extraction and hashes before deleting files. Include prior `.run.json` receipts. Keep artifact files in place and record their path in the index.
- In-place writes are atomic and retain partial failure outputs with a clear failed status. A successful run receipt is written only after artifact validation; failed output cannot be resumed as valid evidence. Test fresh run, resume, code drift, and failure.
- Keep artifact roots and dataset scope claims outside `experiments/notebooks/`, keyed by dataset/profile/namespace. Switching TED-LIUM and IIIT on the single 00b file must fail closed against stale output yet allow a fresh run under the new dataset identity. Test switching explicitly.

## Evidence / boundaries

Current inventory: 22 active source notebooks with zero outputs, three diagnostic sources with verified matching executed code, 16 executed copies under `outputs/executed_notebooks`, three separate smoke-audit executed copies, six exact legacy duplicate pairs and unique legacy notebooks. Existing `.run.json` receipts and scientific artifacts must not be mistaken for a new run after migration. No candidate expansion or model inference.

## Completion evidence — 2026-09-26

- `experiments/notebooks/` now holds all 27 runnable `.ipynb` files: 22 stage notebooks, three existing diagnostics, the consolidation record, and the VS Code launcher. No `.ipynb` remains elsewhere under `experiments/`.
- The tracked `experiments/notebook_history_20260926.zip` holds 66 historical notebook/receipt files. Its external and embedded manifest agree, all entries have unique original paths, CRC and every SHA-256 check pass. Historical output files were removed only after the archive passed verification.
- Matching diagnostic outputs were migrated into the three canonical notebooks. A fresh diagnostic group-00 execution through `run_experiments.ipynb` completed successfully: `00a` 11, `00b` 11 and `00c` 48 saved output blocks; `00b` run metadata says `validated`.
- The consolidation notebook records the focused regression run: 51 passed, including in-place execution/resume, generator preservation, dataset switching, error persistence and interrupted cleanup. `git diff --check` returned 0.
- This is a notebook-location and evidence-access repair. It does not establish Phase 1/2 scientific completeness or execute ASR candidates.
