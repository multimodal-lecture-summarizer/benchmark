"""Notebook admission and full-evidence review must fail closed."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.scripts.spotting_colab_review import require_preflights, require_train_replays, verified_exports, csv_rows, status_rows
from experiments.scripts.spotting_colab_frame_review import review_record
from experiments.scripts.spotting_colab_state import digest, checkpoint_path


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self,name,value):
        path = self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding='utf-8')

    def gates(self):
        registry = {'candidates':[{'candidate_id':str(i),'conditional':False} for i in range(6)]}
        data = {'bundle_sha256':'bundle','train_preflight':[{'frame_id':'Frames/train/a.png','image_sha256':'pixels'}]}
        self.write('prepared-data.json',data)
        for c in registry['candidates']:
            prepared = {'candidate_id':c['candidate_id']}
            runtime = {'device':'Tesla T4'}
            gate = dict(status='passed',no_test_inference=True,runtime=runtime,train_observations=data['train_preflight'],
                        binding=dict(configuration_sha256=digest(c),runtime_sha256=digest(runtime),prepared_sha256=digest(prepared),
                                     run_binding=dict(data_sha256=digest(data),registry_sha256=digest(registry),bundle_sha256='bundle')))
            self.write(c['candidate_id']+'/prepared.json',prepared)
            self.write(c['candidate_id']+'/preflight.json',gate)
        return registry

    def test_all_six_gates_required_and_qualification_cannot_replace_one(self):
        registry = self.gates()
        self.assertTrue(require_preflights(self.root,registry))
        path = self.root/'5/preflight.json'
        gate = json.loads(path.read_text())
        gate['binding']['run_binding'] = {'purpose':'standalone_qualification'}
        self.write('5/preflight.json',gate)
        with self.assertRaisesRegex(ValueError,'another run/cohort'):
            require_preflights(self.root,registry)
        path.unlink()
        with self.assertRaisesRegex(ValueError,'missing required'):
            require_preflights(self.root,registry)

    def test_altered_config_or_runtime_gate_rejected(self):
        registry = self.gates()
        registry['candidates'][0]['threshold'] = 'changed'
        with self.assertRaisesRegex(ValueError,'candidate changed'):
            require_preflights(self.root,registry)
        registry = self.gates()
        gate = json.loads((self.root/'0/preflight.json').read_text())
        gate['runtime']['device'] = 'changed'
        self.write('0/preflight.json',gate)
        with self.assertRaisesRegex(ValueError,'runtime changed'):
            require_preflights(self.root,registry)

    def test_status_does_not_treat_failed_receipt_as_passed(self):
        registry = self.gates()
        self.write('0/preflight.json',{'status':'failed'})
        self.assertEqual(status_rows(self.root,registry)[0]['preflight'],'failed')

    def test_all_replays_must_pass_and_bind_to_current_gates(self):
        registry = self.gates()
        with self.assertRaisesRegex(ValueError, 'missing required train replay'):
            require_train_replays(self.root, registry)
        for c in registry['candidates']:
            gate = json.loads((self.root/c['candidate_id']/'preflight.json').read_text())
            self.write(c['candidate_id']+'/train-replay.json', dict(status='passed', no_test_inference=True,
                       binding=gate['binding'], runtime=gate['runtime'], train_frames=1))
        self.assertTrue(require_train_replays(self.root, registry))
        replay = json.loads((self.root/'0/train-replay.json').read_text())
        replay['runtime']['device'] = 'changed'
        self.write('0/train-replay.json', replay)
        with self.assertRaisesRegex(ValueError, 'train replay identity changed'):
            require_train_replays(self.root, registry)

    def test_export_hash_and_compressed_full_text(self):
        data = 'candidate_id,frame_id,text\na,Frames/test/x.png,"full, text"\n'.encode()
        path = self.root/'full.csv.gz'
        path.write_bytes(gzip.compress(data))
        self.write('analysis-summary.json',{'artifacts':{'full':{'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}})
        verified_exports(self.root)
        self.assertEqual(csv_rows(path)[0]['text'],'full, text')
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'altered'):
            verified_exports(self.root)

    def test_viewer_rejects_altered_checkpoint_and_preserves_failure(self):
        frame = {'frame_id':'Frames/test/1/1/a.png','image_sha256':'image'}
        record = dict(frame_id=frame['frame_id'],status='error',error='OOM',predictions=[])
        binding = {'model':'frozen'}
        target = checkpoint_path(self.root,'candidate',frame['frame_id']).relative_to(self.root)
        self.write(target,dict(binding=binding,image_sha256='image',record_sha256=digest(record),record=record))
        self.assertEqual(review_record(self.root,'candidate',frame,{'binding':binding}),record)
        record['error']='altered'
        self.write(target,dict(binding=binding,image_sha256='image',record_sha256='old',record=record))
        with self.assertRaisesRegex(ValueError,'altered'):
            review_record(self.root,'candidate',frame,{'binding':binding})


if __name__=='__main__':
    unittest.main()
