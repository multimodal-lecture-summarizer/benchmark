"""Offline ordered reduction lineage and lexical proxies; no semantic scorer."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from .tib_benchmark_checkpoint import restore


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def reduction_diagnostic(result):
    """Inspect a saved summarize_source result without inference or tokenization.

    Resolve children by generation order, never a hash-to-one-node dictionary.
    Split-note edges cannot be reconstructed fully without native token IDs;
    fail closed on that topology instead of claiming verified input content.
    """
    nodes = result['nodes']
    identities = [(n['stage'], n['layer'], n['node']) for n in nodes]
    if len(set(identities)) != len(nodes):
        raise ValueError('Duplicate node identity')
    if any(_sha(n['output_text']) != n['output_sha256'] for n in nodes):
        raise ValueError('Saved node output hash mismatch')
    layers = {}
    for index, node in enumerate(nodes):
        layers.setdefault(node['layer'], []).append(index)
    cursors, leaves, rows, issues = {}, {}, [], []
    native_hashes = {}
    for index, node in enumerate(nodes):
        identity = ':'.join(map(str, identities[index]))
        child_hashes = node['ordered_child_output_sha256']
        native = node['ordered_child_native_ids_sha256']
        if len(native) != len(child_hashes):
            raise ValueError('Child native/output hash cardinality mismatch')
        previous = layers.get(node['layer'] - 1, [])
        cursor = cursors.get(node['layer'], 0)
        children = previous[cursor:cursor + len(child_hashes)]
        ordered_match = (len(children) == len(child_hashes) and
                         [nodes[c]['output_sha256'] for c in children] == child_hashes)
        lineage = [interval for child in children for interval in nodes[child]['source_intervals']]
        lineage_match = not child_hashes or lineage == node['source_intervals']
        if child_hashes and not (ordered_match and lineage_match):
            issues.append({'node_id': identity, 'issue': 'ordered_edge_unresolved_or_split_note'})
            children = []
        else:
            cursors[node['layer']] = cursor + len(child_hashes)
        leaf_ids = [leaf for child in children for leaf in leaves.get(child, [])]
        leaves[index] = leaf_ids if child_hashes else ([identity] if node['stage'] == 'map' else [])
        parent_words = _words(node['output_text'])
        child_rows = []
        for position, child in enumerate(children):
            child_node = nodes[child]
            # This checks recorded edge-hash consistency, not re-tokenization.
            hashes = native_hashes.setdefault(child, set())
            hashes.add(native[position])
            child_words = _words(child_node['output_text'])
            common = len(parent_words & child_words)
            child_rows.append({
                'position': position, 'node_id': ':'.join(map(str, identities[child])),
                'output_sha256': child_hashes[position],
                'recorded_native_ids_sha256': native[position],
                'exact_output_match': child_node['output_text'] == node['output_text'],
                'shared_unique_words': common,
                'child_unique_word_retention_proxy': common / len(child_words) if child_words else None,
                'parent_unique_word_overlap_proxy': common / len(parent_words) if parent_words else None,
            })
        rows.append({'node_id': identity, 'stage': node['stage'], 'layer': node['layer'],
                     'output_sha256': node['output_sha256'],
                     'output_text_tokens': node['output_text_tokens'],
                     'ordered_child_count': len(child_hashes),
                     'ordered_child_hash_alignment': ordered_match,
                     'ordered_lineage_alignment': lineage_match,
                     'incoming_map_leaf_count': len(leaf_ids),
                     'incoming_unique_map_leaf_count': len(set(leaf_ids)),
                     'child_text_tokens_total': sum(nodes[c]['output_text_tokens'] for c in children),
                     'output_to_child_text_token_ratio': (node['output_text_tokens'] /
                         sum(nodes[c]['output_text_tokens'] for c in children)) if children else None,
                     'zero_lexical_overlap_child_positions': [c['position'] for c in child_rows
                                                            if c['shared_unique_words'] == 0],
                     'exact_child_clone': any(c['exact_output_match'] for c in child_rows),
                     'multi_child_exact_clone_flag': len(child_rows) > 1 and any(c['exact_output_match'] for c in child_rows),
                     'children': child_rows})
    for layer, previous in ((layer, layers.get(layer - 1, [])) for layer in cursors):
        if cursors[layer] != len(previous):
            issues.append({'layer': layer, 'issue': 'unconsumed_previous_layer_nodes'})
    if any(len(values) != 1 for values in native_hashes.values()):
        issues.append({'issue': 'child_native_hash_varies_across_edges_or_slices'})
    intervals = sorted(result['source_intervals'])
    end = 0
    complete = bool(intervals)
    for start, stop in intervals:
        complete = complete and start <= end and stop > start
        end = max(end, stop)
    complete = complete and intervals[0][0] == 0 and end == result['source_token_count']
    maps = [n for n in nodes if n['stage'] == 'map']
    exact_maps = [':'.join(map(str, (n['stage'], n['layer'], n['node'])))
                  for n in maps if n['output_text'] == result['raw_final']]
    return {
        'scope': 'offline generation graph and lexical proxies only; not formal evaluation',
        'semantic_coverage_review': 'pending',
        'limitations': [
            'Token lineage shows input exposure, not retained facts or semantic completeness.',
            'Word overlap and exact clones are descriptive proxies, not factual or semantic scores.',
            'Token ratios describe compression; zero lexical overlap does not prove omitted meaning.',
            'Native child hashes are recorded evidence; no tokenizer or model was invoked.',
            'Split-note topology is unresolved rather than inferred from duplicate output hashes.',
        ],
        'full_source_token_lineage': complete,
        'ordered_graph_alignment_verified': not issues,
        'native_edge_hash_consistency': all(len(v) == 1 for v in native_hashes.values()),
        'native_edge_hashes_independently_retokenized': False,
        'source_token_count': result['source_token_count'],
        'map_windows': result['map_windows'],
        'stage_counts': dict(Counter(n['stage'] for n in nodes)),
        'maximum_generation_layer': max(layers),
        'raw_final_exact_map_matches': exact_maps,
        'final_exact_map_clone_with_multiple_windows': len(maps) > 1 and bool(exact_maps),
        'multi_child_clone_nodes': [r['node_id'] for r in rows if r['multi_child_exact_clone_flag']],
        'issues': issues, 'nodes': rows,
    }


def audit_directory(directory, candidate='bart'):
    """Read only completed saved result envelopes; omit all raw text in report."""
    directory = Path(directory)
    candidate_dir = directory / 'checkpoints' / candidate
    records = []
    for path in sorted(candidate_dir.glob('valid-*.json')):
        result = restore(path)
        if 'raw_final' not in result:
            continue
        records.append({'artifact': str(path.relative_to(directory)).replace('\\', '/'),
                        'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'diagnostic': reduction_diagnostic(result)})
    if not records:
        raise ValueError('No saved result artifacts found')
    return {'candidate_id': candidate, 'inference_run': False, 'scorer_run': False,
            'semantic_coverage_review': 'pending', 'records': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-directory', type=Path, required=True)
    parser.add_argument('--candidate', default='bart')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit_directory(args.evidence_directory, args.candidate)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
