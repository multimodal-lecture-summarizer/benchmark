import os
import json
import argparse

# Import modules from our visual pipeline
from scene_detector import extract_scenes_and_keyframes, evaluate_scene_diversity
from clip_filter import load_clip_model, extract_image_embeddings, filter_keyframes, evaluate_filter_quality
from image_captioner import load_blip2_model, generate_captions, evaluate_clip_score

def run_visual_pipeline(video_path, output_dir="output", keep_ratio=0.7):
    """
    End-to-End Visual Pipeline:
    Video -> PySceneDetect -> CLIP Filter -> BLIP-2 Captions
    """
    print("=" * 60)
    print(f"STARTING VISUAL PIPELINE FOR: {video_path}")
    print("=" * 60)
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    keyframe_dir = os.path.join(output_dir, "keyframes")
    result_dir = os.path.join(output_dir, "results")
    os.makedirs(result_dir, exist_ok=True)
    
    # ---------------------------------------------------------
    # STEP 1: SCENE DETECTION
    # ---------------------------------------------------------
    print("\\n[STEP 1] Running Scene Detection")
    metadata = extract_scenes_and_keyframes(video_path, output_dir=keyframe_dir, threshold=27.0)
    
    if not metadata:
        print("Error: No scenes detected.")
        return None
        
    diversity_score = evaluate_scene_diversity(metadata)
    print(f"-> Extracted {len(metadata)} keyframes.")
    print(f"-> Scene Diversity Score: {diversity_score:.4f}")
    
    # Get paths of extracted images
    image_paths = [m['keyframe_path'] for m in metadata if os.path.exists(m['keyframe_path'])]
    
    # ---------------------------------------------------------
    # STEP 2: CLIP FILTERING
    # ---------------------------------------------------------
    print("\\n[STEP 2] Running Semantic Filtering (CLIP + KMeans)...")
    clip_processor, clip_model, clip_device = load_clip_model()
    
    embeddings, valid_paths = extract_image_embeddings(image_paths, clip_processor, clip_model, clip_device)
    filtered_paths, filtered_embeddings = filter_keyframes(valid_paths, embeddings, keep_ratio=keep_ratio)
    
    orig_dist, filt_dist = evaluate_filter_quality(embeddings, filtered_embeddings)
    print(f"-> Original frames: {len(valid_paths)} | Filtered frames: {len(filtered_paths)}")
    print(f"-> Semantic distance improved: {orig_dist:.4f} -> {filt_dist:.4f}")
    
    # ---------------------------------------------------------
    # STEP 3: BLIP-2 IMAGE CAPTIONING
    # ---------------------------------------------------------
    print("\\n[STEP 3] Running Image Captioning (BLIP-2)...")
    blip_processor, blip_model, blip_device = load_blip2_model()
    
    captions_dict = generate_captions(filtered_paths, blip_processor, blip_model, blip_device)
    
    print("\\n[STEP 4] Evaluating Captions (CLIP-Score)...")
    avg_clip_score = evaluate_clip_score(captions_dict)
    print(f"-> Average CLIP-Score: {avg_clip_score:.2f}")
    
    # ---------------------------------------------------------
    # FINAL: COMPILE AND SAVE RESULTS
    # ---------------------------------------------------------
    print("\\n[FINAL] Compiling narrative summary...")
    
    summary_lines = []
    for path in filtered_paths:
        if path in captions_dict:
            filename = os.path.basename(path)
            caption = captions_dict[path]
            summary_lines.append(f"[{filename}]: {caption}")
            
    final_text = " ".join([captions_dict[p] for p in filtered_paths if p in captions_dict])
    
    # Save to JSON
    output_json = os.path.join(result_dir, f"{video_name}_summary.json")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            "video_name": video_name,
            "metrics": {
                "diversity_score": diversity_score,
                "clip_distance_improvement": f"{orig_dist:.4f} -> {filt_dist:.4f}",
                "clip_score": avg_clip_score
            },
            "captions": summary_lines,
            "combined_text": final_text
        }, f, indent=4)
        
    # Save raw text for the LLM step
    output_txt = os.path.join(result_dir, f"{video_name}_summary.txt")
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write(final_text)
        
    print(f"\\nPipeline completed successfully!")
    print(f"Results saved to: {output_json} and {output_txt}")
    
    return final_text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full Video Visual Summarization Pipeline.")
    parser.add_argument("--video", type=str, default=os.path.join("..", "dataset", "Visual", "0tmA_C6XwfM.mp4"),
                        help="Path to the input video file")
    parser.add_argument("--out_dir", type=str, default="pipeline_output",
                        help="Directory to save output files")
    parser.add_argument("--ratio", type=float, default=0.7,
                        help="Ratio of frames to keep after CLIP filtering (0.0 to 1.0)")
                        
    args = parser.parse_args()
    
    run_visual_pipeline(args.video, output_dir=args.out_dir, keep_ratio=args.ratio)
