"""Execute the shipped notebook locally with synthetic media, never research GT.

Only runtime parameters/input bindings change. Helpers, extraction, presentation,
and receipt code execute directly from the generated standalone notebook.
"""
import ast
import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import nbformat
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT/'benchmark/experiments/notebooks/diagnostics/mlpdataset-targeted-review-colab.ipynb'
REGISTRY = ROOT/'benchmark/experiments/registry/datasets'
EDA_SHA = '5a1b0622cd046c42df3e12b8347fb07864056f6bbe0301be6b9824f4c55c9c64'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NotebookCellTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = nbformat.read(NOTEBOOK, as_version=4)
        cls.sources = [c.source for c in cls.notebook.cells if c.cell_type == 'code']

    @classmethod
    def cell(cls, marker):
        matches = [source for source in cls.sources if marker in source]
        if len(matches) != 1:
            raise AssertionError(f'Expected one notebook cell matching {marker!r}; got {len(matches)}')
        return matches[0]


class NotebookContractTests(NotebookCellTestCase):
    def test_schema_ast_unexecuted_and_frozen_protocol(self):
        nbformat.validate(self.notebook)
        self.assertEqual(len(self.notebook.cells), 18)
        for cell in self.notebook.cells:
            if cell.cell_type == 'code':
                ast.parse(cell.source)
                self.assertIsNone(cell.execution_count)
                self.assertEqual(cell.outputs, [])
        namespace = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec('import base64, hashlib, json\n'+self.cell('BUNDLE_BYTES ='), namespace)
        bundle = namespace['BUNDLE']
        queue = bundle['queue']
        self.assertEqual(queue['summary'], dict(selected_marks=82, videos=42, groups=10,
                                               historical_verified_clips=14, new_dense_contexts=48,
                                               policy_only_edges=20))
        self.assertEqual(len(queue['cases']), 82)
        self.assertEqual(len({c['video_id'] for c in queue['cases']}), 42)
        self.assertEqual(sum(c['requires_new_dense_context'] for c in queue['cases']), 48)
        self.assertEqual(queue['input_notebook_sha256'], EDA_SHA)
        self.assertEqual(sha(ROOT/'benchmark/experiments/notebooks/diagnostics/mlpdataset_slide_transition_eda_colab.ipynb'), EDA_SHA)
        self.assertEqual(bundle['queue_sha256'], sha(REGISTRY/'mlpdataset-targeted-review-queue-v1.json'))
        self.assertEqual(bundle['protocol_sha256'], sha(REGISTRY/'mlpdataset-slide-transition-protocol-v1.json'))
        self.assertEqual(bundle['protocol']['status'], 'rules_frozen')
        self.assertFalse(bundle['protocol']['evaluation_ready'])
        historical = [c for c in queue['cases'] if c.get('historical_evidence')]
        self.assertEqual(len(historical), 14)
        self.assertEqual(len(bundle['historical_media']), 14)
        for case in historical:
            evidence = case['historical_evidence']
            key = case['video_id']+':'+str(case['annotation_index'])
            data = base64.b64decode(bundle['historical_media'][key], validate=True)
            self.assertEqual(hashlib.sha256(data).hexdigest(), evidence['clip_sha256'])
            self.assertEqual(data, (ROOT/evidence['clip_local_path']).read_bytes())
            self.assertEqual(evidence['source_sha256'], case['source_sha256'])
            self.assertEqual(evidence['annotation_s'], case['annotation_s'])
            self.assertEqual(evidence['gt_disposition'], 'hold')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class NotebookExecutionTests(NotebookCellTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (ROOT/'tmp').mkdir(exist_ok=True)
        cls.work = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        cls.fixture = Path(cls.work.name)/'synthetic-test-media-not-research.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=red:s=160x90:r=20:d=1', '-f', 'lavfi', '-i',
                        'color=c=blue:s=160x90:r=20:d=1', '-filter_complex',
                        '[0:v][1:v]concat=n=2:v=1:a=0,setpts=PTS+7/TB[v]', '-map', '[v]',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough',
                        str(cls.fixture)], check=True, capture_output=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root/'synthetic-test-media-not-research'
        source = self.base/'videos/fixture/source.mp4'
        source.parent.mkdir(parents=True)
        shutil.copyfile(self.fixture, source)
        (source.parent/'state.json').write_text(json.dumps(dict(
            status='downloaded', identity=dict(video_id='fixture'), sha256=sha(source),
            file_name='source.mp4')), encoding='utf8')
        annotation_sha = hashlib.sha256(b'fixture labels, not research annotations').hexdigest()
        common = dict(video_id='fixture', duration_s=2., source_sha256=sha(source),
                      source_relative_path='videos/fixture/source.mp4', annotation_sha256=annotation_sha,
                      group='fixture-test-only', reasons=['synthetic test media'],
                      review_action='new_context', requires_new_dense_context=True)
        self.cases = [dict(common, annotation_index=i, annotation_s=.5+i*.25) for i in range(4)]
        self.cases[2].update(requires_new_dense_context=False, review_action='historical')
        self.cases[2]['historical_evidence'] = dict(clip_sha256=sha(source),
            event_observation='synthetic test context', measured_window=dict(start=0, end=2),
            timing_status='fixture_only_not_research')
        self.cases[3].update(requires_new_dense_context=False, review_action='policy_hold')
        analysis = self.base/'analysis'
        analysis.mkdir()
        pd.DataFrame([dict(video_id='fixture', annotation_sha256=annotation_sha)]).to_csv(
            analysis/'video-ledger.csv', index=False)
        pd.DataFrame([dict(video_id=c['video_id'], index=c['annotation_index'], time_s=c['annotation_s'])
                      for c in self.cases]).to_csv(analysis/'boundary-ledger.csv', index=False)
        for name in ('full-release-mark-coverage.csv', 'full-release-video-coverage.csv'):
            (analysis/name).write_text('fixture_only\ntrue\n', encoding='utf8')
        self.queue = dict(queue_id='fixture-test-only', inventory=dict(videos=1, marks=4),
                          cases=self.cases, input_notebook_sha256=EDA_SHA,
                          summary=dict(selected_marks=4), required_drive_exports=[
                              dict(relative_path='analysis/'+p.name, sha256=sha(p))
                              for p in sorted(analysis.iterdir())])
        self.output = io.StringIO()
        self.ns = {'__name__': '__notebook_fixture__'}
        config = self.cell('RUN_NAME =').replace('USE_GOOGLE_DRIVE = True', 'USE_GOOGLE_DRIVE = False')
        config = config.replace('BASE = Path.cwd()/RUN_NAME', 'BASE = Path('+repr(str(self.base))+')')
        self.execute(config)
        self.ns.update(display=lambda *args, **kwargs: None, QUEUE=self.queue,
            PROTOCOL=dict(protocol_id='fixture-test-only', status='rules_frozen', gt_status='pending',
                          evaluation_ready=False), EXTRACT_NEW_CONTEXTS=True, SOURCE_STAGE_GB=0,
            MIN_FREE_GB=0, BUNDLE=dict(queue_sha256='fixture', protocol_sha256='fixture',
                historical_media={'fixture:2': base64.b64encode(source.read_bytes()).decode('ascii')}))
        for marker in ('def targeted_timing(', 'class PreviewSourceStager:', 'class ReviewRunner:',
                       'def validate_review_inputs('):
            self.execute(self.cell(marker))
        self.inputs_before = {p: sha(p) for p in self.base.rglob('*') if p.is_file()}

    def execute(self, source):
        with contextlib.redirect_stdout(self.output):
            exec(compile(source, str(NOTEBOOK), 'exec'), self.ns)

    def prepare(self):
        self.execute(self.cell('validated_inputs ='))
        self.execute(self.cell('historical_rows = []'))

    def extract(self):
        self.execute(self.cell('selected_cases ='))

    def receipt(self):
        return json.loads((self.ns['REVIEW_ROOT']/'review-receipt.json').read_text(encoding='utf8'))

    def test_actual_cells_extract_only_missing_contexts_and_resume_without_ffmpeg(self):
        self.prepare()
        self.assertEqual(len(self.ns['queue_table']), 4)
        self.assertEqual(len(self.ns['historical_rows']), 1)
        self.extract()
        self.assertEqual(len(self.ns['status_rows']), 4)
        self.assertEqual(self.receipt()['all_case_statuses'], self.ns['status_rows'])
        self.assertEqual([r['selected_for_extraction'] for r in self.ns['status_rows']],
                         [True, True, False, False])
        self.assertEqual(set(self.ns['results']), {'fixture:0', 'fixture:1'})
        self.assertTrue(all(v['status'] == 'ready' for v in self.ns['results'].values()))
        self.assertEqual(self.receipt()['display']['status'], 'pending_after_receipt')
        self.assertEqual(self.receipt()['runner']['source_hashes'], 1)
        for result in self.ns['results'].values():
            self.assertEqual(result['timing']['origin_s'], 7.)
            self.assertGreater(len(result['frames']), 6)
        self.execute(self.cell('display_summary ='))
        self.execute(self.cell('template=[]'))
        self.assertEqual(self.receipt()['display']['display_failures'], 0)
        self.assertEqual(self.receipt()['display']['cases'], 2)
        self.assertFalse(self.receipt()['evaluation_ready'])
        self.assertEqual(self.receipt()['semantic_certified_events'], 0)
        decisions = pd.read_csv(self.ns['REVIEW_ROOT']/'review-decisions-template.csv')
        self.assertEqual(len(decisions), 4)
        self.assertEqual(set(decisions.disposition), {'hold'})
        self.extract()
        self.assertEqual(self.receipt()['runner']['process_launches'], 0)
        self.assertEqual(self.receipt()['runner']['cache_hits'], 2)
        self.assertEqual({p: sha(p) for p in self.inputs_before}, self.inputs_before)

    def test_gallery_exception_preserves_receipt_and_counts_failures(self):
        self.prepare()
        self.extract()
        before = self.receipt()['results']
        def fail_display(*args, **kwargs):
            self.assertEqual(self.receipt()['display']['status'], 'pending_after_receipt')
            raise RuntimeError('synthetic frontend display exception')
        self.ns['display'] = fail_display
        self.execute(self.cell('display_summary ='))
        receipt = self.receipt()
        self.assertEqual(receipt['results'], before)
        self.assertEqual(receipt['display']['display_failures'], 2)
        self.assertEqual(receipt['display']['cases'], 0)
        self.assertIn('synthetic frontend display exception', self.output.getvalue())

    def test_interrupt_stops_loop_preserves_completed_checkpoint_and_receipt(self):
        self.prepare()
        runner_class = self.ns['ReviewRunner']
        original = runner_class.run_case
        def interrupt_second(runner, case):
            if case['annotation_index'] == 1:
                raise KeyboardInterrupt('synthetic user stop')
            return original(runner, case)
        with patch.object(runner_class, 'run_case', interrupt_second):
            with self.assertRaises(KeyboardInterrupt):
                self.extract()
        receipt = self.receipt()
        self.assertEqual(set(receipt['results']), {'fixture:0'})
        self.assertEqual(len(receipt['all_case_statuses']), 4)
        self.assertEqual([r['extraction_status'] for r in receipt['all_case_statuses']],
                         ['ready', 'not_attempted', 'historical', 'policy_hold'])
        self.assertTrue(self.ns['stager'].closed)
        result = receipt['results']['fixture:0']
        self.assertEqual(result['status'], 'ready')
        self.assertTrue((self.ns['REVIEW_ROOT']/result['case_key']/'checkpoint.json').is_file())
        self.extract()
        self.assertEqual(self.receipt()['runner']['cache_hits'], 1)
        self.assertEqual(len(self.receipt()['results']), 2)

    def test_deadline_receipt_keeps_every_status_without_process_launch(self):
        self.prepare()
        runner_class = self.ns['ReviewRunner']
        original = runner_class.__init__
        def already_expired(runner, *args, **kwargs):
            original(runner, *args, **kwargs)
            runner.deadline = 0
        with patch.object(runner_class, '__init__', already_expired):
            self.extract()
        receipt = self.receipt()
        self.assertEqual(receipt['runner']['process_launches'], 0)
        self.assertEqual([r['extraction_status'] for r in receipt['all_case_statuses']],
                         ['deadline', 'not_attempted', 'historical', 'policy_hold'])

    def test_full_embedded_queue_retains_all_82_statuses_when_extraction_disabled(self):
        # Exercise production queue accounting without touching unavailable sources.
        self.prepare()
        self.execute(self.cell('BUNDLE_BYTES ='))
        self.ns['case_by_key'] = {c['video_id']+':'+str(c['annotation_index']): c
                                 for c in self.ns['QUEUE']['cases']}
        self.ns.update(EXTRACT_NEW_CONTEXTS=False, historical_rows=[])
        self.extract()
        receipt = self.receipt()
        self.assertEqual(len(receipt['all_case_statuses']), 82)
        self.assertEqual(len({r['key'] for r in receipt['all_case_statuses']}), 82)
        self.assertEqual(receipt['selected_for_extraction'], 0)
        self.assertEqual(receipt['runner']['process_launches'], 0)
        self.assertTrue(all(r['gt_disposition'] == 'hold' for r in receipt['all_case_statuses']))

    def test_setup_rejects_changed_export_annotation_state_hash_and_source_path(self):
        validate = self.ns['validate_review_inputs']
        path = self.base/'analysis/boundary-ledger.csv'
        saved = path.read_bytes()
        path.write_bytes(saved+b'changed')
        with self.assertRaisesRegex(ValueError, 'Input artifact mismatch'):
            validate(self.base, self.queue)
        path.write_bytes(saved)
        for field, value, error in (
                ('annotation_sha256', '0'*64, 'Annotation source hash'),
                ('source_sha256', '0'*64, 'Media checkpoint'),
                ('source_relative_path', 'videos/fixture/wrong.mp4', 'Source path/binding'),
                ('annotation_s', 99, 'Released mark identity')):
            queue = copy.deepcopy(self.queue)
            queue['cases'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                validate(self.base, queue)
        self.assertFalse(self.ns['REVIEW_ROOT'].exists())

    def test_actual_source_bytes_mismatch_rejected_at_extraction(self):
        self.prepare()
        source = self.base/'videos/fixture/source.mp4'
        source.write_bytes(source.read_bytes()+b'changed source bytes')
        self.extract()
        self.assertEqual({v['status'] for v in self.ns['results'].values()}, {'source_mismatch'})
        self.assertEqual(self.receipt()['runner']['process_launches'], 0)
        self.assertFalse(self.receipt()['evaluation_ready'])


if __name__ == '__main__':
    unittest.main()
