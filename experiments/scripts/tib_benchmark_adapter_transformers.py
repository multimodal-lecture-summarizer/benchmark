"""Explicit loaded-model bindings. Importing this module never loads weights."""
from .tib_benchmark_adapter_budget import AdapterFailure, Budget, materialize_batch, plan_windows
from .tib_benchmark_generation_telemetry import generation_receipt


def encoder_wrapper(tokenizer):
    return lambda ids, stage: tokenizer.build_inputs_with_special_tokens(ids)


def causal_chat_wrapper(tokenizer, prompts):
    # Tokenize fixed chat scaffolding separately. Decoding a window and encoding
    # it again can corrupt a byte-level token split inside a Unicode character.
    marker = "__TIB_CANONICAL_CONTENT_SENTINEL_a9f41__"
    scaffolds = {}
    for stage, prompt in prompts.items():
        rendered = tokenizer.apply_chat_template(
            [{"role": "system", "content": prompt},
             {"role": "user", "content": marker}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        if not isinstance(rendered, str) or rendered.count(marker) != 1:
            raise AdapterFailure("chat template must preserve one unique content marker")
        prefix, suffix = rendered.split(marker)
        scaffolds[stage] = (tokenizer.encode(prefix, add_special_tokens=False),
                            tokenizer.encode(suffix, add_special_tokens=False))

    def wrap(ids, stage):
        prefix, suffix = scaffolds[stage]
        return list(prefix) + list(ids) + list(suffix)
    wrap.scaffold_ids = scaffolds
    return wrap


def native_bindings(tokenizer, profile):
    """Bind an explicit proposed/frozen profile without loading model weights."""
    architecture = profile["architecture"]
    wrapper = (causal_chat_wrapper(tokenizer, profile["prompts"])
               if architecture == "causal" else encoder_wrapper(tokenizer))
    budgets = {
        stage: Budget(architecture=architecture,
                      input_cap=profile.get("context_cap", profile.get("encoder_cap")),
                      max_new_tokens=profile[f"{stage}_max_new_tokens_including_EOS"],
                      decoder_cap=profile.get("decoder_cap"),
                      decoder_prefix_tokens=profile.get("decoder_prefix_tokens", 1),
                      padding_multiple=profile["padding_multiple"],
                      global_first_token=profile["candidate_id"] == "led")
        for stage in ("map", "reduce", "final")}
    return {"encode": lambda text: tokenizer.encode(text, add_special_tokens=False,
                                                    truncation=False),
            "decode": lambda ids: tokenizer.decode(ids, skip_special_tokens=False,
                                                    clean_up_tokenization_spaces=False),
            "wrapper": wrapper, "budgets": budgets}


def plan_profile_source(source, tokenizer, profile, *, overlap=0):
    """Measured tokenization/window planning only; no model/T4 feasibility claim."""
    bound = native_bindings(tokenizer, profile)
    ids = bound["encode"](source)
    windows = plan_windows(ids, bound["budgets"]["map"], bound["wrapper"], overlap=overlap)
    try:
        bound["budgets"]["final"].prepare(ids, bound["wrapper"], "final")
    except AdapterFailure:
        direct = False
    else:
        direct = True
    return {"candidate_id": profile["candidate_id"], "source_tokens": len(ids),
            "direct_final_fits_native_budget": direct,
            "planned_map_calls": 0 if direct else len(windows),
            "reduce_calls": None,
            "windows": [{"start": w["start"], "end": w["end"],
                         "wrapped_input_tokens": len(w["batch"]["input_ids"]),
                         "padded_input_tokens": w["batch"]["padded_length"]}
                        for w in windows],
            "full_source_token_coverage": (windows[0]["start"] == 0
                and windows[-1]["end"] == len(ids)
                and all(b["start"] <= a["end"] for a, b in zip(windows, windows[1:]))),
            "model_loaded": False, "generation_executed": False,
            "T4_capacity_verified": False}


class LoadedGenerator:
    """Caller supplies a pinned, explicitly placed model and decode parameters.

    This is an executable adapter, not evidence that any model fits a T4.
    No automatic quantization, offload, device map or truncation is introduced.
    """
    def __init__(self, model, tokenizer, *, architecture, device, decode_parameters,
                 led_global_attention=False):
        if architecture not in {"causal", "encoder_decoder"}:
            raise ValueError("unknown architecture")
        forbidden = {"max_length", "max_new_tokens", "truncation", "input_ids",
                     "attention_mask", "global_attention_mask"}
        if forbidden.intersection(decode_parameters):
            raise ValueError("decode parameters override adapter bounds")
        self.model, self.tokenizer = model, tokenizer
        self.architecture, self.device = architecture, device
        self.decode_parameters = dict(decode_parameters)
        self.led_global_attention = led_global_attention
        self.last_receipt = None

    def __call__(self, prepared, max_new_tokens, stage):
        import torch
        self.last_receipt = None
        batch = materialize_batch(prepared, self.tokenizer.pad_token_id)
        inputs = {key: torch.tensor([value], device=self.device, dtype=torch.long)
                  for key, value in batch.items()
                  if key != "global_attention_mask" or self.led_global_attention}
        self.model.eval()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens,
                                         **self.decode_parameters)
        sequence = output[0].tolist()
        if self.architecture == "causal":
            prompt = batch["input_ids"]
            if sequence[:len(prompt)] != prompt:
                raise AdapterFailure("causal output did not preserve prompt prefix")
            generated = sequence[len(prompt):]
        else:
            # Hugging Face encoder-decoder generate includes decoder start.
            generated = sequence[1:]
        if len(generated) > max_new_tokens:
            raise AdapterFailure("backend generated beyond native output reserve")
        text = self.tokenizer.decode(generated, skip_special_tokens=True,
                                     clean_up_tokenization_spaces=False)
        self.last_receipt = {"stage": stage, "generated_native_tokens": len(generated),
                             "generated_ids": generated, "device": str(self.device),
                             **generation_receipt(self.model, self.tokenizer,
                                self.decode_parameters, generated, max_new_tokens, text)}
        return text
