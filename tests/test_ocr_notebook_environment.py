"""Regression: native Colab kernel must not receive the OCR NumPy 1.x pin."""

import ast
import json
from pathlib import Path
import subprocess
import sys


NOTEBOOK = Path(__file__).resolve().parents[1] / 'experiments/notebooks/iiit_cvid_ocr_comparison_colab.ipynb'


def native_setup():
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    return ast.parse(''.join(notebook['cells'][1]['source']))


def test_native_installer_keeps_preloaded_binary_stack():
    commands = []
    for node in ast.walk(native_setup()):
        if isinstance(node, ast.List):
            strings = [v.value for v in node.elts if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            if 'pip' in strings and 'install' in strings:
                commands.append(strings)
    assert len(commands) == 1
    assert set(commands[0]) == {'-m', 'pip', 'install', '-q', 'huggingface_hub==0.30.2', 'uv==0.6.17'}


def test_scientific_preflight_checks_actual_binary_imports_and_rendering():
    assignment = next(node for node in native_setup().body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'probe' for t in node.targets))
    probe = ast.literal_eval(assignment.value)
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    versions = json.loads(result.stdout.strip().splitlines()[-1])
    assert set(versions) == {'numpy', 'pandas', 'matplotlib', 'Pillow', 'python'}


def test_isolated_paddle_environment_installs_setuptools_explicitly():
    # uv venv is unseeded; Paddle's cpp_extension imports setuptools at import time.
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    setup = next(''.join(c['source']) for c in notebook['cells']
                 if c['cell_type'] == 'code' and 'ENV = WORK' in ''.join(c['source']))
    commands = []
    for node in ast.walk(ast.parse(setup)):
        if isinstance(node, ast.List):
            strings = [v.value for v in node.elts if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            if 'paddlepaddle==2.6.2' in strings:
                commands.append(strings)
    assert len(commands) == 1
    assert 'setuptools==75.8.0' in commands[0]
    assert '--python' in commands[0]
