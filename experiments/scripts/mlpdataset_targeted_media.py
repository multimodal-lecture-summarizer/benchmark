"""FFmpeg primitives for targeted review; stdlib-only, safe to embed in a notebook."""
import json
import math
import re
from fractions import Fraction
from pathlib import Path


def targeted_window(mark, duration, radius):
    return dict(requested_start_s=mark-radius, requested_end_s=mark+radius,
                effective_start_s=max(0., mark-radius), effective_end_s=min(duration, mark+radius),
                truncated_start=mark-radius < 0, truncated_end=mark+radius > duration)


def targeted_timing(data, fallback_duration):
    stream = data['streams'][0]
    base = Fraction(stream['time_base'])
    if base <= 0:
        raise ValueError('Invalid video time base')
    if stream.get('start_pts') not in (None, 'N/A'):
        ticks = int(stream['start_pts'])
    else:
        exact = Fraction(stream['start_time']) / base
        if exact.denominator != 1:
            raise ValueError('Video origin cannot be represented as integer PTS')
        ticks = int(exact)
    origin = ticks * base
    format_origin = Fraction(data['format']['start_time'])
    duration = stream.get('duration')
    if duration in (None, 'N/A'):
        if origin != 0:
            raise ValueError('Nonzero origin requires video-stream duration')
        duration = fallback_duration
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid video duration')
    return dict(origin_s=float(origin), origin_pts_ticks=ticks, time_base=str(base),
                format_origin_s=float(format_origin), duration_s=duration)


def targeted_decode_pts(log, files, timing, window, mark):
    bases = re.findall(r'config in time_base:\s*(\d+)/(\d+)', log)
    if len(set(bases)) != 1:
        raise ValueError('Missing or changing frame time base')
    num, den = map(int, bases[0])
    if num <= 0 or den <= 0:
        raise ValueError('Invalid selected-frame time base')
    entries = re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', log)
    if not files or [int(n) for n, _ in entries] != list(range(len(files))):
        raise ValueError('Frame/showinfo index mismatch')
    if [p.name for p in files] != [f'frame-{i:04d}.png' for i in range(1, len(files)+1)]:
        raise ValueError('Noncontiguous frame sequence')
    origin = Fraction(timing['origin_pts_ticks']) * Fraction(timing['time_base'])
    rows = []
    for _, raw in entries:
        ticks = int(raw)
        elapsed = float(Fraction(ticks*num, den)-origin)
        if not window['effective_start_s']-.002 <= elapsed <= window['effective_end_s']+.002:
            raise ValueError('Frame outside source window')
        if rows and elapsed <= rows[-1]['source_elapsed_s']:
            raise ValueError('Nonmonotonic PTS')
        rows.append(dict(source_pts_ticks=ticks, source_time_base=f'{num}/{den}',
                         source_elapsed_s=elapsed, offset_s=elapsed-mark))
    return rows
