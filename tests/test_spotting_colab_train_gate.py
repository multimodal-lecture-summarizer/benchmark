"""Regression checks for lazy warm-up work and fail-closed mismatch diagnostics."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from experiments.scripts.spotting_colab_execution import execute_worker_job
from experiments.scripts.spotting_colab_state import read, sha
from experiments.scripts.spotting_colab_train_gate import difference, observe_train
from experiments.scripts.spotting_metrics import prediction_polygon


class TrainGateTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1]/'experiments/outputs/colab-contract-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        image = self.root/'train.png'
        Image.new('RGB', (20, 20), 'white').save(image)
        self.train = dict(frame_id='Frames/train/1/1/a.png', path=str(image), image_sha256=sha(image))
        # This path deliberately does not exist: a mismatch must never reach test pixels.
        self.test = dict(frame_id='Frames/test/1/1/a.png', path=str(self.root/'unread-test.png'), image_sha256='x')
        self.region = dict(polygon=[[1, 1], [10, 1], [10, 10], [1, 10]], text='word')
        self.job = dict(candidate={'candidate_id': 'fixture'}, output_root=str(self.root),
                        run_binding={'data': 'fixed'}, prepared={'weights': 'fixed'},
                        mode='preflight', inputs=[self.train])

    def tearDown(self):
        self.temp.cleanup()

    def test_both_phases_decode_and_validate_geometry_before_native_seal(self):
        with patch('PIL.Image.open', wraps=Image.open) as opened, patch(
                'experiments.scripts.spotting_metrics.prediction_polygon', wraps=prediction_polygon) as polygon:
            def libraries():
                self.assertEqual(opened.call_count, 1)
                self.assertEqual(polygon.call_count, 1)
                return {'same-loaded-library': 'same-bytes'}
            with patch('experiments.scripts.spotting_colab_execution.native_libraries', side_effect=libraries):
                gate = execute_worker_job(self.job, lambda _: [self.region], {'device': 'cpu'})
                opened.reset_mock(); polygon.reset_mock()
                self.job.update(mode='infer', inputs=[], train_inputs=[self.train])
                result = execute_worker_job(self.job, lambda _: [self.region], {'device': 'cpu'})
                self.assertEqual(result['binding'], gate['binding'])

    def test_runtime_mismatch_saves_both_snapshots_and_never_reads_test(self):
        with patch('experiments.scripts.spotting_colab_execution.native_libraries', return_value={}):
            execute_worker_job(self.job, lambda _: [self.region], {'device': 'original'})
            gate_path = self.root/'fixture/preflight.json'; original = gate_path.read_bytes()
            self.job.update(mode='infer', inputs=[self.test], train_inputs=[self.train])
            calls = []
            def predictor(path):
                calls.append(path)
                return [self.region]
            with self.assertRaisesRegex(ValueError, 'runtime/config differs'):
                execute_worker_job(self.job, predictor, {'device': 'changed'})
            paths = list((self.root/'fixture/diagnostics').glob('*.json'))
            self.assertEqual(len(paths), 1)
            report = read(paths[0])
            self.assertEqual(report['runtime_diff'], [dict(path='/device', change='changed',
                                                           expected='original', actual='changed')])
            self.assertFalse(report['test_inference_started'])
            self.assertNotEqual(report['actual_binding'], report['expected_binding'])
            self.assertEqual(gate_path.read_bytes(), original)
            self.assertEqual(calls, [Path(self.train['path'])])
            self.assertFalse((self.root/'fixture/records').exists())

    def test_native_library_drift_remains_blocked_and_is_not_filtered(self):
        with patch('experiments.scripts.spotting_colab_execution.native_libraries', return_value={'a.so': 'original'}):
            execute_worker_job(self.job, lambda _: [self.region], {})
        self.job.update(mode='infer', inputs=[self.test], train_inputs=[self.train])
        with patch('experiments.scripts.spotting_colab_execution.native_libraries', return_value={'a.so': 'changed', 'b.so': 'added'}):
            with self.assertRaisesRegex(ValueError, 'runtime/config differs'):
                execute_worker_job(self.job, lambda _: [self.region], {})
        report = read(next((self.root/'fixture/diagnostics').glob('*.json')))
        self.assertEqual(len(report['runtime_diff']), 2)
        self.assertTrue(all(r['path'].startswith('/loaded_native_sha256/') for r in report['runtime_diff']))

    def test_warmup_cannot_skip_geometry_or_train_split_checks(self):
        invalid = copy.deepcopy(self.region); invalid['polygon'][0] = [-1, -1]
        with self.assertRaisesRegex(ValueError, 'invalid geometry'):
            observe_train([self.train], lambda _: [invalid], None)
        with self.assertRaisesRegex(ValueError, 'train only'):
            observe_train([self.test], lambda _: [self.region], None)

    def test_separate_process_verification_mode_never_reaches_test_or_records(self):
        with patch('experiments.scripts.spotting_colab_execution.native_libraries', return_value={}):
            gate = execute_worker_job(self.job, lambda _: [self.region], {})
            self.job.update(mode='verify', inputs=[self.test], train_inputs=[self.train])
            calls = []
            def predictor(path):
                calls.append(path)
                return [self.region]
            result = execute_worker_job(self.job, predictor, {})
            self.assertEqual(result['binding'], gate['binding'])
            self.assertTrue(result['no_test_inference'])
            self.assertEqual(calls, [Path(self.train['path'])])
            self.assertFalse((self.root/'fixture/records').exists())
            self.assertFalse((self.root/'fixture/candidate-complete.json').exists())
            self.assertEqual(read(self.root/'fixture/train-replay.json'), result)

    def test_diff_tracks_removed_added_and_changed_fields_with_safe_paths(self):
        rows = difference({'a/b': 'old', 'removed': 1}, {'a/b': 'new', 'added': 2})
        self.assertEqual([r['path'] for r in rows], ['/a~1b', '/added', '/removed'])
        self.assertEqual([r['change'] for r in rows], ['changed', 'added', 'removed'])


if __name__ == '__main__':
    unittest.main()
