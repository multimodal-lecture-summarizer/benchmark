---
phase: 2
title: "Audio Modality Figures for TED-LIUM"
status: completed
priority: P1
dependencies: []
effort: "4-6 hours"
completed: 2026-09-26
---

# Phase 2: Audio Modality Figures for TED-LIUM

## Overview

Sinh 4-6 audio modality-specific figures từ 20 WAV đã freeze trong TED-LIUM D2 subset, đóng deferred criterion #7 của master plan Phase 2 ("modality-specific figure for audio applicable"). Figures phải reproducible từ unit-level metadata, có source-table hash, revision, scope, split, `n`, unit, exclusion policy trong `figure_manifest.json`.

## Requirements

- **Functional**: ≥ 4 audio figures emitted dưới `experiments/outputs/phase2_tedlium_d2/official/full/figures/audio/`; mỗi figure có metadata file (.json) kèm source table hash + code revision.
- **Non-functional**: chỉ dùng `soundfile` + `numpy` (đã có trong requirements.freeze.txt); không cần thêm dependency; figures phải nhỏ (< 200 KB mỗi cái); không lưu raw waveform trong figure (chỉ lưu aggregated statistics).
- **Contract preservation**: TED-LIUM frozen_manifest SHA-256 không đổi (phase này chỉ emit thêm figures, không đụng đến frozen artifacts).

## Architecture

Driver mới: `experiments/scripts/emit_audio_modality_figures.py`.

Workflow:
1. Load `dataset.unit_profile.json` từ `phase2_tedlium_d2/official/full/payloads/`.
2. Cho mỗi unit, đọc WAV metadata bằng `soundfile.info()` (duration, sample rate, channels, subtype, frames).
3. Aggregate: per-unit dictionary `{unit_id, duration_sec, sample_rate_hz, channels, bit_depth, peak_db, rms_db, speech_ratio_proxy}`.
4. Sinh 6 figures:
   - `audio_duration_ecdf.png` — ECDF of unit duration (giây), n=20.
   - `audio_sample_rate_distribution.png` — bar chart sample rate (Hz) theo count.
   - `audio_channel_layout.png` — pie chart channels (mono/stereo).
   - `audio_peak_rms_distribution.png` — scatter peak_db vs rms_db, colored by split.
   - `audio_speech_ratio_distribution.png` — histogram speech ratio proxy (=1 - silence_ratio; silence = frames có |amplitude| < 0.01).
   - `audio_duration_vs_size.png` — scatter duration vs file size (bytes), log scale.
5. Mỗi figure + companion `.json`:
   ```json
   {
     "figure_id": "audio_duration_ecdf",
     "dataset_id": "tedlium3",
     "revision": "release3-snapshot-e51a4a2a93f3",
     "scope": "full",
     "split": "validation+final_test",
     "n": 20,
     "unit": "wav_file",
     "source_table_hash": "{sha256 of dataset.unit_profile.json}",
     "code_revision": "{git_sha_short}",
     "plotting_config": {"backend": "matplotlib", "version": "...", "dpi": 150},
     "exclusion_policy": "none — all 20 eligible units included"
   }
   ```
6. Append 6 entries vào `dataset.figure_manifest.json` (existing 8 figures + 6 audio = 14 total).

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/scripts/emit_audio_modality_figures.py`
  - `multimodal-lecture-summarizer/tests/test_audio_modality_figures.py`
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.unit_profile.json`
  - `multimodal-lecture-summarizer/experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.figure_manifest.json` (append target)
- **No modify** (chỉ append vào existing manifest; không touch frozen artifacts).

## Implementation Steps

1. **Verify matplotlib available**:
   ```bash
   python -c "import matplotlib; print(matplotlib.__version__)"
   ```
   Nếu chưa có → thêm `matplotlib` vào `requirements.freeze.txt`. Expect có sẵn (đã dùng cho 8 universal figures).

2. **Implement `emit_audio_modality_figures.py`** (~300 dòng):
   ```python
   #!/usr/bin/env python3
   """Emit 6 audio modality-specific figures for TED-LIUM D2 frozen subset.
   
   Reproducibility contract: figures rebuilt from unit_profile.json only;
   no inline constants; deterministic ordering; source-table hash recorded.
   """
   import argparse
   import hashlib
   import json
   import pathlib
   import subprocess
   import numpy as np
   import soundfile as sf
   import matplotlib
   matplotlib.use("Agg")
   import matplotlib.pyplot as plt
   
   FIGURE_IDS = [
       "audio_duration_ecdf",
       "audio_sample_rate_distribution",
       "audio_channel_layout",
       "audio_peak_rms_distribution",
       "audio_speech_ratio_distribution",
       "audio_duration_vs_size",
   ]
   
   def compute_unit_audio_stats(unit_profile_entry, media_path):
       info = sf.info(media_path)
       samples, sr = sf.read(media_path, dtype="float32")
       peak = float(np.max(np.abs(samples)))
       rms = float(np.sqrt(np.mean(samples**2)))
       peak_db = 20 * np.log10(peak + 1e-12)
       rms_db = 20 * np.log10(rms + 1e-12)
       silence_ratio = float(np.mean(np.abs(samples) < 0.01))
       speech_ratio = 1.0 - silence_ratio
       return {
           "unit_id": unit_profile_entry["unit_id"],
           "split": unit_profile_entry["split"],
           "duration_sec": info.duration,
           "sample_rate_hz": info.samplerate,
           "channels": info.channels,
           "subtype": info.subtype,
           "frames": info.frames,
           "peak_db": peak_db,
           "rms_db": rms_db,
           "speech_ratio": speech_ratio,
       }
   
   def render_figures(stats, output_dir, manifest_metadata):
       # ... 6 hàm render, mỗi hàm return path to .png
       pass
   
   def main():
       parser = argparse.ArgumentParser()
       parser.add_argument("--artifact-root", required=True)
       parser.add_argument("--dataset-id", default="tedlium3")
       args = parser.parse_args()
       
       artifact_root = pathlib.Path(args.artifact_root)
       payload_dir = artifact_root / "official/full/payloads"
       figure_dir = artifact_root / "official/full/figures"
       audio_figure_dir = figure_dir / "audio"
       audio_figure_dir.mkdir(parents=True, exist_ok=True)
       
       unit_profile = json.loads((payload_dir / "dataset.unit_profile.json").read_text())
       unit_records = unit_profile["records"][0]["unit_records"]  # 20 entries
       
       source_table = payload_dir / "dataset.unit_profile.json"
       source_hash = hashlib.sha256(source_table.read_bytes()).hexdigest()
       code_rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
       
       metadata = {
           "dataset_id": args.dataset_id,
           "revision": "release3-snapshot-e51a4a2a93f3",
           "scope": "full",
           "split": "validation+final_test",
           "n": len(unit_records),
           "unit": "wav_file",
           "source_table_hash": source_hash,
           "code_revision": code_rev,
           "plotting_config": {"backend": "matplotlib", "version": matplotlib.__version__, "dpi": 150},
           "exclusion_policy": "none — all 20 eligible units included",
       }
       
       stats = []
       for unit in unit_records:
           stats.append(compute_unit_audio_stats(unit, unit["media_path"]))
       
       render_figures(stats, audio_figure_dir, metadata)
       
       # Append to existing figure_manifest.json
       manifest_path = payload_dir / "dataset.figure_manifest.json"
       existing = json.loads(manifest_path.read_text())
       audio_manifest = []
       for fig_id in FIGURE_IDS:
           entry = dict(metadata)
           entry["figure_id"] = fig_id
           entry["path"] = f"figures/audio/{fig_id}.png"
           audio_manifest.append(entry)
       
       # Add to existing records (preserve 8 universal figures)
       for record in existing["records"]:
           if "figures" in record:
               record["figures"].extend(audio_manifest)
       
       manifest_path.write_text(json.dumps(existing, indent=2))
       print(f"Emitted {len(FIGURE_IDS)} audio figures under {audio_figure_dir}")
   
   if __name__ == "__main__":
       main()
   ```

3. **Run driver**:
   ```bash
   cd multimodal-lecture-summarizer
   python -m experiments.scripts.emit_audio_modality_figures \
     --artifact-root experiments/outputs/phase2_tedlium_d2
   ```
   Verify:
   - 6 file `.png` mới trong `experiments/outputs/phase2_tedlium_d2/official/full/figures/audio/`.
   - `dataset.figure_manifest.json` có thêm 6 entries (total = 14 figures).
   - 6 file `.json` metadata kèm mỗi figure.

4. **Regression check**:
   ```bash
   python -c "
   import json, hashlib
   m = json.loads(open('experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.frozen_manifest.json').read())
   # frozen_manifest phải SHA-256 y nguyên
   print('OK')
   "
   ```

5. **Tests mới** `tests/test_audio_modality_figures.py` (≥ 3 tests):
   - `test_audio_figures_all_6_emitted`: kiểm tra 6 file `.png` tồn tại + không rỗng.
   - `test_audio_figure_metadata_complete`: mỗi figure có source_table_hash, code_revision, plotting_config, n=20.
   - `test_audio_figure_manifest_appended_not_replaced`: existing 8 figures vẫn còn trong manifest.

## Success Criteria

- [x] `experiments/scripts/emit_audio_modality_figures.py` chạy thành công.
- [x] 6 file `.png` emitted trong `experiments/outputs/phase2_tedlium_d2/official/full/figures/audio/`.
- [x] 6 file `.json` metadata kèm mỗi figure, có source_table_hash, code_revision, plotting_config.
- [x] `dataset.figure_manifest.json` có 14 entries (8 universal + 6 audio).
- [x] TED-LIUM frozen_manifest SHA-256 không đổi.
- [x] `tests/test_audio_modality_figures.py` PASS 8/8.

## Outcome (2026-09-26)

Kết quả thực tế: 6 PNG (32-55 KiB, đều dưới budget 200 KiB), 6 sidecar, manifest 8 → 14,
contract revalidate PASS (`d2_figure_count=14`), 24/25 payload TED-LIUM còn lại byte-identical.
Test mới 8/8; `tests/` suite 346 passed / 1 failed (failure cũ ở `test_validation_gate.py`).

### Deviations từ plan (bắt buộc, do contract thực tế)

1. **Sidecar/metadata dùng `source_table_sha256` (contract-recomputed hash của
   `source_artifact`), không phải hash của `dataset.unit_profile.json`.**
   `dataset_contracts._validate_contract_record` recompute `source_table_sha256` từ
   `record["source_artifact"]` và chỉ cho phép 6 artifact:
   `dataset.acquisition_inventory`, `dataset.unit_profile`, `dataset.profile`,
   `dataset.attrition`, `dataset.statistics`, `dataset.split_statistics`.
   Không artifact nào chứa per-unit audio measurement, nên record khai
   `source_artifact="dataset.statistics"` + hash recompute tương ứng. Provenance thật
   của số liệu vẽ được lưu ở sidecar: `audio_statistics_sha256` (bảng per-unit đo được)
   và `unit_profile_sha256` (bảng unit frozen mà nó join vào).
2. **Không thêm `audio_geometry` vào `dataset.statistics`** (khác Phase 1 image figures).
   Phase 1 thêm `image_geometry` chỉ cho image dataset nên TED-LIUM vẫn 25/25. Audio thì
   ngược lại: thêm vào sẽ đổi `dataset.statistics` của TED-LIUM, vi phạm yêu cầu
   "frozen_manifest SHA-256 không đổi" của chính phase này.
3. **Manifest là flat `records` list**, không phải `record["figures"]` như code snippet
   trong plan. Script append vào `records` và fail loudly (exit 5) nếu `figure_id` trùng.
4. **`audio_channel_layout` dùng bar chart + coverage table, không phải pie** — 20/20 unit
   đều mono nên pie chỉ có 1 slice, không mang thông tin. `audio_sample_rate_distribution`
   thêm panel "byte-rate implied rate" làm integrity check (16 kHz × PCM_16 mono = 32000 B/s).

### Data thực tế của 20 WAV (đã verify, không phải giả định)

Toàn bộ 20 unit đều là **16 kHz, mono, PCM_16**; duration 1.67-18.22 s (median 8.33,
tổng 172.2 s); peak -8.24 → -0.36 dBFS; RMS -26.69 → -14.91 dBFS; speech-ratio proxy
0.467-0.859; bytes/sec 32002-32026 (khớp 32000 B/s + 44-byte WAV header). Test
`test_measured_audio_properties_match_frozen_files` assert các invariant này để chặn
figure bị sinh từ hằng số bịa.


## Risk Assessment

- **Risk:** `soundfile` chưa có trong env → import fail.
  **Mitigation:** Phase 1 driver `phase2_freeze_tedlium.py` đã dùng `soundfile` thành công → expect có sẵn. Nếu không → add vào `requirements.freeze.txt`.
- **Risk:** matplotlib backend issue trên headless server.
  **Mitigation:** Set `matplotlib.use("Agg")` trước `import pyplot`; pattern đã dùng cho 8 universal figures.
- **Risk:** Speech ratio proxy quá đơn giản (silence = |amp| < 0.01) gây misinterpretation.
  **Mitigation:** Ghi rõ trong figure caption + figure metadata: "speech_ratio_proxy = 1 - silence_ratio; silence threshold = 0.01 absolute amplitude; calibrated cho 16-bit PCM WAV; không phải VAD output".
- **Risk:** Figure size > 200 KB → bloated output directory.
  **Mitigation:** DPI=150, format=png, expect ~50-150 KB mỗi figure. Nếu > 200 KB → reduce DPI to 100.

## Effort Breakdown

| Step | Time |
|------|------|
| Verify matplotlib + soundfile | 0.5 giờ |
| Implement `emit_audio_modality_figures.py` (6 figures + 1 manifest) | 3-4 giờ |
| Run + debug + visual review 6 figures | 1-2 giờ |
| Tests + regression check + journal | 1 giờ |
| **Tổng** | **5.5-7.5 giờ** |