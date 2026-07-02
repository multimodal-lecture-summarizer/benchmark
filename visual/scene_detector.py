import os
import cv2
import numpy as np
from scenedetect import detect, ContentDetector

def calculate_histogram_similarity(img1_path, img2_path):
    """
    Calculate the similarity between 2 images based on Color Histogram (Bhattacharyya distance).
    Returns a distance: 0 (identical) to 1 (completely different).
    """
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    
    if img1 is None or img2 is None:
        return 1.0

    # Convert to HSV color space
    hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

    # Calculate histogram for Hue (0-180) and Saturation (0-256) channels
    hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])

    # Normalize histograms
    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    # Calculate Bhattacharyya distance (0: identical, 1: different)
    distance = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
    return distance

def extract_scenes_and_keyframes(video_path, output_dir="keyframes", threshold=27.0):
    """
    Detect scene changes and extract the middle keyframe of each scene.
    
    Args:
        video_path (str): Relative path to the video file (.mp4).
        output_dir (str): Relative path to the output directory for keyframes.
        threshold (float): Sensitivity threshold for scene detection.
        
    Returns:
        list: Metadata list of extracted scenes.
    """
    print(f"Starting video analysis: {video_path}")
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"File not found: {video_path}")
        
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_keyframe_dir = os.path.join(output_dir, video_name)
    os.makedirs(video_keyframe_dir, exist_ok=True)
    
    scene_list = detect(video_path, ContentDetector(threshold=threshold))
    print(f"Number of detected scenes: {len(scene_list)}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Cannot open video: {video_path}")
    
    metadata_list = []
    
    for i, scene in enumerate(scene_list):
        start_time, end_time = scene
        
        # Use frame_num property to avoid deprecation warning
        start_frame = start_time.frame_num
        end_frame = end_time.frame_num
        
        middle_frame = (start_frame + end_frame) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
        ret, frame = cap.read()
        
        if ret:
            img_filename = f"scene_{i+1:03d}.jpg"
            img_path = os.path.join(video_keyframe_dir, img_filename)
            cv2.imwrite(img_path, frame)
            
            metadata_list.append({
                'scene_id': i + 1,
                'start_time': start_time.get_timecode(),
                'end_time': end_time.get_timecode(),
                'middle_frame_idx': middle_frame,
                'keyframe_path': img_path
            })
        else:
            print(f"Warning: Cannot read frame number {middle_frame} of scene {i+1}.")
            
    cap.release()
    print("Keyframe extraction completed.")
    return metadata_list

def evaluate_scene_diversity(metadata_list):
    """
    Evaluate the Diversity Score of extracted keyframes.
    Uses the average distance between adjacent frames.
    High distance -> Good segmentation (less redundancy).
    Low distance -> Possible over-segmentation.
    """
    if len(metadata_list) < 2:
        return 0.0
        
    total_distance = 0.0
    valid_pairs = 0
    
    for i in range(len(metadata_list) - 1):
        img1_path = metadata_list[i]['keyframe_path']
        img2_path = metadata_list[i+1]['keyframe_path']
        
        if os.path.exists(img1_path) and os.path.exists(img2_path):
            dist = calculate_histogram_similarity(img1_path, img2_path)
            total_distance += dist
            valid_pairs += 1
            
    if valid_pairs == 0:
        return 0.0
        
    avg_distance = total_distance / valid_pairs
    return avg_distance

if __name__ == "__main__":
    video_path = os.path.join("..", "dataset", "Visual", "0tmA_C6XwfM.mp4")
    output_dir = "keyframes"
    
    try:
        # 1. Extract scenes
        metadata = extract_scenes_and_keyframes(video_path, output_dir=output_dir, threshold=27.0)
        
        # 2. Benchmark (Reference-free evaluation)
        diversity_score = evaluate_scene_diversity(metadata)
        
        print("-" * 40)
        print("SCENE DETECTOR BENCHMARK RESULTS")
        print("-" * 40)
        print(f"Number of extracted keyframes: {len(metadata)}")
        print(f"Adjacent frame diversity score: {diversity_score:.4f}")
        
        # Evaluation notes
        if diversity_score < 0.2:
            print("Evaluation: Frames are quite similar. Algorithm might be over-segmenting, consider increasing threshold.")
        elif diversity_score > 0.5:
            print("Evaluation: Frames are very distinct. High quality segmentation.")
        else:
            print("Evaluation: Diversity is average.")
            
    except Exception as e:
        print(f"Execution error: {e}")
