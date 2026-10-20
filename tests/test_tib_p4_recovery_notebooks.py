"""Fresh-session notebook syntax and preflight ordering, without Colab execution."""
import ast
import json
from pathlib import Path

import pytest

from experiments.scripts import tib_p4_recovery_notebooks as notebooks


@pytest.fixture
def generated(tmp_path, monkeypatch):
    registry = tmp_path / 'registry'
    registry.mkdir()
    (tmp_path / 'experiments/notebooks').mkdir(parents=True)
    (registry / 'preparation_receipt.json').write_text(json.dumps({
        'archive_sha256': 'a' * 64, 'manifest_sha256': 'b' * 64}))
    monkeypatch.setattr(notebooks, 'REGISTRY', registry)
    monkeypatch.setattr(notebooks, 'ROOT', tmp_path)
    result = notebooks.create()
    return {kind: json.loads(Path(row['path']).read_text(encoding='utf-8')) for kind, row in result.items()}


def test_both_notebooks_compile_and_make_no_execution_claim(generated):
    for notebook in generated.values():
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                ast.parse(''.join(cell['source']))
                assert cell['execution_count'] is None and cell['outputs'] == []
    origin = [''.join(c['source']) for c in generated['handoff']['cells'] if c['cell_type'] == 'code']
    assert len(origin) == 2
    assert 'seal_origin(PACKAGE,DRIVE,WITNESS)' in origin[-1]
    assert all("'install'" not in source and 'gen_command' not in source for source in origin)


def test_same_vm_refusal_precedes_context_creation_and_install(generated):
    source = next(''.join(c['source']) for c in generated['fresh-recovery']['cells']
                  if c['cell_type'] == 'code' and 'RECOVERY_PREFLIGHT_OK=False' in ''.join(c['source']))
    called = []
    def fail(*args):
        raise ValueError('Same VM/session')
    environment = {'verify_fresh': fail, 'PACKAGE': None, 'DRIVE': None, 'WITNESS': None,
                   'create_run_context': lambda *args: called.append(True)}
    with pytest.raises(ValueError, match='Same VM'):
        exec(source, environment)
    assert not called and environment['RECOVERY_PREFLIGHT_OK'] is False


def test_separate_original_bundle_import_roots_and_context_passed_to_each_stage(generated):
    code = [''.join(c['source']) for c in generated['fresh-recovery']['cells'] if c['cell_type'] == 'code']
    gen = next(source for source in code if 'gen_command=' in source)
    scorer = next(source for source in code if 'score_command=' in source)
    assert "RUN_ENV['PYTHONPATH']=str(PACKAGE/'generation_bundle')" in gen
    assert "RUN_ENV['PYTHONPATH']=str(PACKAGE/'scorer_bundle')" in scorer
    assert "'--session-context',str(CONTEXT)" in gen
    assert "'--session-context',str(CONTEXT)" in scorer
    assert '--resume' not in scorer  # no old scorer runner fixture/model calls
