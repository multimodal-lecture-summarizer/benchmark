"""Real native-cadence tests; synthetic media is never research evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import contextlib
import io
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'experiments/scripts'
sys.path.insert(0, str(SCRIPTS))
from mlpdataset_native_review import NativeReviewRunner, run_native_queue, render_native_job


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/"tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root/'cache'
        self.source = self.base/'videos/abc/source.mp4'
        self.source.parent.mkdir(parents=True)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'color=c=red:s=160x90:r=20:d=1', '-f', 'lavfi', '-i', 'color=c=blue:s=160x90:r=20:d=1',
            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0,setpts=PTS+7/TB[v]', '-map', '[v]',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', str(self.source)],
            check=True, capture_output=True, timeout=30)
        self.job = dict(job_id='cut', video_id='abc', source_relative_path='videos/abc/source.mp4',
            source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(), duration_s=2.,
            start_s=.8, end_s=1.2, original_keys=['abc:0'], source_bindings=[dict(annotation_index=0, annotation_s=1., annotation_sha256='a'*64)], evidence=[])
        self.queue = dict(queue_id='test', protocol_sha256='p', review_ledger_sha256='l',
            original_queue_sha256='q', original_queue=dict(cases=[dict(video_id='abc', annotation_index=i) for i in range(82)]), jobs=[self.job, dict(self.job, job_id='second', start_s=1.2, end_s=1.4)])
        self.runner = NativeReviewRunner(self.base, self.root/'review', self.queue, width=160, min_free_bytes=0)

    def test_nonzero_origin_known_cut_identical_frames_and_cache(self):
        result = self.runner.run_job(self.job)
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['timing']['origin_s'], 7)
        self.assertEqual(len(result['frames']), 8)
        self.assertEqual([f['native_frame_index'] for f in result['frames']], list(range(8)))
        self.assertEqual([round(f['source_elapsed_s'], 2) for f in result['frames']], [.8,.85,.9,.95,1.,1.05,1.1,1.15])
        # Consecutive identical PNGs remain present; there is no content-based deduplication.
        self.assertEqual(result['frames'][0]['sha256'], result['frames'][1]['sha256'])
        self.assertNotEqual(result['frames'][0]['sha256'], result['frames'][-1]['sha256'])
        launches = self.runner.stats()['process_launches']
        self.assertEqual(self.runner.run_job(self.job), result)
        self.assertEqual(self.runner.stats()['process_launches'], launches)
        self.assertEqual(self.runner.stats()['source_hashes'], 1)
        block, stats = render_native_job(self.job, result, self.runner.root, 1)
        self.assertEqual(stats['omitted_inline_frames'], 8)
        self.assertEqual(block.count('retained PNG'), 8)
        bad = dict(result, frames=[dict(result['frames'][0], relative_path='../escape.png')])
        with self.assertRaises(ValueError):
            render_native_job(self.job, bad, self.runner.root, 100000)
        bad = dict(result, frames=[dict(result['frames'][0], sha256='0'*64)])
        with self.assertRaises(ValueError):
            render_native_job(self.job, bad, self.runner.root, 100000)
        bad = dict(result, log=dict(result['log'], sha256='0'*64))
        with self.assertRaises(ValueError):
            render_native_job(self.job, bad, self.runner.root, 100000)
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        self.assertEqual(self.runner.run_job(self.job)['status'], 'source_changed')

    def test_vfr_all_pts(self):
        # Retain alternating temporal gaps (50/100ms), then shift origin by7s.
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i',
            'testsrc2=s=160x90:r=20:d=2','-vf',"select='not(eq(mod(n,3),1))',setpts=PTS+7/TB",
            '-c:v','libx264','-fps_mode','passthrough',str(self.source)], check=True,capture_output=True,timeout=30)
        self.job['source_sha256'] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.runner.run_job(self.job)
        self.assertEqual(result['status'], 'ready', result)
        elapsed = [round(f['source_elapsed_s'], 2) for f in result['frames']]
        self.assertEqual(elapsed, [.85,.9,1.,1.05,1.15])

    def test_bounds_quota_deadline_and_all82_interrupt_receipt(self):
        for start, end in [(-1,1),(1,1),(0,3),(float('nan'),1)]:
            self.assertEqual(self.runner.run_job(dict(self.job,start_s=start,end_s=end))['status'], 'failed')
        self.runner.max_bytes=1
        self.assertEqual(self.runner.run_job(self.job)['status'],'quota')
        self.assertFalse(list(self.runner.root.rglob('scratch-*')))
        self.runner.max_bytes=1024**3
        self.runner.deadline=time.monotonic()-1
        self.assertEqual(self.runner.run_job(self.job)['status'],'deadline')
        self.runner.deadline=time.monotonic()+60
        def interrupt(command, log, stage):
            (stage/'partial.png').write_bytes(b'x')
            raise KeyboardInterrupt()
        with patch.object(self.runner, 'run_process', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                run_native_queue(self.runner, progress=lambda x:None)
        receipt=json.loads((self.runner.root/'native-review-receipt.json').read_text())
        self.assertEqual(len(receipt['original_row_statuses']),82)
        self.assertEqual([r['status'] for r in receipt['job_statuses']],['interrupted','not_attempted'])
        self.assertFalse(list(self.runner.root.rglob('scratch-*')))
        self.assertFalse(list(self.runner.root.rglob('partial.png')))

    def test_standalone_notebook_executes_synthetic_bindings(self):
        from build_mlpdataset_native_review import build
        import os
        rows = self.queue['original_queue']['cases']
        for row in rows:
            row.update(annotation_s=1., annotation_sha256='a'*64,
                       source_sha256=self.job['source_sha256'],
                       source_relative_path=self.job['source_relative_path'])
        original = self.queue['original_queue']
        original.update(required_drive_exports=[], inventory=dict(videos=1, marks=82))
        analysis = self.base/'analysis'
        analysis.mkdir()
        (analysis/'video-ledger.csv').write_text('video_id,annotation_sha256\nabc,'+'a'*64+'\n')
        (analysis/'boundary-ledger.csv').write_text('video_id,index,time_s\n'+''.join(f'abc,{i},1.0\n' for i in range(82)))
        (self.source.parent/'state.json').write_text(json.dumps(dict(status='downloaded',identity=dict(video_id='abc'),sha256=self.job['source_sha256'],file_name='source.mp4')))
        protocol = self.root/'protocol.json'
        protocol.write_text(json.dumps(dict(protocol_id='test',evaluation_ready=False)))
        self.queue.update(drive_run_name='cache', protocol_id='test', protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest())
        queue_path = self.root/'queue.json'
        queue_path.write_text(json.dumps(self.queue))
        notebook = build(queue_path, protocol, self.root/'native.ipynb')
        namespace = {}
        before = Path.cwd()
        try:
            os.chdir(self.root)
            with contextlib.redirect_stdout(io.StringIO()):
                for cell in notebook.cells:
                    if cell.cell_type != 'code':
                        continue
                    source = cell.source
                    if 'USE_GOOGLE_DRIVE = True' in source:
                        source = source.replace('USE_GOOGLE_DRIVE = True', 'USE_GOOGLE_DRIVE = False').replace('FREE_FLOOR_GIB = 1.0','FREE_FLOOR_GIB = 0.000001').replace('STAGE_GIB = 2.0','STAGE_GIB = 0.0')
                    exec(compile(source, '<native-notebook-cell>', 'exec'), namespace)
        finally:
            os.chdir(before)
        receipt = namespace['receipt']
        self.assertEqual([r['status'] for r in receipt['job_statuses']], ['ready','ready'])
        self.assertEqual(len(receipt['original_row_statuses']), 82)
        self.assertEqual(len(namespace['template']),82)
        self.assertTrue(all(r['native_point'] is None for r in namespace['template']))
        self.assertEqual(namespace['runner'].stats()['source_hashes'], 1)
        namespace['receipt']['results']['cut'] = dict(status='ready', frames=None)
        gallery = next(c.source for c in notebook.cells if c.cell_type=='code' and c.source.startswith('display_state ='))
        with contextlib.redirect_stdout(io.StringIO()):
            exec(gallery, namespace)
        self.assertEqual(namespace['display_state']['status'], 'partial_display_errors')
        self.assertEqual(len(namespace['display_state']['jobs']), 2)
        self.assertEqual(namespace['display_state']['jobs'][0]['status'], 'display_error')
        self.assertEqual(namespace['display_state']['jobs'][1]['status'], 'complete')

    def test_actual_queue_generated_bundle_and_all_job_receipt(self):
        import base64
        import nbformat
        benchmark = Path(__file__).resolve().parents[1]
        queue_path = benchmark/'experiments/registry/datasets/mlpdataset-native-review-queue-v1.json'
        queue = json.loads(queue_path.read_text(encoding='utf8'))
        runner = NativeReviewRunner(self.base, self.root/'actual-review', queue, min_free_bytes=0)
        for job in queue['jobs']:
            self.assertEqual(runner.binding(job)['job'], job)
        runner.deadline = time.monotonic()-1
        receipt = run_native_queue(runner, progress=lambda text:None)
        self.assertEqual(len(receipt['original_row_statuses']),82)
        self.assertEqual(len(receipt['job_statuses']), len(queue['jobs']))
        self.assertEqual(receipt['job_statuses'][0]['status'], 'deadline')
        self.assertTrue(all(r['status']=='not_attempted' for r in receipt['job_statuses'][1:]))
        notebook = nbformat.read(benchmark/'experiments/notebooks/diagnostics/mlpdataset-native-review-colab.ipynb', as_version=4)
        namespace = dict(base64=base64, hashlib=hashlib, json=json, RUN_NAME=queue['drive_run_name'])
        with contextlib.redirect_stdout(io.StringIO()):
            exec(notebook.cells[2].source, namespace)
            for cell in notebook.cells[4:9]:
                exec(cell.source, namespace)
        self.assertEqual(namespace['QUEUE'], queue)
        for name, expected in namespace['BUNDLE']['helper_sha256'].items():
            self.assertEqual(hashlib.sha256((SCRIPTS/name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
