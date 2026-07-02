import os
import torch
from PIL import Image
from transformers import Blip2Processor, Blip2ForConditionalGeneration
# Reuse the CLIP loader from our previous module for the benchmark
from clip_filter import load_clip_model

def load_blip2_model(model_name="Salesforce/blip2-opt-2.7b"):
    """
    Load the BLIP-2 model and processor from HuggingFace.
    Optimized for Kaggle (CUDA) using float16 precision.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"Loading BLIP-2 processor: {model_name}")
    processor = Blip2Processor.from_pretrained(model_name)
    
    print(f"Loading BLIP-2 model weights (this will take time on first run)...")
    # Load in float16 to save memory and speed up inference on GPUs like T4
    model = Blip2ForConditionalGeneration.from_pretrained(
        model_name, 
        torch_dtype=torch.float16,
        use_safetensors=True
    ).to(device)
    
    return processor, model, device

def generate_captions(image_paths, processor, model, device):
    """
    Generate descriptive captions for a list of images using BLIP-2.
    """
    valid_paths = [p for p in image_paths if os.path.exists(p)]
    captions_dict = {}
    
    if not valid_paths:
        return captions_dict

    # Process images one by one to avoid VRAM OOM errors during text generation
    for path in valid_paths:
        try:
            raw_image = Image.open(path).convert("RGB")
            
            # Không sử dụng prompt rườm rà vì lõi OPT-2.7B dễ bị "ảo giác" (hallucination)
            # Dùng prompt hỏi đáp chuẩn của BLIP-2 hoặc sinh tự do
            prompt = "Question: describe this image in detail. Answer:"
            inputs = processor(raw_image, text=prompt, return_tensors="pt").to(device, torch.float16)
            
            # Thêm repetition_penalty để chống lặp từ (như [dog][dog]...)
            # Thêm length_penalty và giới hạn token để câu văn gọn gàng
            generated_ids = model.generate(
                **inputs, 
                max_new_tokens=30,
                min_new_tokens=5,
                repetition_penalty=1.5
            )
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            
            # Xóa câu prompt mồi ra khỏi kết quả (do kiến trúc Decoder-only của OPT sẽ trả về cả prompt)
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            captions_dict[path] = generated_text
        except Exception as e:
            print(f"Error generating caption for {path}: {e}")
            captions_dict[path] = ""
            
    return captions_dict

def evaluate_clip_score(captions_dict):
    """
    Reference-free Benchmark: CLIP-Score.
    Measures how well the generated text matches the visual content of the image.
    Score ranges roughly from 20 to 40. Higher is better.
    """
    if not captions_dict:
        return 0.0
        
    print("Loading CLIP for benchmark scoring...")
    try:
        clip_processor, clip_model, device = load_clip_model()
    except Exception as e:
        print(f"Failed to load CLIP for evaluation: {e}")
        return 0.0
        
    total_score = 0.0
    valid_count = 0
    
    with torch.no_grad():
        for img_path, text in captions_dict.items():
            if not text or not os.path.exists(img_path):
                continue
                
            image = Image.open(img_path).convert("RGB")
            
            # Pass both image and generated text to CLIP
            inputs = clip_processor(text=[text], images=image, return_tensors="pt", padding=True).to(device)
            outputs = clip_model(**inputs)
            
            # Extract logits (similar to unscaled cosine similarity)
            logits_per_image = outputs.logits_per_image  # shape: [1, 1]
            score = logits_per_image.item()
            
            # Typical CLIP score is scaled by a factor (usually 2.5 in academic papers) for readability
            scaled_score = max(0.0, score * 2.5)
            
            total_score += scaled_score
            valid_count += 1
            
    if valid_count == 0:
        return 0.0
        
    return total_score / valid_count

if __name__ == "__main__":
    import glob
    
    # Use relative paths
    video_name = "0tmA_C6XwfM"
    keyframe_dir = os.path.join("keyframes", video_name)
    image_paths = sorted(glob.glob(os.path.join(keyframe_dir, "*.jpg")))
    
    # For testing, we only take the first 3 images so we don't wait forever
    test_paths = image_paths[:3]
    
    if not test_paths:
        print(f"Error: No images found in {keyframe_dir}")
        exit(1)
        
    try:
        print(f"Initializing BLIP-2 pipeline for {len(test_paths)} test images...")
        processor, model, device = load_blip2_model()
        print(f"BLIP-2 loaded on {device}")
        
        print("Generating captions...")
        results = generate_captions(test_paths, processor, model, device)
        
        for path, caption in results.items():
            print(f"Image: {os.path.basename(path)} -> Caption: {caption}")
            
        # Run Reference-free benchmark
        print("\\nCalculating CLIP-Score...")
        avg_clip_score = evaluate_clip_score(results)
        
        print("-" * 40)
        print("BLIP-2 CAPTIONING BENCHMARK RESULTS")
        print("-" * 40)
        print(f"Average CLIP-Score: {avg_clip_score:.2f}")
        
        if avg_clip_score > 70.0:
            print("Evaluation: Excellent. High correlation between text and image.")
        elif avg_clip_score > 60.0:
            print("Evaluation: Good. The captions accurately describe the scenes.")
        else:
            print("Evaluation: Average. Captions might lack specific details.")
            
    except Exception as e:
        print(f"Execution error: {e}")
