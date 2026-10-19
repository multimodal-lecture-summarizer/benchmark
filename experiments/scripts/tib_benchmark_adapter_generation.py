"""Injected native generation with full-source lineage and bounded reduction."""
from dataclasses import dataclass
import hashlib
import json
import time

from .tib_benchmark_adapter_budget import AdapterFailure, plan_windows


@dataclass(frozen=True)
class Note:
    text: str
    intervals: tuple
    token_ids: tuple


def stable_node_seed(study, record_id, profile_hash, layer, node, base_seed):
    key = repr((study, record_id, profile_hash, layer, node, base_seed))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big")


def summarize_source(source, *, encode, decode, wrapper, generate, budgets,
                     selector, word_cap, max_depth=8, overlap=0, separator="\n\n",
                     on_node=None):
    """Backend signature: generate(prepared_batch, max_new_tokens, stage)->str.

    Backend must consume every unmasked input token and return only generated
    text (causal prompts must be stripped). No abstract/reference argument exists.
    on_node receives each completed node immediately, enabling durable checkpoint
    integration by a caller; this function alone does not promise resumability.
    """
    if max_depth < 1 or word_cap < 1:
        raise ValueError("positive depth and word cap required")
    ids = list(encode(source))
    nodes = []

    def call(text_ids, stage, layer, index, intervals, children=()):
        budget = budgets[stage]
        batch = budget.prepare(text_ids, wrapper, stage)
        if hasattr(generate, "set_node_context"):
            generate.set_node_context({"layer": layer, "node": index,
                                      "source_intervals": [list(x) for x in intervals]})
        started = time.perf_counter()
        text = generate(batch, budget.max_new_tokens, stage)
        if not isinstance(text, str) or not text.strip():
            raise AdapterFailure("empty generated node")
        # Count generated EOS in the backend receipt too; plain text can only
        # establish this necessary, not sufficient, output-budget check.
        output_tokens = tuple(encode(text))
        count = len(output_tokens)
        if count > budget.max_new_tokens:
            raise AdapterFailure("generated text exceeds native reserve")
        node = {"stage": stage, "layer": layer, "node": index,
                "source_intervals": [list(x) for x in intervals],
                "input_tokens": len(batch["input_ids"]),
                "padded_input_tokens": batch["padded_length"],
                "output_text_tokens": count, "output_text": text,
                "canonical_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "wrapped_input_ids_sha256": hashlib.sha256(
                    json.dumps(batch["input_ids"], separators=(",", ":")).encode()).hexdigest(),
                "ordered_child_output_sha256": [hashlib.sha256(n.text.encode()).hexdigest()
                                                 for n in children],
                "ordered_child_native_ids_sha256": [hashlib.sha256(
                    json.dumps(n.token_ids, separators=(",", ":")).encode()).hexdigest()
                    for n in children],
                "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "wall_seconds": time.perf_counter() - started}
        nodes.append(node)
        if on_node is not None:
            on_node(node)
        return Note(text, intervals, output_tokens)

    def deliver(final, window_count):
        delivery = selector(final.text, word_cap)
        delivered = delivery["text"]
        if not isinstance(delivered, str) or not delivered.strip():
            raise AdapterFailure("empty delivered output")
        if len(delivered.split()) > word_cap:
            raise AdapterFailure("delivered selector violated global cap")
        return {"raw_final": final.text, "delivered_final": delivered,
                "source_token_count": len(ids), "map_windows": window_count,
                "source_intervals": [list(x) for x in final.intervals],
                "delivery": delivery, "nodes": nodes}

    if not ids:
        raise AdapterFailure("empty canonical source")
    try:
        budgets["final"].prepare(ids, wrapper, "final")
    except AdapterFailure:
        pass
    else:
        return deliver(call(ids, "final", 0, 0, ((0, len(ids)),)), 0)

    windows = plan_windows(ids, budgets["map"], wrapper, overlap=overlap)
    notes = [call(ids[w["start"]:w["end"]], "map", 0, i,
                  ((w["start"], w["end"]),)) for i, w in enumerate(windows)]
    for layer in range(1, max_depth + 1):
        if len(notes) == 1:
            final = notes[0]
            # Always use the independently declared final reserve/profile.
            final = call(list(final.token_ids), "final", layer, 0, final.intervals, (final,))
            return deliver(final, len(windows))
        before_tokens = sum(len(n.token_ids) for n in notes)
        # An oversized singleton is split in source order with lineage retained.
        expanded = []
        for note in notes:
            tokens = list(note.token_ids)
            for window in plan_windows(tokens, budgets["reduce"], wrapper, "reduce"):
                expanded.append(Note(note.text, note.intervals,
                                     tuple(tokens[window["start"]:window["end"]])))
        separator_ids = list(encode(separator))

        def concatenate(group):
            payload = []
            for position, note in enumerate(group):
                if position:
                    payload.extend(separator_ids)
                payload.extend(note.token_ids)
            return payload

        groups, current = [], []
        for note in expanded:
            proposal = current + [note]
            try:
                budgets["reduce"].prepare(concatenate(proposal), wrapper, "reduce")
            except AdapterFailure:
                if len(current) < 2:
                    raise AdapterFailure("reducer cannot fit fan-in >= 2")
                groups.append(current)
                current = [note]
            else:
                current = proposal
        if len(current) == 1:
            if not groups or len(groups[-1]) < 3:
                raise AdapterFailure("singleton reduction group; amend profile")
            current.insert(0, groups[-1].pop())
        if current:
            groups.append(current)
        reduced = [call(concatenate(group), "reduce", layer, i,
                        tuple(interval for n in group for interval in n.intervals), group)
                   for i, group in enumerate(groups)]
        if len(reduced) >= len(notes) or sum(len(n.token_ids) for n in reduced) >= before_tokens:
            raise AdapterFailure("reduction does not reduce note count and native tokens")
        notes = reduced
    raise AdapterFailure("maximum reduction depth reached")
