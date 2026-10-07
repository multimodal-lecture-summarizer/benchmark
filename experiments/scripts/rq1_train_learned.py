"""Train frozen RQ1 C1-C6 on eight groups and score four validation groups.

This command never reads final-test media, features, or GT. Full mode uses the
predeclared three seeds and equal 35-epoch/5-patience budgets. --smoke writes
to a separate diagnostic directory and cannot be used for official selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
import torch

from benchmarks.models.chaptering import (
    ChapteringBatch, C1_TextOnlyChapterer, C2_AcousticChapterer,
    C3_VisualChapterer, C4_OCRChapterer,
    C5_TemporalCrossAttentionTransformer, C6_LateFusionChapterer,
    extract_visual_transitions,
)
from experiments.scripts.benchmark_artifacts import sha256_file
from experiments.scripts.chapter_benchmark_contract import score_chapters
from experiments.scripts.rq1_validation_precision_gate import plan_validation_precision
from experiments.scripts.rq1_learned_features import (
    DEFAULT_OUTPUT as FEATURE_DIR, REPO, SPLIT, TEXT_MODEL, TEXT_REVISION,
    VISUAL_MODEL, VISUAL_REVISION, development_sources,
    published_development_targets,
)


SEEDS = (42, 1337, 2026)
EPOCHS = 35
PATIENCE = 5
CHUNK_TOKENS = 128
DEFAULT_OUTPUT = REPO / "experiments/outputs/rq1_locked_mixed_20/learned_training"
MODEL_CODE = REPO / "benchmarks/models/chaptering.py"
ALIASES = {"C5": "C5_cross_attention", "C6": "C6_late_fusion"}


def _factory(candidate: str):
    return {
        "C1": lambda: C1_TextOnlyChapterer(d_text=384),
        "C2": lambda: C2_AcousticChapterer(d_text=384, d_ac=32),
        "C3": lambda: C3_VisualChapterer(d_text=384, d_vis=384),
        "C4": lambda: C4_OCRChapterer(d_text=384, d_ocr=384),
        "C5": lambda: C5_TemporalCrossAttentionTransformer(
            d_text=384, d_vis=384, d_ocr=384, d_ac=32,
            d_model=256, n_layers=4, n_heads=8, num_boundary_tokens=3),
        "C6": lambda: C6_LateFusionChapterer(
            d_text=384, d_vis=384, d_ocr=384, d_ac=32, d_hidden=256),
    }[candidate]


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _targets(times: torch.Tensor, boundaries: list[float]) -> torch.Tensor:
    targets = torch.zeros_like(times)
    indices = [int(torch.argmin(torch.abs(times - float(value))).item()) for value in boundaries]
    if len(indices) != len(set(indices)):
        raise ValueError("two GT boundaries map to one 2-second token")
    for index in indices:
        targets[index] = 1.0
    return targets


def load_units(feature_dir: Path) -> tuple[list[dict], list[dict], str]:
    """Verify all twelve model tensors against the locked source and split."""
    rows = development_sources()
    source_by_id = {row["unit_id"]: row for row in rows}
    gt_by_id = published_development_targets()
    if set(gt_by_id) != set(source_by_id):
        raise ValueError("published 00c development targets differ from source inputs")
    units = []
    feature_configurations = set()
    for uid, row in sorted(source_by_id.items()):
        tensor_path = feature_dir / f"{uid}.pt"
        receipt_path = feature_dir / f"{uid}.receipt.json"
        if not tensor_path.is_file() or not receipt_path.is_file():
            raise FileNotFoundError(f"missing learned features: {uid}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (receipt["unit_id"] != uid or receipt["split"] != row["split"]
                or receipt["media_sha256"] != row["media_sha256"]
                or receipt["transcript_file_sha256"] != row["transcript_file_sha256"]
                or receipt["source_feature_file_sha256"] != row["source_feature_file_sha256"]
                or receipt["split_sha256"] != sha256_file(SPLIT)
                or receipt["tensor_sha256"] != sha256_file(tensor_path)
                or receipt["extractor_sha256"] != sha256_file(
                    REPO / "experiments/scripts/rq1_learned_features.py")
                or receipt["text_model"] != TEXT_MODEL or receipt["text_revision"] != TEXT_REVISION
                or receipt["visual_model"] != VISUAL_MODEL or receipt["visual_revision"] != VISUAL_REVISION
                or receipt["ocr_model"] != "PaddleOCR ch_PP-OCRv4 confidence>=0.6"
                or set(receipt["ocr_weight_sha256"]) != {
                    f"{stage}/{name}" for stage in ("det", "rec", "cls")
                    for name in ("inference.pdmodel", "inference.pdiparams")}
                or receipt["frame_sampling"] != "1fps fallback; same frames for DINOv2 and OCR"
                or receipt.get("visual_compute") not in {"cpu", "cuda"}
                or not isinstance(receipt.get("visual_batch_size"), int)
                or receipt["visual_batch_size"] < 1
                or receipt["audio"] != "FFmpeg mono 16kHz; 32-band log-mel mean per 2s"):
            raise ValueError(f"learned tensor provenance mismatch: {uid}")
        if receipt.get("ocr_worker_sha256") is not None:
            from experiments.scripts.rq1_ocr_resume import load_cache
            if receipt["ocr_worker_sha256"] != sha256_file(
                    REPO / "experiments/scripts/rq1_ocr_resume.py"):
                raise ValueError(f"OCR worker changed: {uid}")
            _, _, manifest_sha = load_cache(
                feature_dir / "ocr_chunks" / uid, unit_id=uid,
                media_sha256=row["media_sha256"],
                duration=float(row["duration_sec"]),
                weights=receipt["ocr_weight_sha256"],
                compute=receipt["ocr_compute"])
            if manifest_sha != receipt.get("ocr_manifest_sha256"):
                raise ValueError(f"OCR cache changed: {uid}")
        feature_configurations.add((receipt["paddleocr_version"], receipt["ocr_compute"],
                                    receipt["visual_compute"], receipt["visual_batch_size"],
                                    json.dumps(receipt["ocr_weight_sha256"], sort_keys=True),
                                    json.dumps(receipt["dependencies"], sort_keys=True)))
        data = torch.load(tensor_path, map_location="cpu", weights_only=True)
        if data["unit_id"] != uid or data["split"] != row["split"]:
            raise ValueError(f"learned tensor identity mismatch: {uid}")
        length = len(data["timestamps"])
        for key, dim in (("text_features", 384), ("visual_features", 384),
                         ("ocr_features", 384), ("acoustic_features", 32)):
            feature = data[key]
            if feature.shape != (length, dim) or not torch.isfinite(feature).all():
                raise ValueError(f"invalid {key} tensor: {uid}")
        if length < 3 or not torch.all(data["timestamps"][1:] > data["timestamps"][:-1]):
            raise ValueError(f"invalid timestamps: {uid}")
        data["targets"] = _targets(data["timestamps"], gt_by_id[uid])
        units.append({"row": row, "data": data, "gt": gt_by_id[uid],
                      "tensor_sha256": receipt["tensor_sha256"]})
    train = [unit for unit in units if unit["row"]["split"] == "train"]
    validation = [unit for unit in units if unit["row"]["split"] == "validation"]
    if len(train) != 8 or len(validation) != 4:
        raise ValueError("learned features must cover exactly 8 train and 4 validation")
    if len(feature_configurations) != 1:
        raise ValueError("learned features mix model versions or compute settings")
    train_fingerprint = hashlib.sha256(json.dumps([
        {"unit_id": unit["row"]["unit_id"], "tensor_sha256": unit["tensor_sha256"],
         "gt": unit["gt"]} for unit in train], sort_keys=True).encode()).hexdigest()
    return train, validation, train_fingerprint


def _batch(data: dict, start: int, end: int, device: str, candidate: str,
           include_targets: bool = True) -> ChapteringBatch:
    modalities = {
        "text_features": {"C1", "C2", "C3", "C4", "C5", "C6"},
        "visual_features": {"C3", "C5", "C6"},
        "ocr_features": {"C4", "C5", "C6"},
        "acoustic_features": {"C2", "C5", "C6"},
    }
    length = end - start
    features = {key: data[key][start:end].unsqueeze(0).to(device)
                if candidate in allowed else None for key, allowed in modalities.items()}
    return ChapteringBatch(
        timestamps=data["timestamps"][start:end].unsqueeze(0).to(device),
        mask=torch.ones((1, length), dtype=torch.bool, device=device),
        targets=(data["targets"][start:end].unsqueeze(0).to(device)
                 if include_targets else None), **features)


def _chunks(length: int):
    for start in range(0, length, CHUNK_TOKENS):
        yield start, min(start + CHUNK_TOKENS, length)


def _validation_loss(model, units: list[dict], candidate: str, device: str) -> float:
    model.eval()
    losses = []
    with torch.inference_mode():
        for unit in units:
            data = unit["data"]
            chunk_losses = [float(model(_batch(data, start, end, device, candidate)).loss)
                            for start, end in _chunks(len(data["timestamps"]))]
            losses.append(float(np.mean(chunk_losses)))
    return float(np.mean(losses))


def train_one(candidate: str, seed: int, train: list[dict], validation: list[dict],
              device: str, epochs: int = EPOCHS, patience: int = PATIENCE):
    _seed(seed)
    model = _factory(candidate)().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best_loss, best_state, best_epoch, stale = math.inf, None, 0, 0
    for epoch in range(1, epochs + 1):
        model.train()
        for unit in train:
            data = unit["data"]
            chunks = list(_chunks(len(data["timestamps"])))
            optimizer.zero_grad(set_to_none=True)
            for start, end in chunks:
                loss = model(_batch(data, start, end, device, candidate)).loss
                (loss / len(chunks)).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        val_loss = _validation_loss(model, validation, candidate, device)
        if val_loss < best_loss - 1e-6:
            best_loss, best_epoch, stale = val_loss, epoch, 0
            best_state = {name: value.detach().cpu().clone()
                          for name, value in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is None:
        raise RuntimeError("no finite validation loss")
    model.load_state_dict(best_state)
    return model, best_state, best_loss, best_epoch


def _predict(model, unit: dict, candidate: str, device: str) -> list[float]:
    data = unit["data"]
    model.eval()
    pieces = []
    with torch.inference_mode():
        for start, end in _chunks(len(data["timestamps"])):
            output = model(_batch(data, start, end, device, candidate,
                                  include_targets=False))
            pieces.append(output.probabilities.squeeze(0).cpu())
    probabilities = torch.cat(pieces).unsqueeze(0)
    times = data["timestamps"].unsqueeze(0)
    mask = torch.ones_like(times, dtype=torch.bool)
    visual = None
    if candidate in {"C5", "C6"}:
        visual = [extract_visual_transitions(data["visual_features"], data["timestamps"])]
    return model.extract_boundaries(probabilities, times, mask, threshold=0.40,
                                    visual_transitions=visual)[0]


def run(feature_dir: Path, output: Path, device: str = "cuda", smoke: bool = False,
        preload_features: bool = False) -> dict:
    train, validation, train_fingerprint = load_units(feature_dir)
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; use --device cpu")
    if preload_features:
        # Twelve development tensors are small enough to keep resident on a Colab GPU.
        for unit in train + validation:
            data = unit["data"]
            for key in ("timestamps", "targets", "text_features", "visual_features",
                        "ocr_features", "acoustic_features"):
                data[key] = data[key].to(device)
    output = output / "smoke" if smoke else output / "full"
    output.mkdir(parents=True, exist_ok=True)
    seeds, epochs, patience = ((42,), 1, 1) if smoke else (SEEDS, EPOCHS, PATIENCE)
    configuration = {
        "schema": "rq1-learned-training-config/1",
        "status": "diagnostic_smoke" if smoke else "locked_before_validation",
        "split_sha256": sha256_file(SPLIT), "train_data_sha256": train_fingerprint,
        "feature_extractor_sha256": sha256_file(REPO / "experiments/scripts/rq1_learned_features.py"),
        "model_code_sha256": sha256_file(MODEL_CODE),
        "trainer_sha256": sha256_file(Path(__file__)),
        "text_model": [TEXT_MODEL, TEXT_REVISION],
        "visual_model": [VISUAL_MODEL, VISUAL_REVISION],
        "ocr": "PaddleOCR ch_PP-OCRv4 confidence>=0.6; same 1fps frames as visual",
        "acoustic": "FFmpeg mono 16kHz; 32-band log-mel mean per 2s",
        "grid_step_sec": 2.0, "chunk_tokens": CHUNK_TOKENS,
        "training_device": device, "preload_features": preload_features,
        "candidate_ids": ["C1", "C2", "C3", "C4", "C5", "C6"],
        "seeds": list(seeds), "epochs": epochs, "early_stop_patience": patience,
        "optimizer": {"name": "AdamW", "learning_rate": 1e-3, "weight_decay": 1e-4,
                      "gradient_clip_norm": 1.0},
        "checkpoint_selection": "minimum validation BCE; lower seed wins tie",
        "prediction_threshold": 0.4, "primary_metric": "collar_f1_3s",
        "visual_snap_postprocessing": "C5 and C6 share 45s visual-anchor snapping",
        "final_test_accessed": False,
    }
    config_path = output / "configuration.json"
    if config_path.exists():
        if json.loads(config_path.read_text(encoding="utf-8")) != configuration:
            raise ValueError("locked learned training configuration drifted")
    else:
        config_path.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    config_sha = sha256_file(config_path)
    selected, score_rows = {}, []
    for candidate in ("C1", "C2", "C3", "C4", "C5", "C6"):
        trained = []
        for seed in seeds:
            checkpoint = output / f"{candidate}.seed{seed}.pt"
            provenance_path = checkpoint.with_suffix(".provenance.json")
            if checkpoint.exists() != provenance_path.exists():
                # Only a complete, hash-bound pair can be reused. Retrain this seed.
                (checkpoint if checkpoint.exists() else provenance_path).unlink()
            if checkpoint.exists():
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                if (provenance["checkpoint_sha256"] != sha256_file(checkpoint)
                        or provenance["rq1_candidate"] != candidate
                        or provenance["seed"] != seed
                        or provenance["train_data_sha256"] != train_fingerprint
                        or provenance["locked_split_sha256"] != sha256_file(SPLIT)
                        or provenance["code_sha256"] != sha256_file(MODEL_CODE)
                        or provenance["trainer_sha256"] != sha256_file(Path(__file__))
                        or provenance["training_config_sha256"] != config_sha
                        or provenance["training_epochs_budget"] != epochs
                        or provenance["early_stop_patience"] != patience):
                    raise ValueError(f"checkpoint provenance drifted: {checkpoint}")
                model = _factory(candidate)().to(device)
                saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
                if saved["candidate"] != candidate:
                    raise ValueError(f"checkpoint candidate changed: {checkpoint}")
                model.load_state_dict(saved["state_dict"])
                val_loss, epoch = provenance["validation_loss"], provenance["best_epoch"]
                print(f"reused {candidate} seed={seed} val_loss={val_loss:.6f} epoch={epoch}")
                trained.append((val_loss, seed, checkpoint, model))
                continue
            model, state, val_loss, epoch = train_one(
                candidate, seed, train, validation, device, epochs, patience)
            checkpoint_tmp = checkpoint.with_suffix(".pt.partial")
            torch.save({"state_dict": state, "candidate": candidate}, checkpoint_tmp)
            checkpoint_tmp.replace(checkpoint)
            provenance = {
                "schema": "rq1-learned-checkpoint-provenance/1",
                "candidate": ALIASES.get(candidate, candidate),
                "rq1_candidate": candidate, "architecture": model.__class__.__name__,
                "code_sha256": sha256_file(MODEL_CODE),
                "trainer_sha256": sha256_file(Path(__file__)),
                "training_config_sha256": config_sha,
                "seed": seed, "train_dataset_id": "rq1_locked_mixed_20",
                "train_unit_ids": [unit["row"]["unit_id"] for unit in train],
                "train_course_ids": [unit["row"]["course_id"] for unit in train],
                "train_lecturer_ids": sorted({lecturer for unit in train
                                              for lecturer in unit["row"]["lecturer_ids"]}),
                "train_data_sha256": train_fingerprint,
                "train_feature_sha256": {unit["row"]["unit_id"]: unit["tensor_sha256"]
                                         for unit in train},
                "validation_unit_ids": [unit["row"]["unit_id"] for unit in validation],
                "locked_split_sha256": sha256_file(SPLIT),
                "training_epochs_budget": epochs, "early_stop_patience": patience,
                "best_epoch": epoch, "validation_loss": val_loss,
                "checkpoint_sha256": sha256_file(checkpoint),
                "selection_mode": "diagnostic_smoke" if smoke else "validation_loss_only",
                "final_test_accessed": False,
            }
            provenance_tmp = provenance_path.with_suffix(".json.partial")
            provenance_tmp.write_text(
                json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
            provenance_tmp.replace(provenance_path)
            trained.append((val_loss, seed, checkpoint, model))
            print(f"trained {candidate} seed={seed} val_loss={val_loss:.6f} epoch={epoch}")
        _, chosen_seed, chosen_path, chosen_model = min(trained, key=lambda item: (item[0], item[1]))
        selected[candidate] = {"checkpoint": str(chosen_path), "checkpoint_sha256": sha256_file(chosen_path),
                               "seed": chosen_seed, "selection_rule": "lowest validation BCE; seed tie-break"}
        for unit in validation:
            predictions = _predict(chosen_model, unit, candidate, device)
            score_rows.append({"unit_id": unit["row"]["unit_id"], "candidate": candidate,
                               "status": "run", "metrics": score_chapters(
                                   predictions, unit["gt"], unit["row"]["duration_sec"]),
                               "predicted_boundaries_sec": predictions,
                               "checkpoint_sha256": sha256_file(chosen_path)})
    selection = {"schema": "rq1-learned-selection/1", "status": "diagnostic_smoke" if smoke else "validation_scored",
                 "split_sha256": sha256_file(SPLIT), "train_data_sha256": train_fingerprint,
                 "train_unit_ids": [unit["row"]["unit_id"] for unit in train],
                 "validation_unit_ids": [unit["row"]["unit_id"] for unit in validation],
                 "final_test_accessed": False, "selected": selected}
    scores_path = output / "validation_scores.json"
    selected_path = output / "selected.json"
    if selected_path.exists() or scores_path.exists():
        if selected_path.is_file() and scores_path.is_file():
            prior = json.loads(selected_path.read_text(encoding="utf-8"))
            if (prior["selected"] != selected or prior["split_sha256"] != selection["split_sha256"]
                    or prior["train_data_sha256"] != train_fingerprint
                    or prior["validation_scores_sha256"] != sha256_file(scores_path)):
                raise ValueError("selected validation result drifted")
            return prior
        # Incomplete publication is discarded; checkpoint receipts remain valid.
        (selected_path if selected_path.exists() else scores_path).unlink()
    scores_tmp = scores_path.with_suffix(".json.partial")
    scores_tmp.write_text(json.dumps(score_rows, indent=2) + "\n", encoding="utf-8")
    scores_tmp.replace(scores_path)
    selection["validation_scores_sha256"] = sha256_file(scores_path)
    if not smoke:
        precision = plan_validation_precision(
            json.loads(SPLIT.read_text(encoding="utf-8")), score_rows)
        precision["split_sha256"] = sha256_file(SPLIT)
        precision["validation_score_receipt_sha256"] = sha256_file(scores_path)
        (output / "validation_precision.json").write_text(
            json.dumps(precision, indent=2) + "\n", encoding="utf-8")
        selection["validation_precision_status"] = precision["status"]
    selected_tmp = selected_path.with_suffix(".json.partial")
    selected_tmp.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    selected_tmp.replace(selected_path)
    return selection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", type=Path, default=FEATURE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--preload-features", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    result = run(args.feature_dir, args.output, args.device, args.smoke,
                 args.preload_features)
    print(json.dumps({"status": result["status"], "selected": result["selected"]}, indent=2))


if __name__ == "__main__":
    main()
