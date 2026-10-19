"""Offline diagnostics distinguish ordered exposure from output content."""
import copy
import hashlib

import pytest

from experiments.scripts.tib_benchmark_reduction_diagnostics import reduction_diagnostic


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def node(stage, layer, number, text, intervals, children=()):
    return {'stage': stage, 'layer': layer, 'node': number, 'output_text': text,
            'output_sha256': sha(text), 'output_text_tokens': len(text.split()),
            'source_intervals': intervals,
            'ordered_child_output_sha256': [c['output_sha256'] for c in children],
            'ordered_child_native_ids_sha256': [sha('native:' + c['output_text']) for c in children]}


def sample(repeated=False):
    maps = [node('map', 0, i, text, [[i * 10, (i + 1) * 10]])
            for i, text in enumerate(['alpha key', 'alpha key' if repeated else 'beta finding',
                                      'gamma result', 'delta note'])]
    reduced = [node('reduce', 1, i, maps[2 * i]['output_text'],
                    maps[2 * i]['source_intervals'] + maps[2 * i + 1]['source_intervals'],
                    maps[2 * i:2 * i + 2]) for i in range(2)]
    final = node('final', 2, 0, reduced[0]['output_text'],
                 reduced[0]['source_intervals'] + reduced[1]['source_intervals'], reduced)
    return {'nodes': maps + reduced + [final], 'source_intervals': final['source_intervals'],
            'source_token_count': 40, 'map_windows': 4, 'raw_final': final['output_text']}


def test_full_exposure_does_not_imply_retained_content():
    report = reduction_diagnostic(sample())
    assert report['full_source_token_lineage']
    assert report['ordered_graph_alignment_verified']
    assert report['raw_final_exact_map_matches'] == ['map:0:0']
    assert report['final_exact_map_clone_with_multiple_windows']
    assert report['nodes'][-1]['incoming_unique_map_leaf_count'] == 4
    assert report['semantic_coverage_review'] == 'pending'
    assert report['nodes'][-1]['children'][1]['child_unique_word_retention_proxy'] == 0


def test_repeated_hashes_preserve_ordered_distinct_child_identity():
    report = reduction_diagnostic(sample(repeated=True))
    assert report['ordered_graph_alignment_verified']
    assert [c['node_id'] for c in report['nodes'][4]['children']] == ['map:0:0', 'map:0:1']
    assert report['raw_final_exact_map_matches'] == ['map:0:0', 'map:0:1']
    assert report['nodes'][-1]['incoming_unique_map_leaf_count'] == 4


def test_repeated_hash_across_reduction_groups_retains_both_children():
    result = sample()
    for index in (2, 5, 6):
        result['nodes'][index]['output_text'] = 'alpha key'
        result['nodes'][index]['output_sha256'] = sha('alpha key')
    for index, children in ((4, [0, 1]), (5, [2, 3]), (6, [4, 5])):
        result['nodes'][index]['ordered_child_output_sha256'] = [
            result['nodes'][c]['output_sha256'] for c in children]
        result['nodes'][index]['ordered_child_native_ids_sha256'] = [
            sha('native:' + result['nodes'][c]['output_text']) for c in children]
    report = reduction_diagnostic(result)
    assert report['ordered_graph_alignment_verified']
    assert [c['node_id'] for c in report['nodes'][-1]['children']] == ['reduce:1:0', 'reduce:1:1']
    assert report['nodes'][-1]['incoming_unique_map_leaf_count'] == 4


def test_ordered_child_corruption_fails_closed():
    result = sample()
    result['nodes'][4]['ordered_child_output_sha256'].reverse()
    report = reduction_diagnostic(result)
    assert not report['ordered_graph_alignment_verified']
    assert report['issues'][0]['issue'] == 'ordered_edge_unresolved_or_split_note'


def test_duplicate_hash_lineage_swap_is_detected():
    result = sample(repeated=True)
    result['nodes'][4]['source_intervals'].reverse()
    assert not reduction_diagnostic(result)['ordered_graph_alignment_verified']


def test_output_corruption_raises():
    result = sample()
    result['nodes'][0]['output_text'] = 'corrupt'
    with pytest.raises(ValueError, match='hash mismatch'):
        reduction_diagnostic(result)


def test_source_gap_not_complete():
    result = copy.deepcopy(sample())
    result['source_intervals'][1][0] = 11
    assert not reduction_diagnostic(result)['full_source_token_lineage']


def test_direct_final_has_no_map_clone():
    final = node('final', 0, 0, 'short answer', [[0, 10]])
    result = {'nodes': [final], 'source_intervals': [[0, 10]], 'source_token_count': 10,
              'map_windows': 0, 'raw_final': 'short answer'}
    report = reduction_diagnostic(result)
    assert report['ordered_graph_alignment_verified']
    assert report['full_source_token_lineage']
    assert not report['final_exact_map_clone_with_multiple_windows']


def test_mismatching_native_cardinality_raises():
    result = sample()
    result['nodes'][4]['ordered_child_native_ids_sha256'].pop()
    with pytest.raises(ValueError, match='cardinality'):
        reduction_diagnostic(result)
