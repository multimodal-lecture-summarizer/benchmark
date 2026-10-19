"""Real FFmpeg fixture tests; generated colors are test media, never research evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'experiments'/'scripts'
sys.path.insert(0, str(SCRIPTS))
from mlpdataset_targeted_review import ReviewRunner, ReviewLimitError
from mlpdataset_targeted_media import targeted_timing


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class TargetedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'tmp')
        cls.fixture = Path(cls.work.name)/'known-cut.mp4'
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                   'color=c=red:s=160x90:r=20:d=1', '-f', 'lavfi', '-i',
                   'color=c=blue:s=160x90:r=20:d=1', '-filter_complex',
                   '[0:v][1:v]concat=n=2:v=1:a=0,setpts=PTS+7/TB[v]', '-map', '[v]',
                   '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough',
                   str(cls.fixture)]
        subprocess.run(command, check=True, capture_output=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root/'cache'
        self.source = self.base/'videos'/'abc'/'known-cut.mp4'
        self.source.parent.mkdir(parents=True)
        shutil.copyfile(self.fixture, self.source)
        self.case = dict(video_id='abc', annotation_index=2, annotation_s=1., duration_s=2.,
                         source_relative_path='videos/abc/known-cut.mp4',
                         source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.runner = ReviewRunner(self.base, self.root/'review', min_free_bytes=0, width=160)

    def test_real_cut_nonzero_origin_eof_and_cache(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['timing']['origin_s'], 7.)
        self.assertTrue(result['window']['truncated_start'])
        self.assertTrue(result['window']['truncated_end'])
        self.assertGreaterEqual(len(result['frames']), 7)
        self.assertEqual(result['frames'][0]['source_elapsed_s'], 0.)
        self.assertGreater(result['frames'][-1]['source_elapsed_s'], 1.5)
        # Inspect actual decoded pixels around the known cut, using FFmpeg rawvideo.
        pixels = []
        for frame in (result['frames'][0], result['frames'][-1]):
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i',
                                  str(self.runner.root/frame['relative_path']), '-f', 'rawvideo',
                                  '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True).stdout
            pixels.append(tuple(raw[:3]))
        self.assertGreater(pixels[0][0], 200)
        self.assertGreater(pixels[1][2], 200)
        launches = self.runner.stats()['process_launches']
        self.assertEqual(self.runner.run_case(self.case), result)
        self.assertEqual(self.runner.stats()['source_hashes'], 1)
        self.assertEqual(self.runner.stats()['process_launches'], launches)
        json.dumps(result, allow_nan=False)

    def test_no_overlap_and_negative_center(self):
        for mark in (-20, 20):
            case = dict(self.case, annotation_s=mark)
            self.assertEqual(self.runner.run_case(case)['status'], 'outside_video')
        result = self.runner.run_case(dict(self.case, annotation_s=-1))
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['window']['effective_start_s'], 0.)

    def test_corrupt_checkpoint_or_artifact_cannot_resume(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        folder = self.runner.root/result['case_key']
        checkpoint = folder/'checkpoint.json'
        checkpoint.write_text('{broken', encoding='utf-8')
        self.assertEqual(self.runner.run_case(self.case)['status'], 'ready')
        current = json.loads(checkpoint.read_text())
        (self.runner.root/current['frames'][0]['relative_path']).write_bytes(b'broken')
        launches = self.runner.stats()['process_launches']
        self.assertEqual(self.runner.run_case(self.case)['status'], 'ready')
        self.assertGreater(self.runner.stats()['process_launches'], launches)
        current = json.loads(checkpoint.read_text())
        current['frames'][0]['source_elapsed_s'] = 999
        checkpoint.write_text(json.dumps(current), encoding='utf-8')
        launches = self.runner.stats()['process_launches']
        self.assertEqual(self.runner.run_case(self.case)['status'], 'ready')
        self.assertGreater(self.runner.stats()['process_launches'], launches)

    def test_deadline_before_launch_and_after_staging(self):
        self.runner.deadline = time.monotonic()-1
        self.assertEqual(self.runner.run_case(self.case)['status'], 'deadline')
        self.assertEqual(self.runner.stats()['process_launches'], 0)
        def expire(source, sha, deadline):
            self.runner.deadline = time.monotonic()-1
            return source
        self.runner.deadline = time.monotonic()+60
        self.runner.stage_getter = expire
        self.assertEqual(self.runner.run_case(self.case)['status'], 'deadline')
        self.assertEqual(self.runner.stats()['process_launches'], 0)

    def test_changed_source_rejected_even_with_cached_case(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        launches = self.runner.stats()['process_launches']
        self.assertEqual(self.runner.run_case(self.case)['status'], 'source_changed')
        self.assertEqual(self.runner.stats()['process_launches'], launches)
        self.assertEqual(self.runner.stats()['source_hashes'], 1)

    def test_interrupt_cleanup_and_retry(self):
        original = self.runner.run_process
        def interrupt(command, log, stage):
            (stage/'partial.png').write_bytes(b'partial')
            raise KeyboardInterrupt()
        with patch.object(self.runner, 'run_process', side_effect=interrupt):
            result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(result['frames'], [])
        self.assertFalse(list(self.runner.root.rglob('scratch-*')))
        self.assertFalse(list(self.runner.root.rglob('partial.png')))
        self.assertEqual(self.runner.run_case(self.case)['status'], 'ready')

    def test_quota_and_source_containment(self):
        self.runner.max_bytes = 1
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'quota', result)
        self.assertFalse(list(self.runner.root.rglob('scratch-*')))
        for path in ('../known-cut.mp4', str(self.source), 'videos/other/known-cut.mp4'):
            self.assertEqual(self.runner.run_case(dict(self.case, source_relative_path=path))['status'], 'failed')
        with self.assertRaises(ValueError):
            ReviewRunner(self.base, self.base/'review')

    def test_source_mismatch_and_nonzero_unknown_duration(self):
        self.assertEqual(self.runner.run_case(dict(self.case, source_sha256='0'*64))['status'], 'source_mismatch')
        with self.assertRaises(ValueError):
            targeted_timing(dict(streams=[dict(start_pts=70, time_base='1/10')],
                                 format=dict(start_time='7')), 2)

    def test_nonzero_video_origin_different_container_origin(self):
        fixture = self.source.with_name('with-audio.mp4')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(self.source),
                        '-f', 'lavfi', '-i', 'anullsrc=r=8000:cl=mono', '-copyts',
                        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
                        '-t', '9', str(fixture)], check=True, capture_output=True, timeout=30)
        case = dict(self.case, source_relative_path='videos/abc/with-audio.mp4',
                    source_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest())
        result = self.runner.run_case(case)
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['timing']['origin_s'], 7.)
        self.assertEqual(result['timing']['format_origin_s'], 0.)
        self.assertEqual(result['window']['input_seek_s'], 7.)
        self.assertEqual(result['frames'][0]['source_elapsed_s'], 0.)

    def test_active_process_interrupt_and_quota_kill(self):
        stage = self.runner.root/'owned-test-process'
        stage.mkdir()
        launches = []
        actual_popen = subprocess.Popen
        def capture(*args, **kwargs):
            process = actual_popen(*args, **kwargs)
            launches.append(process)
            return process
        actual_check = self.runner.check_deadline
        def interrupt_running():
            actual_check()
            if launches:
                raise KeyboardInterrupt()
        command = [sys.executable, '-c', 'import time; time.sleep(20)']
        with patch('mlpdataset_targeted_review.subprocess.Popen', side_effect=capture):
            with patch.object(self.runner, 'check_deadline', side_effect=interrupt_running):
                with self.assertRaises(KeyboardInterrupt):
                    self.runner.run_process(command, stage/'process.log', stage)
        self.assertIsNotNone(launches[0].poll())
        self.runner.max_bytes = 1024
        command = [sys.executable, '-c',
                   'from pathlib import Path; import time; Path("growth.bin").write_bytes(b"x"*4096); time.sleep(20)']
        # Use an explicit target path, preserving the shared working directory.
        command[-1] = command[-1].replace('"growth.bin"', repr(str(stage/'growth.bin')))
        with self.assertRaisesRegex(ReviewLimitError, 'quota'):
            self.runner.run_process(command, stage/'quota.log', stage)

    def test_clip_hash_corruption_forces_reextraction(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        (self.runner.root/result['clip']['relative_path']).write_bytes(b'bad clip')
        launches = self.runner.stats()['process_launches']
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        self.assertGreater(self.runner.stats()['process_launches'], launches)

    def test_digest_deadline_preserves_committed_checkpoint(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        folder = self.runner.root/result['case_key']
        checkpoint = folder/'checkpoint.json'
        previous = checkpoint.read_bytes()
        launches = self.runner.stats()['process_launches']
        with patch.object(self.runner, 'digest', side_effect=ReviewLimitError('deadline')):
            attempt = self.runner.run_case(self.case)
        self.assertEqual(attempt['status'], 'deadline')
        self.assertEqual(checkpoint.read_bytes(), previous)
        self.assertEqual(json.loads((folder/'last-attempt.json').read_text())['status'], 'deadline')
        self.assertEqual(self.runner.stats()['process_launches'], launches)
        self.assertEqual(self.runner.run_case(self.case), result)

    def test_corrupt_reextraction_failure_preserves_history_without_cache_hit(self):
        result = self.runner.run_case(self.case)
        self.assertEqual(result['status'], 'ready', result)
        folder = self.runner.root/result['case_key']
        checkpoint = folder/'checkpoint.json'
        previous = checkpoint.read_bytes()
        (self.runner.root/result['clip']['relative_path']).write_bytes(b'corrupt')
        hits = self.runner.stats()['cache_hits']
        with patch.object(self.runner, 'run_process', side_effect=RuntimeError('extraction failed')):
            attempt = self.runner.run_case(self.case)
        self.assertEqual(attempt['status'], 'failed')
        self.assertEqual(attempt['frames'], [])
        self.assertEqual(checkpoint.read_bytes(), previous)
        self.assertEqual(json.loads((folder/'last-attempt.json').read_text())['status'], 'failed')
        self.assertEqual(self.runner.stats()['cache_hits'], hits)
        self.assertFalse(list(folder.glob('scratch-*')))
        self.assertEqual(self.runner.run_case(self.case)['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
