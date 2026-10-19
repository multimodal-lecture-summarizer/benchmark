"""Read-only run binding and inline review presentation; no annotation decisions."""
import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import uuid


def review_digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def validate_review_inputs(base, queue):
    import pandas as pd
    base = Path(base).resolve(strict=True)
    for item in queue['required_drive_exports']:
        relative = Path(item['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid input artifact path')
        path = (base/relative).resolve(strict=True)
        if base not in path.parents or review_digest(path) != item['sha256']:
            raise ValueError('Input artifact mismatch: '+str(relative))
    videos = pd.read_csv(base/'analysis/video-ledger.csv')
    marks = pd.read_csv(base/'analysis/boundary-ledger.csv')
    if (len(videos) != queue['inventory']['videos'] or len(marks) != queue['inventory']['marks']
            or videos.video_id.duplicated().any() or marks.duplicated(['video_id', 'index']).any()):
        raise ValueError('Full inventory identity/count mismatch')
    if len({(c['video_id'], c['annotation_index']) for c in queue['cases']}) != len(queue['cases']):
        raise ValueError('Duplicate review case')
    checked = {}
    for case in queue['cases']:
        vid = case['video_id']
        hit = marks[(marks.video_id == vid) & (marks['index'] == case['annotation_index'])]
        video = videos[videos.video_id == vid]
        if len(hit) != 1 or len(video) != 1 or abs(float(hit.iloc[0].time_s)-case['annotation_s']) > 1e-8:
            raise ValueError('Released mark identity changed: '+vid)
        if str(video.iloc[0].annotation_sha256) != case['annotation_sha256']:
            raise ValueError('Annotation source hash mismatch: '+vid)
        if vid not in checked:
            state_path = base/'videos'/vid/'state.json'
            state = json.loads(state_path.read_text(encoding='utf8'))
            if (state.get('status') != 'downloaded' or state['identity']['video_id'] != vid
                    or state['sha256'] != case['source_sha256']):
                raise ValueError('Media checkpoint mismatch: '+vid)
            checked[vid] = state
        state = checked[vid]
        if (state['sha256'] != case['source_sha256']
                or case['source_relative_path'] != f"videos/{vid}/{state['file_name']}"):
            raise ValueError('Source path/binding changed: '+vid)
        source_relative = Path(case['source_relative_path'])
        if source_relative.is_absolute() or '..' in source_relative.parts:
            raise ValueError('Invalid cached media relative path')
        source = (base/source_relative).resolve(strict=True)
        if base not in source.parents or not source.is_file():
            raise ValueError('Media path escaped existing cache')
    return dict(videos=len(videos), marks=len(marks), selected_sources=len(checked),
                selected_marks=len(queue['cases']), actual_source_bytes_rehashed=False)


def save_review_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def video_html(data, expected_hash):
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Embedded review clip hash mismatch')
    encoded = base64.b64encode(data).decode('ascii')
    return '<video controls preload="metadata" style="max-width:720px;width:100%" src="data:video/mp4;base64,'+encoded+'"></video>'


def render_review_case(case, result, root):
    """All selected frames retained inline, separate from human review disposition."""
    from PIL import Image
    escape = html.escape
    root = Path(root).resolve()
    label = f"{case['video_id']} mark{case['annotation_index']} @ {case['annotation_s']:.4f}s"
    parts = ['<details><summary>'+escape(label+' — '+result['status'])+'</summary>',
             '<p>'+escape('; '.join(case['reasons']))+'</p>',
             '<p>Semantic/native endpoint: UNREVIEWED. Requested sampling does not certify GT.</p>']
    if result['status'] != 'ready':
        parts.append('<pre>'+escape(str(result.get('error', 'No dense output for this case'))[:1000])+'</pre></details>')
        return ''.join(parts), dict(rendered_frames=0, display_failures=0)
    failures = frames = 0
    window = result['window']
    parts.append('<pre>'+escape(json.dumps(dict(window=window, timing=result['timing']), indent=2))+'</pre>')
    parts.append('<p>Playback is reset; nominal source start='+escape(str(window['effective_start_s']))+
                 's. Use measured original frame PTS below for timing; clip playback is illustrative.</p>')
    try:
        clip = result['clip'];path = (root/clip['relative_path']).resolve(strict=True)
        path.relative_to(root)
        parts.append(video_html(path.read_bytes(), clip['sha256']))
    except Exception as exc:
        failures += 1
        parts.append('<p>Clip display unavailable: '+escape(str(exc))+'</p>')
    parts.append('<div style="display:flex;flex-wrap:wrap;gap:4px">')
    for frame in result['frames']:
        caption = (f"source={frame['source_elapsed_s']:.6f}s; offset={frame['offset_s']:+.6f}s; "
                   f"PTS={frame['source_pts_ticks']} * {frame['source_time_base']}")
        parts.append('<figure style="margin:2px;width:230px"><figcaption>'+escape(caption)+'</figcaption>')
        try:
            path = (root/frame['relative_path']).resolve(strict=True);path.relative_to(root)
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != frame['sha256']:
                raise ValueError('Frame hash mismatch')
            with Image.open(io.BytesIO(data)) as image:
                buf = io.BytesIO();image.convert('RGB').save(buf, format='JPEG', quality=85)
            parts.append('<img style="width:230px" loading="lazy" src="data:image/jpeg;base64,'+
                         base64.b64encode(buf.getvalue()).decode('ascii')+'">')
            frames += 1
        except Exception as exc:
            failures += 1;parts.append('<p>Display unavailable: '+escape(str(exc))+'</p>')
        parts.append('</figure>')
    parts.append('</div><details><summary>Complete extraction logs</summary>')
    for name in ['log', 'clip_log']:
        try:
            path = (root/result[name]['relative_path']).resolve(strict=True);path.relative_to(root)
            parts.append('<pre>'+escape(path.read_text(encoding='utf8', errors='replace'))+'</pre>')
        except OSError as exc:
            parts.append('<pre>'+escape(str(exc))+'</pre>')
    parts.append('</details></details>')
    return ''.join(parts), dict(rendered_frames=frames, display_failures=failures)
