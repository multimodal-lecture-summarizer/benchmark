"""Native-token budgets. No generation or reference text enters this module."""
from dataclasses import dataclass
import math


class AdapterFailure(RuntimeError):
    """Keep the record in the denominator when a runtime contract fails."""


@dataclass(frozen=True)
class Budget:
    architecture: str
    input_cap: int
    max_new_tokens: int
    decoder_cap: int | None = None
    decoder_prefix_tokens: int = 1
    padding_multiple: int = 1
    global_first_token: bool = False

    def __post_init__(self):
        if self.architecture not in {"causal", "encoder_decoder"}:
            raise ValueError("unknown architecture")
        if min(self.input_cap, self.max_new_tokens, self.padding_multiple) < 1:
            raise ValueError("positive native budgets required")
        if self.decoder_prefix_tokens < 0:
            raise ValueError("negative decoder prefix")
        if self.architecture == "encoder_decoder" and (
            self.decoder_cap is None
            or self.decoder_prefix_tokens + self.max_new_tokens > self.decoder_cap
        ):
            raise ValueError("decoder prefix + generated tokens/EOS exceed cap")

    def prepare(self, token_ids, wrapper, stage):
        wrapped = list(wrapper(list(token_ids), stage))
        if not wrapped:
            raise AdapterFailure("empty wrapped input")
        padded = math.ceil(len(wrapped) / self.padding_multiple) * self.padding_multiple
        reserve = self.max_new_tokens if self.architecture == "causal" else 0
        if padded + reserve > self.input_cap:
            raise AdapterFailure("native input/padding/output reserve overflow")
        mask = [1] * len(wrapped) + [0] * (padded - len(wrapped))
        global_mask = [0] * padded
        if self.global_first_token:
            global_mask[0] = 1
        return {"input_ids": wrapped, "attention_mask": mask,
                "padded_length": padded, "global_attention_mask": global_mask,
                "padding_tokens": padded - len(wrapped)}


def plan_windows(token_ids, budget, wrapper, stage="map", overlap=0):
    """Cover every source token; wrapper tokens are counted for each window.

    Linear descending search is deliberate: arbitrary wrappers need not have a
    monotonic token cost. Receipts report token intervals in the canonical input.
    """
    if not token_ids:
        raise AdapterFailure("empty canonical source")
    if overlap < 0 or overlap >= budget.input_cap:
        raise ValueError("invalid overlap")
    result, start = [], 0
    while start < len(token_ids):
        payload_ceiling = budget.input_cap - (
            budget.max_new_tokens if budget.architecture == "causal" else 0)
        end = min(len(token_ids), start + max(0, payload_ceiling))
        while end > start:
            try:
                prepared = budget.prepare(token_ids[start:end], wrapper, stage)
                break
            except AdapterFailure:
                end -= 1
        if end == start:
            raise AdapterFailure("wrapper leaves no source capacity")
        result.append({"start": start, "end": end, "batch": prepared})
        if end == len(token_ids):
            break
        following = end - overlap
        if following <= start:
            raise AdapterFailure("overlap prevents progress")
        start = following
    return result


def materialize_batch(prepared, pad_token_id):
    """Apply the already-budgeted right padding before backend tensor creation."""
    if prepared["padding_tokens"] and pad_token_id is None:
        raise AdapterFailure("padding requested without pad token")
    return {"input_ids": prepared["input_ids"] + [pad_token_id] * prepared["padding_tokens"],
            "attention_mask": list(prepared["attention_mask"]),
            "global_attention_mask": list(prepared["global_attention_mask"])}
