"""ASR preprocessing ablation runner for notebook 01b (smoke/full)."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Sequence

from experiments.evaluation.metrics import rtf
from experiments.evaluation.asr_selection_scoring import (
    require_selection_metadata, score_asr_pairs, selection_metadata, validation_units,
)
from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
    require_media,
)

# ---------------------------------------------------------------------------
# Ablation toggle definitions
# ---------------------------------------------------------------------------
# Each toggle is a named configuration axis.  In smoke profile we run a
# minimal cross of the frozen shortlist model against two decoding toggles
# so the runner always emits at least two ablation rows and can rank them.
# ---------------------------------------------------------------------------

_DECODING_PRESETS_SMOKE = [
    {"name": "default_greedy", "beam_size": 1, "temperature": 0.0},
    {"name": "beam5", "beam_size": 5, "temperature": 0.0},
]

_DECODING_PRESETS_FULL = [
    {"name": "default_greedy", "beam_size": 1, "temperature": 0.0},
    {"name": "beam5", "beam_size": 5, "temperature": 0.0},
    {"name": "beam5_temp0.2", "beam_size": 5, "temperature": 0.2},
]


class UnsupportedShortlistCandidate(RuntimeError):
    def __init__(self, candidate: str):
        self.candidate = candidate
        super().__init__(f"01b has no exact adapter for selected candidate {candidate!r}")


def _resolve_shortlisted_model(context, units: list[dict[str, Any]]) -> str:
    """Return the model name selected by the upstream ASR shortlist."""
    payload = read_json_artifact(context, "asr.shortlist")
    records = payload["records"]
    if not records:
        raise RuntimeError("asr.shortlist has no records")
    for record in records:
        require_selection_metadata(record, units)
    selected = [record for record in records if record.get("selected") is True]
    if len(selected) != 1:
        raise RuntimeError("asr.shortlist requires exactly one selected validation candidate")
    candidate = selected[0].get("candidate")
    if candidate not in {"faster-whisper-tiny.en", "faster-whisper-base.en"}:
        raise UnsupportedShortlistCandidate(str(candidate))
    return candidate.removeprefix("faster-whisper-")


def _transcribe(path, model_size: str, beam_size: int, temperature: float) -> tuple[str, float]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    started = time.perf_counter()
    segments, _info = model.transcribe(
        str(path),
        language="en",
        beam_size=beam_size,
        temperature=temperature,
    )
    hypothesis = " ".join(segment.text.strip() for segment in segments).strip()
    wall = time.perf_counter() - started
    if not hypothesis:
        raise RuntimeError(
            f"{model_size}@beam={beam_size} produced an empty transcript for {path.name}"
        )
    return hypothesis, wall


def _audio_duration_sec(path) -> float:
    try:
        import wave

        with wave.open(str(path), "rb") as handle:
            return float(handle.getnframes()) / float(handle.getframerate())
    except Exception:
        try:
            import subprocess

            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                text=True,
            )
            return float(out.strip())
        except Exception as exc:
            raise RuntimeError(f"unable to measure audio duration for {path}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "01b_asr_preprocessing_ablation", argv)
        units = validation_units(load_eligible_units(context, limit_smoke=False))
        if context.profile == "smoke":
            units = units[:1]
        selection = selection_metadata(units)
        try:
            model_size = _resolve_shortlisted_model(context, units)
        except UnsupportedShortlistCandidate as exc:
            context = replace(context, status="partial")
            blocked = {"candidate": exc.candidate,
                       "status": "blocked_unsupported_candidate",
                       "reason": str(exc), **selection}
            write_json_artifact(context, "asr.ablation_predictions", [{
                **blocked, "model_loaded": False, "execution_mode": "not_run",
            }])
            write_json_artifact(context, "asr.ablation_metrics", [{
                **blocked, "metrics": None, "edit_counts": None,
            }])
            write_json_artifact(context, "asr.frozen_configuration", [{
                **blocked, "frozen_model": None, "frozen_toggle": None,
            }])
            write_run_manifest(context)
            print(f"[PARTIAL] asr preprocessing ablation: {blocked['status']} ({exc.candidate})")
            return 2

        presets = (
            _DECODING_PRESETS_SMOKE
            if context.profile == "smoke"
            else _DECODING_PRESETS_FULL
        )

        ablation_predictions: list[dict[str, Any]] = []
        ablation_metrics: list[dict[str, Any]] = []
        pairs_by_toggle: dict[str, list[tuple[str, str]]] = {}

        for unit in units:
            media = require_media(unit, "media_path", "audio_path", "path")
            reference = str(unit.get("reference_text") or "").strip()
            if not reference:
                raise RuntimeError(f"unit {unit['unit_id']!r} missing reference_text")
            duration = _audio_duration_sec(media)

            for preset in presets:
                toggle_name: str = preset["name"]
                hypothesis, wall = _transcribe(
                    media,
                    model_size,
                    beam_size=int(preset["beam_size"]),
                    temperature=float(preset["temperature"]),
                )
                scores = score_asr_pairs([(reference, hypothesis)])
                metrics: dict[str, float] = {
                    "corpus_wer": float(scores["wer"]),
                    "cer": float(scores["cer"]),
                    "rtf": float(rtf(duration, wall)),
                }
                ablation_predictions.append(
                    {
                        "unit_id": unit["unit_id"],
                        "split": "validation",
                        **selection,
                        "dataset_id": unit.get("dataset_id"),
                        "ablation_toggle": toggle_name,
                        "model": model_size,
                        "predictions": {
                            "hypothesis": hypothesis,
                            "reference": reference,
                            "media_path": media.as_posix(),
                            "beam_size": preset["beam_size"],
                            "temperature": preset["temperature"],
                        },
                        "model_loaded": True,
                        "execution_mode": "real",
                    }
                )
                ablation_metrics.append(
                    {
                        "unit_id": unit["unit_id"],
                        "split": "validation",
                        **selection,
                        "ablation_toggle": toggle_name,
                        "model": model_size,
                        "metrics": metrics,
                        "edit_counts": scores,
                    }
                )
                pairs_by_toggle.setdefault(toggle_name, []).append((reference, hypothesis))

        # Frozen configuration: select the toggle with lowest corpus WER
        toggle_wer: dict[str, float] = {
            toggle: float(score_asr_pairs(pairs_by_toggle[toggle])["wer"])
            for toggle in pairs_by_toggle
        }
        best_toggle = min(toggle_wer, key=lambda k: toggle_wer[k])
        best_preset = next(p for p in presets if p["name"] == best_toggle)

        frozen_configuration = [
            {
                "frozen_model": model_size,
                "frozen_toggle": best_toggle,
                "frozen_beam_size": best_preset["beam_size"],
                "frozen_temperature": best_preset["temperature"],
                "selection_corpus_wer": toggle_wer[best_toggle],
                **selection,
                "selection_edit_counts": score_asr_pairs(pairs_by_toggle[best_toggle]),
                "toggle_wer_table": [
                    {"toggle": k, "corpus_wer": v} for k, v in sorted(toggle_wer.items())
                ],
            }
        ]

        write_json_artifact(context, "asr.ablation_predictions", ablation_predictions)
        write_json_artifact(context, "asr.ablation_metrics", ablation_metrics)
        write_json_artifact(context, "asr.frozen_configuration", frozen_configuration)
        write_run_manifest(context)
        print(
            f"[OK] asr preprocessing ablation: {len(units)} unit(s), "
            f"{len(presets)} toggle(s), frozen={best_toggle}"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] asr preprocessing ablation: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
