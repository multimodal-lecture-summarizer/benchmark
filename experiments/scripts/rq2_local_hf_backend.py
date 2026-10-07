"""Local, pinned Transformers backend with exact token receipts for RQ2.

This adapter uses raw prompt text consistently for counting and generation.
It never fetches model files: the supplied directory must already be complete.
"""

from __future__ import annotations

from pathlib import Path


class LocalHfUsageBackend:
    def __init__(self, model_dir: Path, *, model_id: str, revision: str,
                 device: str = "cpu") -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        folder = Path(model_dir).resolve()
        if not folder.is_dir() or not (folder / "model.safetensors").is_file():
            raise FileNotFoundError(f"Pinned local model weights are missing: {folder}")
        if not model_id or not revision:
            raise ValueError("Model identity and pinned revision are required")
        if device not in {"cpu", "cuda"}:
            raise ValueError("Device must be cpu or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; do not retry a lost GPU device")
        self.model_id = f"{model_id}@{revision}"
        self.tokenizer_id = self.model_id
        self.tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            folder, local_files_only=True, torch_dtype=torch.float16
        )
        self.device = device
        self.model.to(self.device)
        self.model.eval()
        self.context_limit = int(self.model.config.max_position_embeddings)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def generate(self, prompt: str, *, max_output_tokens: int,
                 temperature: float, seed: int) -> dict:
        import torch

        if temperature != 0:
            raise ValueError("This controlled backend currently supports greedy decoding only")
        inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        input_ids = inputs["input_ids"].to(self.device)
        prompt_tokens = int(input_ids.shape[-1])
        if prompt_tokens + max_output_tokens > self.context_limit:
            raise ValueError("Prompt plus output budget exceeds pinned model context")
        torch.manual_seed(seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(seed)
        with torch.inference_mode():
            output = self.model.generate(
                input_ids=input_ids,
                attention_mask=inputs["attention_mask"].to(self.device),
                max_new_tokens=max_output_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0, prompt_tokens:]
        text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        return {
            "text": text,
            "attempts": [{"status": "success", "prompt_tokens": prompt_tokens,
                          "output_tokens": int(generated.shape[-1]),
                          "content_tokens": self.count_tokens(text)}],
        }

    def generate_batch(self, prompts: list[str], *, max_output_tokens: int,
                       temperature: float, seed: int) -> list[dict]:
        """Generate several map summaries in one GPU call with exact per-prompt usage."""
        import torch

        if not prompts:
            return []
        if temperature != 0:
            raise ValueError("This controlled backend supports greedy decoding only")
        inputs = self.tokenizer(prompts, return_tensors="pt", padding=True,
                                add_special_tokens=False)
        input_ids = inputs["input_ids"].to(self.device)
        attention_mask = inputs["attention_mask"].to(self.device)
        padded_length = int(input_ids.shape[-1])
        if padded_length + max_output_tokens > self.context_limit:
            raise ValueError("Batched prompt plus output budget exceeds pinned model context")
        prompt_counts = [int(value) for value in attention_mask.sum(dim=1).tolist()]
        torch.manual_seed(seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(seed)
        with torch.inference_mode():
            output = self.model.generate(
                input_ids=input_ids, attention_mask=attention_mask,
                max_new_tokens=max_output_tokens, do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        responses = []
        for row, prompt_tokens in zip(output[:, padded_length:], prompt_counts):
            generated = row.tolist()
            if self.tokenizer.eos_token_id in generated:
                generated = generated[:generated.index(self.tokenizer.eos_token_id) + 1]
            text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
            responses.append({
                "text": text,
                "attempts": [{"status": "success", "prompt_tokens": prompt_tokens,
                              "output_tokens": len(generated),
                              "content_tokens": self.count_tokens(text)}],
            })
        return responses
