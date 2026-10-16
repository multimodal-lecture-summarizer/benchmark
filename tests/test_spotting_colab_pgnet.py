"""Joint candidate selection must preserve anchors and never invent confidence."""
import ast
import json
from pathlib import Path
import unittest

from experiments.scripts.spotting_colab_candidates import load_registry
from experiments.scripts.spotting_colab_pgnet import pgnet_regions
from experiments.scripts.spotting_colab_artifacts import digest

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / 'experiments/registry/datasets/iiit-cvid-spotting-colab-t4-candidates-261015-v2.json'


class JointCandidateTests(unittest.TestCase):
    def test_required_joint_replacement_retains_five_exact_anchors(self):
        old, new = load_registry(), load_registry(NEW)
        self.assertEqual(new['candidates'][:5], old['candidates'][:5])
        self.assertEqual(len(new['candidates']), 6)
        self.assertTrue(all(c['locked'] and not c['conditional'] for c in new['candidates']))
        pg = new['candidates'][-1]
        self.assertEqual(pg['adapter'], 'pgnet')
        self.assertEqual(pg['configuration']['e2e_pgnet_valid_set'], 'totaltext')
        self.assertEqual(pg['configuration']['e2e_pgnet_score_thresh'], .5)
        self.assertEqual(digest(pg['configuration']), pg['configuration_sha256'])
        self.assertEqual(len(pg['model_sha256']), 3)
        self.assertIn('TESTR', new['excluded_candidates'][0]['reason'] if 'TESTR' in new['excluded_candidates'][0]['reason']
                      else new['excluded_candidates'][0]['candidate_id'].upper())

    def test_native_output_empty_text_and_no_synthetic_confidence(self):
        points = [[[1, 2], [5, 2], [5, 8], [1, 8]]]
        rows = pgnet_regions(points, [''])
        self.assertEqual(rows[0]['text'], '')
        self.assertEqual(set(rows[0]), {'polygon', 'text'})
        self.assertEqual(rows[0]['polygon'][0], [1., 2.])
        self.assertEqual(pgnet_regions([], []), [])

    def test_malformed_joint_outputs_fail_without_partial_predictions(self):
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            pgnet_regions([[]], [])
        with self.assertRaisesRegex(ValueError, 'string'):
            pgnet_regions([[]], [None])

    def test_v2_notebook_has_explicit_registry_and_distinct_run(self):
        path = ROOT / 'experiments/notebooks/iiit-cvid-spotting-colab-t4-v2.ipynb'
        if not path.exists():
            self.skipTest('generate v2 notebook before notebook contract test')
        notebook = json.loads(path.read_text(encoding='utf-8'))
        source = ''.join(''.join(c['source']) for c in notebook['cells'])
        self.assertIn('--candidate-registry', source)
        self.assertIn('cvid-spotting-t4-261015-v2', source)
        self.assertIn('TESTR is excluded', source)
        self.assertIn('six-pipeline comparison', source)
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                ast.parse(''.join(cell['source']))
                self.assertIsNone(cell['execution_count'])
                self.assertEqual(cell['outputs'], [])


if __name__ == '__main__':
    unittest.main()
