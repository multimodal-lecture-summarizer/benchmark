import os
import numpy as np
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

def load_clip_model(model_name="openai/clip-vit-base-patch32"):
    """
    Load the CLIP model and processor from HuggingFace.
    Returns: processor, model, device
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name, use_safetensors=True).to(device)
    return processor, model, device

def extract_image_embeddings(image_paths, processor, model, device):
    """
    Extract CLIP feature embeddings for a list of images.
    """
    valid_paths = [p for p in image_paths if os.path.exists(p)]
    if not valid_paths:
        return np.array([]), []

    images = [Image.open(p).convert("RGB") for p in valid_paths]
    
    # Process images in batches to prevent memory overflow
    batch_size = 32
    all_embeddings = []
    
    with torch.no_grad():
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            inputs = processor(images=batch_images, return_tensors="pt", padding=True).to(device)
            # Truy cập trực tiếp vào các layer để đảm bảo luôn nhận được Tensor 100%
            pixel_values = inputs["pixel_values"]
            vision_outputs = model.vision_model(pixel_values=pixel_values)
            
            # Lấy pooler_output (đầu ra gom cụm của ảnh)
            pooler_output = vision_outputs.pooler_output if hasattr(vision_outputs, "pooler_output") else vision_outputs[1]
            
            # Chiếu qua không gian vector của CLIP
            image_features = model.visual_projection(pooler_output)
            
            # Chuẩn hóa vector
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            all_embeddings.append(image_features.cpu().numpy())
            
    embeddings_matrix = np.vstack(all_embeddings)
    return embeddings_matrix, valid_paths

def filter_keyframes(image_paths, embeddings, keep_ratio=0.7):
    """
    Use K-Means clustering to remove semantically redundant frames.
    Keeps a percentage (keep_ratio) of the original frames.
    Returns the paths of the selected frames and their embeddings.
    """
    num_frames = len(image_paths)
    if num_frames == 0:
        return [], np.array([])
        
    num_clusters = max(1, int(num_frames * keep_ratio))
    
    if num_clusters == num_frames:
        return image_paths, embeddings
        
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    kmeans.fit(embeddings)
    
    selected_indices = []
    # For each cluster, find the frame closest to the cluster center
    for i in range(num_clusters):
        cluster_center = kmeans.cluster_centers_[i]
        # Calculate distances from all points to this center
        distances = np.linalg.norm(embeddings - cluster_center, axis=1)
        # Find the index of the closest point that hasn't been selected yet
        sorted_indices = np.argsort(distances)
        for idx in sorted_indices:
            if idx not in selected_indices:
                selected_indices.append(idx)
                break
                
    # Sort indices to maintain chronological order
    selected_indices.sort()
    
    filtered_paths = [image_paths[i] for i in selected_indices]
    filtered_embeddings = embeddings[selected_indices]
    
    return filtered_paths, filtered_embeddings

def evaluate_filter_quality(original_embeddings, filtered_embeddings):
    """
    Calculate the average pairwise cosine distance (1 - similarity) 
    before and after filtering.
    A successful filter should increase the average distance among remaining frames.
    """
    if len(original_embeddings) < 2 or len(filtered_embeddings) < 2:
        return 0.0, 0.0
        
    # Calculate pairwise cosine similarities
    orig_sim = cosine_similarity(original_embeddings)
    filt_sim = cosine_similarity(filtered_embeddings)
    
    # Extract upper triangle (excluding diagonal) to get unique pairs
    orig_triu = orig_sim[np.triu_indices(orig_sim.shape[0], k=1)]
    filt_triu = filt_sim[np.triu_indices(filt_sim.shape[0], k=1)]
    
    # Convert similarity to distance
    orig_dist = 1.0 - np.mean(orig_triu)
    filt_dist = 1.0 - np.mean(filt_triu)
    
    return orig_dist, filt_dist

if __name__ == "__main__":
    import glob
    
    video_name = "0tmA_C6XwfM"
    keyframe_dir = os.path.join("keyframes", video_name)
    image_paths = sorted(glob.glob(os.path.join(keyframe_dir, "*.jpg")))
    
    if not image_paths:
        print(f"Error: No images found in {keyframe_dir}")
        exit(1)
        
    print(f"Loading CLIP model")
    try:
        processor, model, device = load_clip_model()
        print(f"Model loaded successfully on device: {device}")
        
        print(f"Extracting embeddings for {len(image_paths)} images")
        embeddings, valid_paths = extract_image_embeddings(image_paths, processor, model, device)
        
        print("Applying K-Means clustering to filter semantic redundancy")
        # Keep only 70% of the frames
        keep_ratio = 0.7 
        filtered_paths, filtered_embeddings = filter_keyframes(valid_paths, embeddings, keep_ratio=keep_ratio)
        
        orig_dist, filt_dist = evaluate_filter_quality(embeddings, filtered_embeddings)
        
        print("-" * 40)
        print("CLIP FILTER BENCHMARK RESULTS")
        print("-" * 40)
        print(f"Original frames: {len(valid_paths)}")
        print(f"Frames after filtering: {len(filtered_paths)} (Ratio: {keep_ratio:.1f})")
        print(f"Average semantic distance before filter: {orig_dist:.4f}")
        print(f"Average semantic distance after filter : {filt_dist:.4f}")
        
        if filt_dist > orig_dist:
            print("Evaluation: SUCCESS. Redundancy reduced. Remaining frames are more semantically distinct.")
        else:
            print("Evaluation: WARNING. Semantic distance did not improve. Filtering may not be optimal.")
            
    except Exception as e:
        print(f"Execution error: {e}")
