"""Offline Arrow metadata selection and bounded selected-row access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sanitized(value: str) -> str:
    return value.replace("<", "_").replace(">", "_")


def metadata_rows(root: Path) -> list[dict]:
    import pyarrow as pa
    import pyarrow.ipc as ipc

    rows = []
    for native in ("validation", "test"):
        directory = root / "experiments/datasets/tedlium3" / native
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        for entry in state["_data_files"]:
            path = directory / entry["filename"]
            with pa.memory_map(str(path), "r") as source:
                for batch_index, batch in enumerate(ipc.open_stream(source)):
                    required = ("id", "file", "speaker_id", "text")
                    if not set(required).issubset(batch.schema.names):
                        raise ValueError("TED Arrow lacks authoritative metadata columns")
                    # Never convert the audio column while selecting metadata.
                    for row_index, row in enumerate(batch.select(required).to_pylist()):
                        identity = str(row["id"] or "")
                        speaker = str(row["speaker_id"] or "").strip()
                        source_id = str(row["file"] or "").replace("\\", "/").rsplit("/", 1)[-1]
                        if not identity or speaker.lower() in {"", "unknown"} or not source_id:
                            raise ValueError(f"TED missing source/speaker identity: {identity}")
                        split = "final_test" if native == "test" else "validation"
                        rows.append({"dataset_id": "tedlium3", "unit_id": f"{split}:{identity}",
                                     "upstream_id": identity, "split": split, "original_split": native,
                                     "speaker_id": speaker, "talk_id": Path(source_id).stem,
                                     "source_id": source_id, "reference_text": str(row["text"] or ""),
                                     "arrow_path": path.relative_to(root).as_posix(),
                                     "arrow_batch": batch_index, "arrow_row": row_index})
    return rows


def select_ted(rows: list[dict], historical_ids: list[str], protocol: dict) -> dict:
    if len({r["unit_id"] for r in rows}) != len(rows):
        raise ValueError("TED source identities must resolve uniquely")
    if len(historical_ids) != 20 or len(set(historical_ids)) != 20:
        raise ValueError("historical TED manifest must identify exactly 20 unique units")
    by_id = {}
    for row in rows:
        by_id.setdefault(sanitized(row["unit_id"]), []).append(row)
    historical = []
    for identity in historical_ids:
        matches = by_id.get(sanitized(identity), [])
        if len(matches) != 1:
            raise ValueError(f"historical TED unit must resolve uniquely: {identity}")
        historical.append(matches[0])
    speakers = {r["speaker_id"] for r in historical}
    talks = {r["talk_id"] for r in historical}
    sources = {r["source_id"] for r in historical}
    candidates = [r for r in rows if r["speaker_id"] not in speakers and
                  r["talk_id"] not in talks and r["source_id"] not in sources]
    selected, issues, counts = [], [], {}
    for split, key, default in (("validation", "ted_validation_units", 30),
                                ("final_test", "ted_test_units", 20)):
        target = protocol.get(key, default)
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            raise ValueError(f"invalid protocol target {key}")
        candidates_split = [r for r in candidates if r["split"] == split]
        salt = protocol.get("selection_salt", "dataset-readiness-v1")
        ranked = sorted(candidates_split, key=lambda r: (
            hashlib.sha256(f"{salt}\n{r['unit_id']}".encode()).hexdigest(), r["unit_id"]))
        selected.extend(ranked[:target])
        counts[split] = {"target": target, "available": len(ranked),
                         "selected": min(target, len(ranked)),
                         "selected_speakers": len({r["speaker_id"] for r in ranked[:target]}),
                         "selected_talks": len({r["talk_id"] for r in ranked[:target]}),
                         "available_speakers": len({r["speaker_id"] for r in ranked}),
                         "available_talks": len({r["talk_id"] for r in ranked})}
        if len(ranked) < target:
            issues.append({"reason": "insufficient_unexposed_candidates", "split": split})
    for key in ("speaker_id", "talk_id", "source_id"):
        left = {r[key] for r in selected if r["split"] == "validation"}
        right = {r[key] for r in selected if r["split"] == "final_test"}
        if left & right:
            raise ValueError(f"selected native TED splits overlap on {key}")
    return {"selected": selected, "historical": historical, "issues": issues,
            "selection_status": "blocked" if issues else "selected",
            "counts": counts, "excluded_historical_speakers": sorted(speakers),
            "excluded_historical_talks": sorted(talks), "excluded_historical_sources": sorted(sources)}


def audio_bytes(root: Path, records: list[dict]):
    """Yield only requested audio rows; map each shard once and keep memory bounded."""
    import pyarrow as pa
    import pyarrow.ipc as ipc

    by_file = {}
    for row in records:
        by_file.setdefault(row["arrow_path"], []).append(row)
    for relative, wanted in by_file.items():
        lookup = {(r["arrow_batch"], r["arrow_row"]): r for r in wanted}
        with pa.memory_map(str(root / relative), "r") as source:
            for batch_index, batch in enumerate(ipc.open_stream(source)):
                for (wanted_batch, row_index), record in lookup.items():
                    if batch_index == wanted_batch:
                        if batch.column("id")[row_index].as_py() != record["upstream_id"]:
                            raise ValueError("TED Arrow row changed after selection")
                        yield record, batch.column("audio")[row_index].as_py()
