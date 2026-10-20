"""Source-only pilot packaging and executable notebook syntax without GPU work."""
import ast
import json
from pathlib import Path

import pytest

from experiments.scripts import tib_pilot_bundle as builder
from experiments.scripts import tib_pilot_notebook as notebook


@pytest.fixture(scope='module')
def source_frame():
    return builder.sources()


def test_exact_sealed40_source_only_and_strata(source_frame):
    cohort, rows, rights = source_frame
    assert [r['record_id'] for r in rows] == cohort['selected_ids']['pilot']
    assert len(rows) == len(rights) == 40
    assert not set(cohort['selected_ids']['pilot']) & set(cohort['selected_ids']['selection'])
    for row in rows:
        assert not any('reference' in key or 'abstract' in key for key in row)
        assert row['attribution']['conditions_recorded']['private_only'] is True
    assert cohort['pilot_quotas'] == {'short': 13, 'medium': 12, 'long': 15}


def test_allocations_are_totals_with_nested_reserves():
    a = builder.pilot_allocation()
    assert (a['total_gpu_hours'], a['total_cpu_hours'], a['total_wall_hours']) == (11.5, 23, 11.5)
    assert a['max_sessions'] == 2 and a['session_headroom_fraction'] == .15
    assert a['scoring_gpu_hours'] == 1.5 and a['scoring_cpu_hours'] == 3
    assert a['minimum_local_free_bytes'] == 32*1024**3
    assert a['local_working_storage_bytes'] == 24*1024**3
    assert a['transfer_bytes'] == 16*1024**3
    assert a['retry_limit_per_node'] == a['pilot_metric_tuning_trial_cap_per_candidate'] == 0


def test_real_private_builder_validates_without_loading_models(tmp_path, monkeypatch):
    from experiments.scripts.tib_pilot_validation import validate_bundle
    from experiments.scripts.tib_pilot_resources import allocated
    from experiments.scripts.tib_pilot_session import validate_allocation, begin_session
    monkeypatch.setattr(builder, 'LOCAL', tmp_path/'private')
    monkeypatch.setattr(builder, 'REGISTRY', tmp_path/'registry')
    prepared = builder.build()
    contract, rows, manifest_sha = validate_bundle(tmp_path/'private/package')
    assert len(rows) == 40 and len(contract['profiles']) == 5
    assert manifest_sha == prepared['manifest_sha256']
    allocation = builder.pilot_allocation()
    allocated(allocation, 11.5)
    validate_allocation(allocation)
    ledger = begin_session(tmp_path/'ledger.json', allocation, manifest_sha,
        local_working_root=tmp_path/'working',
        observation={'boot_id': 'test-vm', 'monotonic': 100., 'epoch_ns': 1000, 'logical_cpu_count': 2})
    assert ledger['bundle_sha256'] == manifest_sha


def test_generated_notebook_syntax_identity_and_scope(tmp_path, monkeypatch):
    registry = tmp_path / 'registry'
    registry.mkdir()
    (registry/'preparation_receipt.json').write_text(json.dumps({
        'archive_sha256': 'a'*64, 'manifest_sha256': 'b'*64}))
    (tmp_path/'experiments/notebooks').mkdir(parents=True)
    monkeypatch.setattr(notebook, 'REGISTRY', registry)
    monkeypatch.setattr(notebook, 'ROOT', tmp_path)
    result = notebook.create()
    data = json.loads(Path(result['path']).read_text(encoding='utf-8'))
    code = [c for c in data['cells'] if c['cell_type'] == 'code']
    for cell in code:
        ast.parse(''.join(cell['source']))
        assert cell['execution_count'] is None and cell['outputs'] == []
    sources = '\n'.join(''.join(c['source']) for c in code)
    assert "'tib_pilot_runtime'" not in sources  # use the full module namespace
    assert 'experiments.scripts.tib_pilot_runtime' in sources
    assert 'record_setup(' in sources and 'begin_session(' in sources
    assert 'finish_session(' in sources
    assert '--without-pip' in sources
    assert '--allow-deferred-trial' not in sources
    assert 'RuntimeSemanticScorer(' not in sources
    assert "HF_HOME=str(WORK/'hf-cache')" in sources
