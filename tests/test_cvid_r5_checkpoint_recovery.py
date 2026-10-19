"""Audit-specific restoration must never change a sealed prediction or receipt."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT.parent/'docs/recover-cvid-r5-doctr-checkpoint.py'
SPEC = importlib.util.spec_from_file_location('cvid_recovery', SCRIPT)
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)
EVIDENCE = Path('C:/Users/hung/Downloads/cvid-spotting-t4-261015-v2-r5-evidence (1).zip')


@unittest.skipUnless(EVIDENCE.is_file(), 'Requires the local user-provided R5 evidence archive')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        base = ROOT/'experiments/outputs/colab-contract-tests'
        base.mkdir(exist_ok=True, parents=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        names = list(RECOVERY.ANCHORS['anchors']) + [
            RECOVERY.ANCHORS['candidate']+'/predictions.jsonl', RECOVERY.ANCHORS['checkpoint_relative']]
        with ZipFile(EVIDENCE) as archive:
            for name in names:
                path = self.root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
        self.target = self.root/RECOVERY.ANCHORS['checkpoint_relative']

    def tearDown(self):
        self.temp.cleanup()

    def test_restores_exact_audited_payload_and_is_idempotent(self):
        before = {name: (self.root/name).read_bytes() for name in RECOVERY.ANCHORS['anchors']}
        RECOVERY.recover(self.root)
        self.assertEqual(RECOVERY.sha(self.target.read_bytes()), RECOVERY.ANCHORS['expected_checkpoint_sha256'])
        self.assertEqual(self.target.stat().st_size, 3158)
        RECOVERY.recover(self.root)
        self.assertEqual(len(list((self.root/'recovery-audit').glob('*/complete.json'))), 1)
        self.assertTrue(all((self.root/name).read_bytes() == value for name, value in before.items()))

    def test_altered_aggregate_is_rejected_before_write(self):
        path = self.root/RECOVERY.ANCHORS['candidate']/'predictions.jsonl'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'Aggregate hash differs'):
            RECOVERY.recover(self.root)
        self.assertEqual(self.target.read_bytes(), b'')

    def test_nonempty_different_checkpoint_is_never_overwritten(self):
        self.target.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'nonempty and differs'):
            RECOVERY.recover(self.root)
        self.assertEqual(self.target.read_bytes(), b'changed')

    def test_execution_lock_blocks_repair(self):
        (self.root/'.execution.lock').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Execution lock remains'):
            RECOVERY.recover(self.root)
        self.assertEqual(self.target.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
