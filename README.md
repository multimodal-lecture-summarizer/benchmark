# Video Summarization Pipeline

A multimodal Artificial Intelligence pipeline designed to automatically summarize videos by extracting both visual semantics and narrative context. 

## Project Structure

```text
Video_summarization/
├── audio/          # (WIP) Modules for Audio processing and Speech-to-Text transcription.
├── dataset/        # Video datasets for testing and validation (Ignored in Git).
├── visual/         # Visual Pipeline - Extracts keyframe descriptions from video.
│   ├── scene_detector.py      # Scene change detection and keyframe extraction (PySceneDetect).
│   ├── clip_filter.py         # Semantic filtering to remove redundant frames (CLIP + K-Means).
│   ├── image_captioner.py     # Image captioning to describe semantic keyframes (BLIP-2).
│   ├── main_visual.py         # Main orchestrator for the Visual Pipeline.
│   └── kaggle_visual_cell.py  # A standalone script to deploy the Visual Pipeline directly to Kaggle.
├── requirements.txt
└── .gitignore
```

## Visual Pipeline (`/visual`)

The Visual Pipeline converts raw video frames into a sequence of meaningful textual descriptions (Visual Facts). It operates in three main steps:

1. **Scene Detection (`scene_detector.py`)**
   - Utilizes `PySceneDetect` to detect scene changes and segment the video.
   - Extracts the middle frame of each scene as a Keyframe.
   - Computes a *Scene Diversity Score* using Color Histograms (Bhattacharyya distance) to evaluate segmentation quality.

2. **Semantic Filtering (`clip_filter.py`)**
   - Uses OpenAI's `CLIP` model to extract semantic embeddings for each keyframe.
   - Applies `K-Means` clustering to group similar frames and discard semantic redundancies.
   - Evaluates filter quality by measuring the improvement in average cosine distance between frames.

3. **Image Captioning (`image_captioner.py`)**
   - Deploys `BLIP-2 (OPT-2.7B)` optimized with `float16` precision to describe the remaining keyframes in natural language.
   - Applies advanced generation parameters (e.g., `repetition_penalty=1.5`) to prevent LLM hallucinations.
   - Outputs a sequence of textual facts (e.g., *"a man playing with his dog"*).
   - Validates caption accuracy using a reference-free **CLIP-Score** benchmark.

## Deployment (Kaggle)

Due to hardware constraints (VRAM for BLIP-2), the Visual Pipeline is designed to be fully deployable on a Kaggle Notebook using a T4 GPU.

1. Open a new Kaggle Notebook (Turn on GPU).
2. Create a new cell.
3. Copy the entire contents of `visual/kaggle_visual_cell.py` and paste it into the cell.
4. Run the cell. This script will automatically recreate the entire `visual` package inside `/kaggle/working/visual`.
5. In the next cell, run the pipeline:
   ```python
   from visual.main_visual import run_visual_pipeline
   
   video_path = "/kaggle/input/your-dataset/video.mp4"
   summary_text = run_visual_pipeline(video_path, output_dir="/kaggle/working/output")
   print(summary_text)
   ```

## Future Work (LLM Pipeline)

The output of the Visual Pipeline (the sequence of factual descriptions) will be combined with the Audio transcription. This combined text will then be fed into a Large Language Model (e.g., LLaMA-3, GPT-4) to generate a cohesive, human-like narrative summary of the entire video.
