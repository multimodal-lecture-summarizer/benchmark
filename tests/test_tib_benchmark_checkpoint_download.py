"""Weight-format regressions without downloading multi-GB checkpoints."""
from fnmatch import fnmatch

import pytest

from experiments.scripts.tib_benchmark_colab_capacity import checkpoint_download_patterns


def selected(files):
    patterns = checkpoint_download_patterns(files)
    return {name for name in files if any(fnmatch(name, pattern) for pattern in patterns)}


def test_pinned_led_legacy_weights_are_selected():
    # Official HF API inventory at 0f8b26971c44af9d4e21edd17ccb5e000f22dac1.
    files = ['.gitattributes', 'README.md', 'config.json', 'generation_config.json',
             'merges.txt', 'pytorch_model.bin', 'special_tokens_map.json',
             'tf_model.h5', 'tokenizer_config.json', 'vocab.json']
    assert selected(files) == set(files) - {'.gitattributes', 'README.md', 'tf_model.h5'}


def test_safetensors_prevents_duplicate_binary_download():
    assert selected(['config.json', 'model.safetensors', 'pytorch_model.bin']) == {
        'config.json', 'model.safetensors'}


@pytest.mark.parametrize('index,shard,excluded', [
    ('model.safetensors.index.json', 'model-00001-of-00002.safetensors', 'pytorch_model.bin'),
    ('pytorch_model.bin.index.json', 'pytorch_model-00001-of-00002.bin', 'tf_model.h5'),
])
def test_sharded_checkpoints_include_index_and_weights(index, shard, excluded):
    assert selected(['config.json', index, shard, excluded]) == {'config.json', index, shard}


def test_subdirectory_weights_cannot_satisfy_root_checkpoint():
    with pytest.raises(ValueError, match='no supported PyTorch weight'):
        checkpoint_download_patterns(['config.json', 'onnx/model.safetensors'])
