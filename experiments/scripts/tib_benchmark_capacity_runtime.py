"""Pinned asset loading and complete inference-environment checkpoint identity."""
import hashlib
import importlib.metadata
from pathlib import Path
import time

from experiments.scripts.tib_benchmark_checkpoint import digest


def checkpoint_download_patterns(repo_files):
    root_files = {name for name in repo_files if '/' not in name}
    if 'model.safetensors' in root_files:
        weights = ['model.safetensors']
    elif 'model.safetensors.index.json' in root_files:
        weights = ['model.safetensors.index.json', 'model-*.safetensors']
    elif 'pytorch_model.bin' in root_files:
        weights = ['pytorch_model.bin']
    elif 'pytorch_model.bin.index.json' in root_files:
        weights = ['pytorch_model.bin.index.json', 'pytorch_model-*.bin']
    else:
        raise ValueError('Pinned checkpoint has no supported PyTorch weight file/index')
    return ['*.json', '*.model', '*.txt', *weights]


def stream_sha(path):
    digestor = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(8*1024*1024), b''):
            digestor.update(chunk)
    return digestor.hexdigest()


def load_runtime_assets(profile, receipt):
    import torch
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer
    started = time.perf_counter()
    repo_files = HfApi().list_repo_files(profile['checkpoint'], revision=profile['revision'])
    patterns = checkpoint_download_patterns(repo_files)
    receipt['checkpoint_download_patterns'] = patterns
    assets = Path(snapshot_download(profile['checkpoint'], revision=profile['revision'],
                                   allow_patterns=patterns, ignore_patterns=['onnx/*','openvino/*'], max_workers=2))
    if assets.name != profile['revision']:
        raise ValueError('Resolved checkpoint revision mismatch')
    receipt['asset_sha256'] = {str(p.relative_to(assets)):stream_sha(p) for p in assets.rglob('*') if p.is_file()}
    tokenizer = AutoTokenizer.from_pretrained(assets, local_files_only=True)
    klass = AutoModelForCausalLM if profile['architecture']=='causal' else AutoModelForSeq2SeqLM
    model = klass.from_pretrained(assets, local_files_only=True, torch_dtype=torch.float16,
                                 attn_implementation='eager', device_map={'':'cuda:0'})
    model.eval()
    torch.cuda.synchronize()
    receipt.update(resolved_generation_config=model.generation_config.to_dict(),
                   resolved_model_config=model.config.to_dict(),
                   actual_parameter_dtype=str(next(model.parameters()).dtype),
                   actual_attention_backend=getattr(model.config,'_attn_implementation',None),
                   actual_device_map={str(k):str(v) for k,v in getattr(model,'hf_device_map',{}).items()},
                   tokenizer_class=type(tokenizer).__name__, load_seconds=time.perf_counter()-started,
                   runtime_dependencies={p:importlib.metadata.version(p) for p in
                                         ('accelerate','tokenizers','safetensors','psutil')})
    return model, tokenizer


def runtime_identity(receipt):
    fields = ('device_name','packages','cuda_runtime','actual_parameter_dtype','runtime_dependencies',
              'actual_attention_backend','actual_device_map','asset_sha256','tokenizer_class','device_memory_bytes')
    return digest({field:receipt[field] for field in fields})
