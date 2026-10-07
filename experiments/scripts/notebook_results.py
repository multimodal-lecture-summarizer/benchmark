"""Render artifact-backed tables and figures; never infer benchmark success."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.scripts.benchmark_artifacts import (
    RunnerContext, read_json_artifact, sha256_file, validated_payload_path,
)


def context_from_environment_record(record: dict[str, str]) -> RunnerContext:
    return RunnerContext(
        profile=record["MLS_BENCHMARK_PROFILE"], run_namespace=record["MLS_RUN_NAMESPACE"],
        status=record["MLS_EVIDENCE_STATUS"], artifact_root=Path(record["MLS_ARTIFACT_ROOT"]),
        notebook_id=record["MLS_NOTEBOOK_ID"], run_id=record["MLS_RUN_ID"],
        source_sha256=record["MLS_SOURCE_SHA256"], config_sha256=record["MLS_CONFIG_SHA256"],
        dependency_state_sha256=record["MLS_DEPENDENCY_STATE_SHA256"],
        evaluation_mode=record.get("MLS_ASR_EVALUATION_MODE") or None,
    )


def render_artifacts(context: RunnerContext, artifact_ids: list[str], limit: int = 20) -> None:
    """Display only receipt-validated data, with explicit row counts and provenance."""
    import pandas as pd
    from IPython.display import Image, Markdown, SVG, display

    display(Markdown(
        f"### Saved evidence — `{context.notebook_id}`\n\n"
        f"Namespace: `{context.run_namespace}/{context.profile}`. "
        "Tables show artifact contents; execution alone does not establish scientific eligibility."
    ))
    for artifact_id in artifact_ids:
        path, receipt = validated_payload_path(context, artifact_id)
        display(Markdown(f"#### `{artifact_id}`"))
        if path.suffix == ".md":
            if sha256_file(path) != receipt["sha256"]:
                raise ValueError(f"{artifact_id}: text payload checksum mismatch")
            display(Markdown(path.read_text(encoding="utf-8")))
            continue
        if path.suffix in {".csv", ".tsv"}:
            table = pd.read_csv(path, sep="\t" if path.suffix == ".tsv" else ",")
            if len(table) != receipt["record_count"]:
                raise ValueError(f"{artifact_id}: table record_count mismatch")
            display(Markdown(f"{len(table)} rows; displaying at most {limit}."))
            display(table.head(limit))
            continue
        payload = read_json_artifact(context, artifact_id)
        rows = payload["records"]
        display(Markdown(
            f"{len(rows)} rows; displaying at most {limit}. "
            f"Run `{receipt['run_id']}`; SHA-256 `{receipt['sha256']}`."
        ))
        if payload.get("metadata"):
            display(pd.json_normalize(payload["metadata"]))
        # Large nested arrays belong in raw artifacts; do not flood a notebook cell.
        compact = [{k: (f"[{len(v)} records]" if isinstance(v, list) else v)
                    for k, v in row.items()} for row in rows[:limit]]
        display(pd.json_normalize(compact))
        if artifact_id == "dataset.figure_manifest":
            for row in rows:
                if row.get("plot_config", {}).get("render_status") == "not_rendered":
                    display(Markdown(f"**PENDING — {row['figure_id']}**: universal EDA plot not rendered; not scientific figure evidence."))
                    continue
                figure = (context.artifact_root / row["path"]).resolve()
                figure.relative_to(context.artifact_root.resolve())
                if sha256_file(figure) != row["sha256"]:
                    raise ValueError(f"figure checksum mismatch: {row['figure_id']}")
                display(Markdown(f"**{row['dataset_id']} — {row['figure_id']}**, n={row['n']}"))
                display(SVG(filename=str(figure)) if figure.suffix == ".svg"
                        else Image(filename=str(figure)))
