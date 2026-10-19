"""Cache-only native temporal review; extraction never certifies ground truth."""
import base64
from fractions import Fraction
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import uuid

if 'ReviewRunner' not in globals():
    from mlpdataset_targeted_review import ReviewRunner, ReviewLimitError
    from mlpdataset_targeted_media import targeted_timing


class NativeReviewRunner(ReviewRunner):
    VERSION = 'mlpdataset-native-review-v1'

    def __init__(self, base, review_root, queue, **kwargs):
        super().__init__(base, review_root, **kwargs)
        self.config = dict(version=self.VERSION, width=self.config['width'],
                           cadence='all_presentation_frames_passthrough', half_open=True)
        self.queue = queue
        self.top_binding = {k: v for k, v in queue.items() if k != 'jobs'}

    def binding(self, job):
        start, end, duration = (float(job[k]) for k in ('start_s', 'end_s', 'duration_s'))
        if not all(math.isfinite(v) for v in (start, end, duration)) or not 0 <= start < end <= duration:
            raise ValueError('Invalid explicit half-open native bounds')
        if not job['original_keys'] or not job['source_bindings']:
            raise ValueError('Missing original-row bindings')
        return dict(queue=self.top_binding, job=job, config=self.config.copy())

    @staticmethod
    def expected_pts(probe, timing, job):
        base = Fraction(timing['time_base'])
        origin = timing['origin_pts_ticks'] * base
        start, end = Fraction(str(job['start_s'])), Fraction(str(job['end_s']))
        pts = [int(row['pts']) for row in probe['frames'] if 'pts' in row]
        if len(pts) != len(probe['frames']):
            raise ValueError('Native probe missing presentation PTS')
        pts = [p for p in pts if start <= p * base - origin < end]
        if not pts or any(b <= a for a, b in zip(pts, pts[1:])):
            raise ValueError('Empty or nonmonotonic native PTS')
        return pts

    def native_cached(self, folder, binding):
        try:
            result = json.loads((folder/'checkpoint.json').read_text(encoding='utf8'))
            if result['binding'] != binding or result['status'] != 'ready':
                return None
            artifacts = result['artifacts']
            expected_paths = [x['relative_path'] for x in result['frames']]
            expected_paths += [result[k]['relative_path'] for k in ('probe', 'native_probe', 'log')]
            if set(expected_paths) != {x['relative_path'] for x in artifacts} or len(expected_paths) != len(artifacts):
                return None
            for item in artifacts:
                path = (self.root/item['relative_path']).resolve(strict=True)
                if self.root not in path.parents or path.stat().st_size != item['size_bytes'] or self.digest(path) != item['sha256']:
                    return None
            timing = targeted_timing(json.loads((self.root/result['probe']['relative_path']).read_text()), binding['job']['duration_s'])
            probe = json.loads((self.root/result['native_probe']['relative_path']).read_text())
            pts = self.expected_pts(probe, timing, binding['job'])
            rows = self.decode((self.root/result['log']['relative_path']).read_text(), timing, pts)
            if timing != result['timing'] or len(rows) != len(result['frames']):
                return None
            for row, frame, artifact in zip(rows, result['frames'], artifacts):
                if any(frame[k] != v for k, v in row.items()) or {k: frame[k] for k in artifact} != artifact:
                    return None
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def decode(log, timing, expected):
        bases = re.findall(r'config in time_base:\s*(\d+)/(\d+)', log)
        if len(set(bases)) != 1 or Fraction('/'.join(bases[0])) != Fraction(timing['time_base']):
            raise ValueError('Native output time base differs from source')
        entries = re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', log)
        if [int(n) for n, _ in entries] != list(range(len(expected))) or [int(p) for _, p in entries] != expected:
            raise ValueError(f'Native cadence differs: decoded={entries}; ffprobe={expected}')
        base = Fraction(timing['time_base'])
        return [dict(native_frame_index=i, source_pts_ticks=p, source_time_base=timing['time_base'],
                     source_elapsed_s=float((p-timing['origin_pts_ticks'])*base)) for i, p in enumerate(expected)]

    def run_job(self, job):
        stage = folder = None
        result = dict(status='failed', frames=[], artifacts=[], gt_disposition='hold', native_point=None)
        try:
            binding = self.binding(job)
            key = hashlib.sha256(self.canonical(binding).encode()).hexdigest()
            result.update(binding=binding, case_key=key)
            folder = self.root/key
            folder.mkdir(exist_ok=True)
            if folder.is_symlink() or folder.resolve() != folder:
                folder = None
                raise ValueError('Native output escapes root')
            self.check_deadline()
            source, fingerprint = self.source(job)
            cached = self.native_cached(folder, binding)
            if cached:
                self.metrics['cache_hits'] += 1
                return cached
            media = Path(self.stage_getter(source, job['source_sha256'], self.deadline)) if self.stage_getter else source
            self.check_deadline()
            stage = Path(tempfile.mkdtemp(prefix='scratch-', dir=folder))
            self.run_process(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                              'stream=start_time,start_pts,time_base,duration:format=start_time', '-of', 'json', str(media)], stage/'probe.json', stage)
            timing = targeted_timing(json.loads((stage/'probe.json').read_text()), job['duration_s'])
            if job['end_s'] > timing['duration_s']:
                raise ValueError('Job exceeds probed source duration')
            base = Fraction(timing['time_base'])
            # Integer trim thresholds implement [start,end) without rounded timestamp tolerances.
            start_pts = timing['origin_pts_ticks'] + math.ceil(Fraction(str(job['start_s']))/base)
            end_pts = timing['origin_pts_ticks'] + math.ceil(Fraction(str(job['end_s']))/base)
            start_abs = float(start_pts*base)
            end_abs = float(end_pts*base)
            self.run_process(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-read_intervals',
                              f'{start_abs}%{end_abs+5}', '-show_frames', '-show_entries', 'frame=pts', '-of', 'json', str(media)], stage/'native-probe.json', stage)
            expected = self.expected_pts(json.loads((stage/'native-probe.json').read_text()), timing, job)
            seek = timing['origin_s'] + float(job['start_s']) - timing['format_origin_s']
            vf = f"trim=start_pts={start_pts}:end_pts={end_pts},scale={self.config['width']}:-2,showinfo"
            self.run_process(['ffmpeg', '-nostdin', '-hide_banner', '-v', 'info', '-y', '-copyts',
                              '-ss', str(seek), '-t', str(float(job['end_s'])-float(job['start_s'])+5), '-i', str(media), '-map', '0:v:0', '-an', '-vf', vf,
                              '-fps_mode', 'passthrough', '-start_number', '1', str(stage/'frame-%06d.png')], stage/'frames.log', stage)
            files = sorted(stage.glob('frame-*.png'))
            rows = self.decode((stage/'frames.log').read_text(errors='replace'), timing, expected)
            if len(files) != len(rows) or [p.name for p in files] != [f'frame-{i:06d}.png' for i in range(1, len(rows)+1)]:
                raise ValueError('Native PNG sequence mismatch')
            if self.fingerprint(source) != fingerprint:
                raise ReviewLimitError('source_changed')
            published = folder/('artifacts-'+uuid.uuid4().hex)
            stage.rename(published)
            stage = published
            frames = [dict(**self.artifact(published/p.name), **row) for p, row in zip(files, rows)]
            result.update(status='ready', timing=timing, frames=frames,
                          cadence_verified=True, temporal_native_only=True)
            for name, filename in [('probe', 'probe.json'), ('native_probe', 'native-probe.json'), ('log', 'frames.log')]:
                result[name] = self.artifact(published/filename)
            result['artifacts'] = [{k: f[k] for k in ('relative_path', 'sha256', 'size_bytes')} for f in frames]
            result['artifacts'] += [result[k] for k in ('probe', 'native_probe', 'log')]
            self.checkpoint(folder, result)
            stage = None
            self.metrics['cases_ready'] += 1
            return result
        except (Exception, KeyboardInterrupt) as error:
            result.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else str(error) if isinstance(error, ReviewLimitError) else 'failed',
                          error=f'{type(error).__name__}: {error}'[:500], frames=[], artifacts=[])
            for name in ('probe', 'native_probe', 'log'):
                result.pop(name, None)
            self.metrics['failures'] += 1
            if folder:
                self.failed_attempt(folder, result)
            if isinstance(error, KeyboardInterrupt):
                raise
            return result
        finally:
            if stage is not None:
                shutil.rmtree(stage)


def run_native_queue(runner, progress=print):
    """Persist every job and original identity before work, after each job, on interrupt."""
    queue, results = runner.queue, {}
    jobs = queue['jobs']
    rows = queue['original_queue']['cases']
    receipt = dict(queue_id=queue['queue_id'], queue_binding=dict(queue=queue, config=runner.config),
                   results=results, evaluation_ready=False, semantic_certified_events=0,
                   gt_status='pending', native_point=None, annotation_repairs_applied=0)
    def save():
        receipt['job_statuses'] = [dict(job_id=j['job_id'], status=results.get(j['job_id'], {}).get('status', 'not_attempted')) for j in jobs]
        receipt['original_row_statuses'] = []
        for row in rows:
            key = str(row['video_id'])+':'+str(row['annotation_index'])
            relevant = [j['job_id'] for j in jobs if key in j['original_keys']]
            receipt['original_row_statuses'].append(dict(key=key, job_ids=relevant,
                extraction_statuses={j:results.get(j, {}).get('status', 'not_attempted') for j in relevant},
                native_review_status='unreviewed', gt_disposition='hold', native_point=None))
        receipt['runner'] = runner.stats()
        runner.checkpoint(runner.root, receipt, 'native-review-receipt.json')
    save()
    try:
        for i, job in enumerate(jobs, 1):
            progress(f"Native [{i}/{len(jobs)}] {job['job_id']}")
            try:
                results[job['job_id']] = runner.run_job(job)
            except KeyboardInterrupt:
                results[job['job_id']] = dict(status='interrupted', frames=[], native_point=None)
                raise
            save()
            progress(f"  {results[job['job_id']]['status']}; frames={len(results[job['job_id']].get('frames', []))}")
            if results[job['job_id']]['status'] in ('deadline', 'quota', 'free_space'):
                break
    finally:
        save()
    return receipt


def render_native_job(job, result, root, remaining_bytes):
    """Inline every retained native frame or explicitly represent its display omission."""
    from PIL import Image
    root = Path(root).resolve(strict=True)
    def verified_bytes(item):
        relative = Path(item['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid native display artifact path')
        path = (root/relative).resolve(strict=True)
        if root not in path.parents or not path.is_file():
            raise ValueError('Native display artifact escapes output root')
        data = path.read_bytes()
        if len(data) != item['size_bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Native display artifact hash/size mismatch')
        return data
    blocks, rendered, used, omitted = [], 0, 0, 0
    for frame in result.get('frames', []):
        label = f"Frame {frame['native_frame_index']} | PTS {frame['source_pts_ticks']} × {frame['source_time_base']} | elapsed {frame['source_elapsed_s']:.9f}s"
        with Image.open(io.BytesIO(verified_bytes(frame))) as picture:
            stream = io.BytesIO()
            picture.convert('RGB').save(stream, format='JPEG', quality=72)
        encoded = base64.b64encode(stream.getvalue()).decode('ascii')
        if used+len(encoded) <= remaining_bytes:
            blocks.append('<figure style="margin:4px;width:230px"><img loading="lazy" width="230" style="max-width:100%;height:auto" src="data:image/jpeg;base64,'+encoded+'"><figcaption>'+html.escape(label)+'</figcaption></figure>')
            used += len(encoded)
            rendered += 1
        else:
            blocks.append('<p>'+html.escape(label+' — retained PNG; inline display budget reached: '+frame['relative_path'])+'</p>')
            omitted += 1
    if result.get('log'):
        log = verified_bytes(result['log']).decode('utf8', errors='replace')
        blocks.append('<details><summary>Complete extraction log</summary><pre>'+html.escape(log)+'</pre></details>')
    stats = dict(status='partial_display_budget' if omitted else 'complete', rendered_frames=rendered,
                 retained_frames=len(result.get('frames', [])), omitted_inline_frames=omitted,
                 payload_bytes=used, payload_budget_scope='base64_jpeg_images_only')
    return '<details><summary>'+html.escape(job['job_id']+' — '+result['status'])+'</summary><div style="display:flex;flex-wrap:wrap;gap:8px;max-height:680px;overflow:auto">'+''.join(blocks)+'</div></details>', stats
