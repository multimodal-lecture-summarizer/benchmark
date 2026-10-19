"""Scientific observation bindings fail closed when saved evidence changes."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT/'benchmark/experiments/scripts/build_mlpdataset_adjudication.py'
SPEC = importlib.util.spec_from_file_location('adjudication_builder', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REGISTRY = ROOT/'benchmark/experiments/registry/datasets'


class ObservationBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt_path = ROOT/'benchmark/experiments/outputs/mlpdataset_targeted_review_executed_261019/review-receipt.json'
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding='utf-8'))
        cls.manual = json.loads((REGISTRY/'mlpdataset-sampled-observations-v1.json').read_text(encoding='utf-8'))

    def verify(self, observation=None, results=None, sha=None, keys=None):
        results = results if results is not None else self.receipt['results']
        return MODULE.verify_observation(observation or self.manual['observations'][0],
            sha or hashlib.sha256(self.receipt_path.read_bytes()).hexdigest(),
            self.manual['receipt_sha256'], list(results) if keys is None else keys, results)

    def test_all33_observations_match_exact_receipt_source_and_frames(self):
        for observation in self.manual['observations']:
            self.assertEqual(self.verify(observation), observation['case_key'])

    def test_receipt_replaced_rejected(self):
        with self.assertRaisesRegex(ValueError, 'receipt SHA256'):
            self.verify(sha='0'*64)

    def test_receipt_order_drift_rejected_even_if_expected_hash_reused(self):
        with self.assertRaisesRegex(ValueError, 'order'):
            self.verify(keys=list(reversed(self.receipt['results'])))

    def test_source_and_annotation_drift_rejected(self):
        for field, value in [('source_sha256','0'*64), ('annotation_s',123.0)]:
            with self.subTest(field=field):
                results = copy.deepcopy(self.receipt['results'])
                results[self.manual['observations'][0]['case_key']]['binding']['case'][field]=value
                with self.assertRaisesRegex(ValueError, 'source, mark or frame'):
                    self.verify(results=results)

    def test_frame_pts_or_hash_drift_rejected(self):
        for field,value in [('source_pts_ticks',0), ('sha256','0'*64)]:
            with self.subTest(field=field):
                results = copy.deepcopy(self.receipt['results'])
                results[self.manual['observations'][0]['case_key']]['frames'][0][field]=value
                with self.assertRaisesRegex(ValueError, 'source, mark or frame'):
                    self.verify(results=results)

    def test_real_ledger_preserves82_and_all_event_identities(self):
        ledger=json.loads((REGISTRY/'mlpdataset-sampled-adjudication-v1.json').read_text())
        self.assertEqual(len(ledger['rows']),82)
        self.assertEqual(len({r['key'] for r in ledger['rows']}),82)
        self.assertEqual(len(ledger['events']),37)
        self.assertEqual(sum(e['primary_candidate'] for e in ledger['events']),33)
        self.assertTrue(all(r['disposition']=='hold' and r['native_endpoint_s'] is None for r in ledger['rows']))
        self.assertFalse(ledger['evaluation_ready'])
        self.assertEqual(ledger['summary']['repeated_mapping_proposals'],dict(
            shared_single_primary_event=11,multiple_events_unresolved=2,auxiliary_only_no_primary_event=1))
        for event in ledger['events']:
            old,different=event['sampled_onset_bracket_s']
            self.assertLess(old,different)
            self.assertLessEqual(different,event['sampled_stable_new_upper_s'])
            self.assertIsNone(event['native_endpoint_s'])

    def test_native_queue_bound_to_ledger_and_all_original_identities(self):
        queue=json.loads((REGISTRY/'mlpdataset-native-review-queue-v1.json').read_text())
        self.assertEqual(queue['review_ledger_sha256'],MODULE.digest(REGISTRY/'mlpdataset-sampled-adjudication-v1.json'))
        self.assertEqual(len(queue['jobs']),64)
        self.assertEqual(len(queue['original_queue']['cases']),82)
        original={f"{c['video_id']}:{c['annotation_index']}":c for c in queue['original_queue']['cases']}
        for job in queue['jobs']:
            self.assertLess(job['start_s'],job['end_s'])
            for key,binding in zip(job['original_keys'],job['source_bindings']):
                for field,value in binding.items():
                    self.assertEqual(original[key][field],value)
                self.assertEqual(original[key]['source_sha256'],job['source_sha256'])
