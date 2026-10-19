"""Bounded cached-source review. No downloads or writes to the original source cache.

Embed the media module first, then this module in a standalone notebook. Construct
one ReviewRunner per session and call run_case sequentially. stage_getter, when
provided, has signature (source_path, expected_sha256, absolute_monotonic_deadline)
and must return a verified local copy; its lifecycle belongs to the caller.
Only status='ready' certifies complete frame, clip and log artifacts. It never
certifies human adjudication. All paths returned are relative to review_root.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

if 'targeted_timing' not in globals():
    from mlpdataset_targeted_media import targeted_timing, targeted_window, targeted_decode_pts


class ReviewLimitError(RuntimeError):
    pass


class ReviewRunner:
    VERSION = 'mlpdataset-targeted-review-v1'

    def __init__(self, base, review_root, max_minutes=60, max_bytes=.75*1024**3,
                 min_free_bytes=1024**3, radius=5, interval=.25, width=480,
                 process_timeout=60, max_clip_bytes=5*1024**2, stage_getter=None):
        self.base = Path(base).resolve(strict=True)
        self.root = Path(review_root).resolve()
        if self.root == self.base or self.base in self.root.parents:
            raise ValueError('review_root must be outside source cache')
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = dict(version=self.VERSION, radius=float(radius), interval=float(interval),
                           width=int(width), max_clip_bytes=int(max_clip_bytes))
        if any(not math.isfinite(v) or v <= 0 for v in
               (radius, interval, width, process_timeout, max_minutes, max_bytes, max_clip_bytes)):
            raise ValueError('Extraction configuration must be positive and finite')
        if not math.isfinite(min_free_bytes) or min_free_bytes < 0:
            raise ValueError('Free-space floor must be finite and nonnegative')
        self.deadline = time.monotonic()+float(max_minutes)*60
        self.max_bytes, self.min_free_bytes = int(max_bytes), int(min_free_bytes)
        self.process_timeout, self.stage_getter = float(process_timeout), stage_getter
        self.verified = {}
        self.metrics = dict(source_hashes=0, source_cache_hits=0, cases_ready=0, cache_hits=0,
                            process_launches=0, failures=0)

    @staticmethod
    def fingerprint(path):
        s = path.stat()
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise ReviewLimitError('deadline')

    def digest(self, path):
        h = hashlib.sha256()
        with path.open('rb') as handle:
            while True:
                self.check_deadline()
                block = handle.read(1024*1024)
                if not block:
                    break
                h.update(block)
        self.check_deadline()
        return h.hexdigest()

    @staticmethod
    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

    def source(self, case):
        relative = Path(case['source_relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid source relative path')
        video_id = str(case['video_id'])
        if len(relative.parts) < 3 or relative.parts[:2] != ('videos', video_id):
            raise ValueError('Source must be videos/{video_id}/file')
        source = (self.base/relative).resolve(strict=True)
        if self.base not in source.parents or not source.is_file():
            raise ValueError('Source escapes cache')
        expected = str(case['source_sha256']).lower()
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Invalid source SHA256')
        fingerprint = self.fingerprint(source)
        key = str(source)
        if key in self.verified:
            if self.verified[key] != (fingerprint, expected):
                raise ReviewLimitError('source_changed')
            self.metrics['source_cache_hits'] += 1
        else:
            self.metrics['source_hashes'] += 1
            if self.digest(source) != expected:
                raise ReviewLimitError('source_mismatch')
            if self.fingerprint(source) != fingerprint:
                raise ReviewLimitError('source_changed')
            self.verified[key] = (fingerprint, expected)
        return source, fingerprint

    @staticmethod
    def tree_bytes(path):
        return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())

    def run_process(self, command, log, stage):
        # One root snapshot per process; subsequent polls only inspect owned stage.
        baseline = self.tree_bytes(self.root)-self.tree_bytes(stage)
        self.check_deadline()
        process_deadline = min(self.deadline, time.monotonic()+self.process_timeout)
        process = None
        def enforce():
            self.check_deadline()
            if baseline+self.tree_bytes(stage) > self.max_bytes:
                raise ReviewLimitError('quota')
            if shutil.disk_usage(self.root).free < self.min_free_bytes:
                raise ReviewLimitError('free_space')
            if time.monotonic() >= process_deadline:
                raise ReviewLimitError('process_timeout')
        enforce()
        try:
            with log.open('wb') as output:
                enforce()
                process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
                self.metrics['process_launches'] += 1
                while process.poll() is None:
                    enforce()
                    time.sleep(.05)
                enforce()
                if process.returncode:
                    raise RuntimeError(f'FFmpeg/ffprobe exit {process.returncode}; see {log.name}')
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()

    def artifact(self, path):
        return dict(relative_path=path.relative_to(self.root).as_posix(),
                    sha256=self.digest(path), size_bytes=path.stat().st_size)

    def checkpoint(self, folder, result, name='checkpoint.json'):
        temp = folder/('checkpoint-'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(self.canonical(result), encoding='utf-8')
            os.replace(temp, folder/name)
        finally:
            temp.unlink(missing_ok=True)

    def failed_attempt(self, folder, result):
        # A later attempt cannot erase a previously committed extraction. This
        # preserves history only: cached() must still validate every artifact.
        try:
            previous = json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))
            preserve = (isinstance(previous, dict) and previous.get('status') == 'ready' and
                        previous.get('binding') == result.get('binding'))
        except (OSError, ValueError, TypeError):
            preserve = False
        self.checkpoint(folder, result, 'last-attempt.json' if preserve else 'checkpoint.json')

    def cached(self, folder, binding):
        try:
            result = json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))
            if result['binding'] != binding or result['status'] != 'ready':
                return None
            artifacts = result['artifacts']
            expected = {f['relative_path'] for f in result['frames']}
            expected.update([result['clip']['relative_path'], result['log']['relative_path'],
                             result['probe']['relative_path'], result['clip_log']['relative_path']])
            if not artifacts or expected != {a['relative_path'] for a in artifacts}:
                return None
            for entry in artifacts:
                path = (self.root/entry['relative_path']).resolve(strict=True)
                if self.root not in path.parents or path.stat().st_size != entry['size_bytes']:
                    return None
                if self.digest(path) != entry['sha256']:
                    return None
            probe = json.loads((self.root/result['probe']['relative_path']).read_text(encoding='utf-8'))
            timing = targeted_timing(probe, binding['case']['duration_s'])
            window = targeted_window(binding['case']['annotation_s'], timing['duration_s'], self.config['radius'])
            window['input_seek_s'] = timing['origin_s']+window['effective_start_s']-timing['format_origin_s']
            if result['timing'] != timing or result['window'] != window:
                return None
            log = (self.root/result['log']['relative_path']).read_text(encoding='utf-8', errors='replace')
            rows = targeted_decode_pts(log, [self.root/f['relative_path'] for f in result['frames']],
                                       timing, window, binding['case']['annotation_s'])
            for row, frame in zip(rows, result['frames']):
                if any(frame[k] != v for k, v in row.items()):
                    return None
            if any(next(a for a in artifacts if a['relative_path'] == f['relative_path']) !=
                   {k: f[k] for k in ('relative_path', 'sha256', 'size_bytes')} for f in result['frames']):
                return None
            for name in ('clip', 'log', 'probe', 'clip_log'):
                if result[name] not in artifacts:
                    return None
            return result
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            return None

    def run_case(self, case):
        stage = None
        folder = None
        result = dict(status='failed', frames=[], artifacts=[], error='')
        try:
            normalized = {k: case[k] for k in ('video_id', 'annotation_index', 'annotation_s',
                          'source_sha256', 'source_relative_path', 'duration_s')}
            normalized['annotation_s'] = float(normalized['annotation_s'])
            normalized['duration_s'] = float(normalized['duration_s'])
            if not math.isfinite(normalized['annotation_s']) or not math.isfinite(normalized['duration_s']) or normalized['duration_s'] <= 0:
                raise ValueError('Invalid annotation or duration')
            binding = dict(case=normalized, config=self.config.copy())
            key = hashlib.sha256(self.canonical(binding).encode()).hexdigest()
            result.update(case_key=key, binding=binding)
            folder = self.root/key
            folder.mkdir(exist_ok=True)
            if folder.is_symlink() or folder.resolve() != folder:
                folder = None
                raise ValueError('Case output directory escapes review root')
            self.check_deadline()
            source, fingerprint = self.source(normalized)
            hit = self.cached(folder, binding)
            if hit is not None:
                self.metrics['cache_hits'] += 1
                return hit
            self.check_deadline()
            media = Path(self.stage_getter(source, normalized['source_sha256'], self.deadline)) if self.stage_getter else source
            self.check_deadline()
            if self.fingerprint(source) != fingerprint:
                raise ReviewLimitError('source_changed')
            stage = Path(tempfile.mkdtemp(prefix='scratch-', dir=folder))
            probe_path = stage/'probe.json'
            self.run_process(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                             'stream=start_time,start_pts,time_base,duration:format=start_time',
                             '-of', 'json', str(media)], probe_path, stage)
            timing = targeted_timing(json.loads(probe_path.read_text(encoding='utf-8')), normalized['duration_s'])
            window = targeted_window(normalized['annotation_s'], timing['duration_s'], self.config['radius'])
            result.update(timing=timing, window=window)
            if window['effective_end_s'] <= window['effective_start_s']:
                result['status'] = 'outside_video'
                self.checkpoint(folder, result)
                return result
            window['input_seek_s'] = timing['origin_s']+window['effective_start_s']-timing['format_origin_s']
            start, span = window['input_seek_s'], window['effective_end_s']-window['effective_start_s']
            vf = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{self.config['interval']})',scale={self.config['width']}:-2,showinfo"
            frame_log = stage/'frames.log'
            self.run_process(['ffmpeg', '-nostdin', '-hide_banner', '-v', 'info', '-y', '-copyts',
                              '-ss', str(start), '-t', str(span), '-i', str(media), '-map', '0:v:0',
                              '-an', '-vf', vf, '-fps_mode', 'vfr', '-start_number', '1',
                              str(stage/'frame-%04d.png')], frame_log, stage)
            files = sorted(stage.glob('frame-*.png'))
            rows = targeted_decode_pts(frame_log.read_text(encoding='utf-8', errors='replace'),
                                       files, timing, window, normalized['annotation_s'])
            clip, clip_log = stage/'clip.mp4', stage/'clip.log'
            self.run_process(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(start), '-t', str(span),
                              '-i', str(media), '-map', '0:v:0', '-an', '-vf', f"scale={self.config['width']}:-2",
                              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28', '-maxrate', '500k',
                              '-bufsize', '1000k', '-movflags', '+faststart', str(clip)], clip_log, stage)
            if not clip.is_file() or not 0 < clip.stat().st_size <= self.config['max_clip_bytes']:
                raise ReviewLimitError('clip_size_limit')
            if self.fingerprint(source) != fingerprint:
                raise ReviewLimitError('source_changed')
            self.check_deadline()
            published = folder/('artifacts-'+uuid.uuid4().hex)
            stage.rename(published)
            stage = published  # Cleanup still owns every file until checkpoint is committed.
            frames = [dict(**self.artifact(published/p.name), **row) for p, row in zip(files, rows)]
            result.update(status='ready', frames=frames, clip=self.artifact(published/'clip.mp4'),
                          log=self.artifact(published/'frames.log'), probe=self.artifact(published/'probe.json'),
                          clip_log=self.artifact(published/'clip.log'))
            result['artifacts'] = [{k: f[k] for k in ('relative_path', 'sha256', 'size_bytes')} for f in frames]
            result['artifacts'].extend(result[n] for n in ('clip', 'log', 'probe', 'clip_log'))
            self.checkpoint(folder, result)
            stage = None
            self.metrics['cases_ready'] += 1
            return result
        except (Exception, KeyboardInterrupt) as exc:
            self.metrics['failures'] += 1
            result.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else
                          str(exc) if isinstance(exc, ReviewLimitError) else 'failed',
                          error=f'{type(exc).__name__}: {exc}'[:500], frames=[], artifacts=[])
            for name in ('clip', 'log', 'probe', 'clip_log'):
                result.pop(name, None)
            if folder is not None:
                self.failed_attempt(folder, result)
            return result
        finally:
            if stage is not None:
                # Only the flat, uniquely-created scratch directory owned by this call.
                for path in stage.iterdir():
                    if path.is_file() or path.is_symlink():
                        path.unlink()
                stage.rmdir()

    def stats(self):
        return dict(self.metrics, remaining_seconds=max(0., self.deadline-time.monotonic()),
                    review_root=str(self.root))
