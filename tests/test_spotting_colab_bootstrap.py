"""Bootstrap regression: unseeded and partially created venvs avoid ensurepip."""
from pathlib import Path
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.scripts import spotting_colab_environments as env


class BootstrapTests(unittest.TestCase):
    def test_worker_keeps_driver_after_candidate_libraries(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH':'/usr/lib64-nvidia:/host/lib'}):
            self.assertEqual(env.worker_library_path({'library_paths':['/venv/cudnn/lib','/venv/cuda/lib']}),
                             '/venv/cudnn/lib:/venv/cuda/lib:/usr/lib64-nvidia:/host/lib')

    def test_worker_deduplicates_and_removes_empty_entries(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH':':/driver:/venv/lib::/driver:'}):
            self.assertEqual(env.worker_library_path({'library_paths':['/venv/lib']}), '/venv/lib:/driver')
        with patch.dict(os.environ, {'LD_LIBRARY_PATH':''}):
            self.assertEqual(env.worker_library_path({}), '')

    def check_unseeded(self, interpreter_exists):
        work = Path('/qualification/work')
        python = work/'bootstrap/bin/python'
        with patch.object(Path, 'exists', return_value=interpreter_exists), \
             patch.object(env.subprocess, 'run', return_value=SimpleNamespace(returncode=1)), \
             patch.object(env, 'run', return_value=SimpleNamespace(stdout='uv 0.8.22\n')) as run:
            result = env._uv(work)
        self.assertEqual(result, [python, '-m', 'uv'])
        commands = [call.args[0] for call in run.call_args_list]
        if not interpreter_exists:
            self.assertEqual(commands[0], [env.sys.executable, '-m', 'venv', '--without-pip', work/'bootstrap'])
        self.assertIn([env.sys.executable, '-m', 'pip', '--python', python,
                       'install', '--no-deps', 'uv==0.8.22'], commands)
        self.assertNotIn([python, '-m', 'pip', 'install', 'uv==0.8.22'], commands)

    def test_fresh_unseeded_environment(self):
        self.check_unseeded(False)

    def test_recover_partial_ensurepip_environment(self):
        self.check_unseeded(True)

    def test_existing_wrong_version_is_rejected(self):
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(env.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
             patch.object(env, 'run', return_value=SimpleNamespace(stdout='uv 9.9.9\n')):
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                env._uv(Path('/qualification/work'))


if __name__ == '__main__':
    unittest.main()
