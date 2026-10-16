"""Cache replay retains request provenance and cannot clear sealed environments."""
from pathlib import Path
import tempfile
import unittest

from experiments.scripts.spotting_colab_replay import replay_commands


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.directory = self.work/'environments/orchestrator'
        self.directory.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def commands(self):
        return replay_commands(['uv'],self.work,self.directory,'3.11.11',
                               self.work/'cache/wheels',self.directory/'resolved.txt',
                               ['pip==25.0.1','pandas==2.2.3'])

    def test_freeze_is_constraints_and_only_original_roots_are_requested(self):
        create, install = self.commands()
        self.assertIn('--constraint',install)
        self.assertNotIn('-r',install)
        self.assertEqual(install[-2:],['pip==25.0.1','pandas==2.2.3'])
        self.assertIn('--no-index',install)
        self.assertEqual(create[-1],self.directory/'venv')
        self.assertIn('--clear',create)

    def test_sealed_environment_cannot_be_cleared(self):
        (self.directory/'environment-seal.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'sealed environment'):
            self.commands()

    def test_target_cannot_escape_work_environments(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            replay_commands(['uv'],self.work,self.work/'outside','3.11',self.work/'w',self.work/'r',[])

    def test_clear_is_only_for_ephemeral_venv_not_cache_or_output(self):
        create, install = self.commands()
        self.assertEqual(create.count('--clear'),1)
        self.assertNotIn(self.work/'cache/wheels',create)
        self.assertNotIn('--force-reinstall',install)


if __name__=='__main__':
    unittest.main()
