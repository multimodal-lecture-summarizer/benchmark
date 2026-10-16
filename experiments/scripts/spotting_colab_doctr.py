"""Exact docTR0.12 PARSeq legacy compatibility, followed by strict loading.

Upstream PARSeq.from_pretrained removes these unused parameters for pre0.11.1
checkpoints (mindee/doctr issue1911). Keep all current-model parameters strict;
never rewrite the frozen checkpoint or ignore unrelated missing/extra keys.
"""
from copy import copy

LEGACY_UNUSED = frozenset({
    'decoder.attention_norm.weight', 'decoder.attention_norm.bias',
    'decoder.cross_attention_norm.weight', 'decoder.cross_attention_norm.bias',
})


def load_parseq_checkpoint(model, state):
    expected = set(model.state_dict())
    if expected & LEGACY_UNUSED:
        raise ValueError('legacy PARSeq keys are used by this model; compatibility profile changed')
    unexpected = set(state) - expected
    if unexpected - LEGACY_UNUSED:
        raise ValueError('unrecognized PARSeq checkpoint keys: '+', '.join(sorted(unexpected-LEGACY_UNUSED)))
    removed = sorted(set(state) & LEGACY_UNUSED)
    compatible = copy(state)  # Preserve OrderedDict state_dict metadata and tensor objects.
    for key in removed:
        del compatible[key]
    model.load_state_dict(compatible, strict=True)
    return dict(policy='doctr0.12_unused_legacy_keys_then_strict',removed_unused_keys=removed,
                upstream='https://github.com/mindee/doctr/issues/1911',checkpoint_bytes_modified=False)
