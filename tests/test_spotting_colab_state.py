"""Regression checks for foreign checkpoints and strict train-only admission."""
from pathlib import Path
import tempfile
import unittest

from experiments.scripts.spotting_colab_state import (
    commit_record, digest, load_records, read, sha, validate_record, write_once,
)
from experiments.scripts.spotting_colab_execution import execute_worker_job
from experiments.scripts.run_spotting_colab import exclusive_run


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'experiments/outputs/colab-contract-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.tmp.name)
        self.frame = dict(frame_id='Frames/test/1/1/a.png', image_sha256='a' * 64)
        self.record = dict(frame_id=self.frame['frame_id'], status='ok', predictions=[], error=None)
        self.binding = {'candidate': 'a', 'weights': 'b'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_immutable_resume_and_foreign_identity_rejected(self):
        commit_record(self.root, 'a', self.binding, self.frame, self.record)
        commit_record(self.root, 'a', self.binding, self.frame, self.record)
        records = load_records(self.root, 'a', self.binding, [self.frame])
        self.assertEqual(records[self.frame['frame_id']], self.record)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            load_records(self.root, 'a', {'candidate': 'changed'}, [self.frame])

    def test_checkpoint_alteration_and_extra_frame_rejected(self):
        commit_record(self.root, 'a', self.binding, self.frame, self.record)
        path = next(self.root.rglob('*.json'))
        item = read(path)
        item['record']['status'] = 'error'
        import json
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            load_records(self.root, 'a', self.binding, [self.frame])
        with self.assertRaisesRegex(ValueError, 'extra or duplicate'):
            load_records(self.root, 'a', self.binding, [])

    def test_failure_cannot_retain_predictions(self):
        record = dict(self.record, status='error', error='OOM', predictions=[{'text': 'x'}])
        with self.assertRaisesRegex(ValueError, 'failure needs'):
            validate_record(record, self.frame['frame_id'])

    def test_immutable_artifact_and_concurrent_run_lock(self):
        write_once(self.root / 'receipt.json', {'a': 1})
        with self.assertRaisesRegex(ValueError, 'immutable'):
            write_once(self.root / 'receipt.json', {'a': 2})
        with exclusive_run(self.root):
            with self.assertRaisesRegex(RuntimeError, 'locked'):
                with exclusive_run(self.root):
                    pass
        self.assertFalse((self.root / '.execution.lock').exists())

    def test_test_frame_cannot_be_used_for_preflight(self):
        job = dict(candidate={'candidate_id': 'testr'}, output_root=str(self.root),
                   run_binding={}, prepared={}, mode='preflight', inputs=[self.frame])
        with self.assertRaisesRegex(ValueError, 'train only'):
            execute_worker_job(job, lambda _: [], {})
        self.assertFalse((self.root / 'testr/preflight.json').exists())

    def test_test_inference_requires_identical_passed_gate(self):
        job = dict(candidate={'candidate_id': 'testr'}, output_root=str(self.root),
                   run_binding={}, prepared={}, mode='infer', inputs=[self.frame])
        with self.assertRaises(FileNotFoundError):
            execute_worker_job(job, lambda _: [], {})
        self.assertFalse((self.root / 'testr/records').exists())

    def test_successful_gate_infer_failure_retention_and_resume(self):
        from PIL import Image
        image = self.root / 'train.png'
        Image.new('RGB', (20, 20), 'white').save(image)
        train = dict(frame_id='Frames/train/1/1/a.png', path=str(image), image_sha256=sha(image))
        region = dict(polygon=[[1, 1], [10, 1], [10, 10], [1, 10]], text='word')
        job = dict(candidate={'candidate_id': 'testr'}, output_root=str(self.root),
                   run_binding={'data': 'fixed'}, prepared={'weights': 'fixed'}, mode='preflight', inputs=[train])
        runtime = {'weights_sha': 'fixed', 'device': 'cuda:0'}
        gate = execute_worker_job(job, lambda _: [region], runtime)
        self.assertEqual(gate['status'], 'passed')
        bad = self.root / 'bad.png'
        bad.write_bytes(image.read_bytes())
        frames = [dict(train, frame_id='Frames/test/1/1/a.png'),
                  dict(train, frame_id='Frames/test/1/1/b.png', path=str(bad))]
        calls = []
        def predictor(path):
            calls.append(path)
            if path.name == 'bad.png':
                raise RuntimeError('inference failure')
            return [region]
        job.update(mode='infer', inputs=frames, train_inputs=[train])
        complete = execute_worker_job(job, predictor, runtime)
        self.assertEqual(complete['failed_frames'], 1)
        self.assertEqual(len(calls), 3)
        resumed = execute_worker_job(job, predictor, runtime)
        self.assertEqual(resumed, complete)
        self.assertEqual(len(calls), 4)  # Only the train warm-up replays on resume.
        records = load_records(self.root, 'testr', complete['binding'], frames)
        self.assertEqual(records[frames[1]['frame_id']]['predictions'], [])
        with self.assertRaisesRegex(ValueError, 'runtime/config differs'):
            execute_worker_job(job, predictor, {'weights_sha': 'changed'})

    def test_empty_preflight_output_cannot_admit_candidate(self):
        from PIL import Image
        image = self.root / 'train.png'
        Image.new('RGB', (20, 20), 'white').save(image)
        row = dict(frame_id='Frames/train/1/1/a.png', path=str(image), image_sha256=sha(image))
        job = dict(candidate={'candidate_id': 'testr'}, output_root=str(self.root),
                   run_binding={}, prepared={}, mode='preflight', inputs=[row])
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            execute_worker_job(job, lambda _: [], {})
        self.assertFalse((self.root / 'testr/preflight.json').exists())

    def test_native_invalid_prediction_can_be_reported_without_quality_selection(self):
        from PIL import Image
        image = self.root / 'train.png'
        Image.new('RGB', (20, 20), 'white').save(image)
        row = dict(frame_id='Frames/train/1/1/a.png', path=str(image), image_sha256=sha(image))
        job = dict(candidate={'candidate_id': 'pgnet'}, preflight_geometry_policy=
                   'retain_and_report_native_invalid_predictions', output_root=str(self.root),
                   run_binding={}, prepared={}, mode='preflight', inputs=[row])
        valid = dict(polygon=[[1, 1], [10, 1], [10, 10], [1, 10]], text='word')
        invalid = dict(polygon=[[1, 1], [10, 10], [10, 1], [1, 10]], text='word')
        gate = execute_worker_job(job, lambda _: [valid, invalid], {})
        self.assertEqual(gate['train_observations'][0]['invalid_predictions'], 1)
        self.assertEqual(gate['train_observations'][0]['predictions'], [valid, invalid])


if __name__ == '__main__':
    unittest.main()
