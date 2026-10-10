"""Bounded public official-source probes; persist failures, never bypass access controls."""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
import requests
from dataset_qualification_io import ROOT, OUT, write_json, sha


def fetch(dataset, label, url):
    record = dict(dataset=dataset, label=label, url=url, observed_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        response = requests.get(url, timeout=25)
        record.update(status=response.status_code, final_url=response.url,
                      sha256=hashlib.sha256(response.content).hexdigest(), bytes=len(response.content))
        suffix = '.json' if 'json' in response.headers.get('content-type', '') else '.txt'
        path = OUT / (dataset + '-' + label + suffix)
        path.write_bytes(response.content)
        record['response_path'] = str(path.relative_to(ROOT))
        return record, response
    except requests.RequestException as exc:
        record['error'] = str(exc)
        return record, None


def video_probe(dataset, video_id, url):
    # Metadata-only extraction verifies whether normal official media acquisition is possible.
    # No cookies, login, proxy or anti-bot bypass. A failed sample is not all-video unavailability.
    command = [sys.executable, '-m', 'yt_dlp', '--skip-download', '--dump-single-json',
               '--no-playlist', '--no-warnings', '--socket-timeout', '12', '--retries', '0', url]
    record = dict(dataset=dataset, id=video_id, url=url,
                  observed_at_utc=datetime.now(timezone.utc).isoformat(),
                  scope='one deterministic source video; metadata extraction only; no media decoded')
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=70)
        record.update(exit_code=result.returncode, stderr=result.stderr)
        path = OUT / (dataset + '-media-probe-' + video_id + '.txt')
        path.write_text(result.stdout + '\nSTDERR\n' + result.stderr, encoding='utf-8')
        record.update(response_path=str(path.relative_to(ROOT)), sha256=sha(path))
        if result.returncode == 0:
            info = json.loads(result.stdout)
            record.update(duration=info.get('duration'), title=info.get('title'),
                          license=info.get('license'), uploader=info.get('uploader'),
                          media_restored=False, decision='HOLD_alignment_and_rights_review')
        else:
            record['decision'] = 'HOLD_sample_acquisition_failed'
    except subprocess.TimeoutExpired:
        record.update(error='70-second bounded probe timeout', decision='HOLD_sample_probe_timeout')
    return record


def clip_probe(dataset, video_id, url):
    """Recover a 20-second low-resolution sample, with explicit CPU decoding evidence."""
    path = OUT / (dataset + '-sample-' + video_id + '.mp4')
    command = [sys.executable, '-m', 'yt_dlp', '--no-playlist', '--no-warnings',
               '--socket-timeout', '12', '--retries', '0', '--download-sections', '*0-20',
               '-f', 'worst[ext=mp4]/worst', '--max-filesize', '30M', '-o', str(path), url]
    record = dict(dataset=dataset, id=video_id, url=url, section='0-20s', max_bytes=30000000,
                  observed_at_utc=datetime.now(timezone.utc).isoformat(), decision='HOLD_alignment_review')
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=100)
        log = OUT / (dataset + '-clip-probe-' + video_id + '.txt')
        log.write_text(result.stdout + '\nSTDERR\n' + result.stderr, encoding='utf-8')
        record.update(exit_code=result.returncode, log_path=str(log.relative_to(ROOT)), log_sha256=sha(log))
        if result.returncode == 0 and path.exists():
            record.update(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size)
            decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'],
                                     capture_output=True, text=True, timeout=35)
            record.update(cpu_decode_exit_code=decoded.returncode, cpu_decode_errors=decoded.stderr,
                          media_sample_valid=decoded.returncode == 0)
            frame = OUT / (dataset + '-sample-' + video_id + '.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '5', '-i', str(path), '-frames:v', '1',
                            '-vf', 'scale=640:-2', str(frame)], capture_output=True, timeout=20)
            if frame.exists():
                record.update(frame_path=str(frame.relative_to(ROOT)), frame_sha256=sha(frame))
        else:
            record['decision'] = 'HOLD_sample_download_failed'
    except subprocess.TimeoutExpired:
        record.update(error='bounded clip download/decode timeout', decision='HOLD_sample_timeout')
    return record


def main():
    probes = []
    # Respect requested dataset order. LVVO source mapping blocker was recorded by parent.
    mlp = list(csv.DictReader((OUT / 'mlpdataset-id-ledger.csv').open(encoding='utf-8')))
    first = sorted((r for r in mlp if r.get('source_url')), key=lambda r: r['id'])[0]
    probes.append(video_probe('mlpdataset', first['id'], first['source_url']))
    probe, _ = fetch('accessmath', 'official-project-page', 'https://www.cs.rit.edu/~rlaz/Projects/AccessMath.html')
    probes.append(probe)
    probe, response = fetch('lecturemath', 'official-commit', 'https://api.github.com/repos/kdavila/lecturemath/commits/master')
    probes.append(probe)
    revision = response.json()['sha'] if response is not None and response.ok else None
    if revision:
        for label, path in [('official-readme', 'ACCESS2021_release/README.md'),
                            ('official-db', 'ACCESS2021_release/lecture_data/db_LectureMath.xml'),
                            ('official-edited', 'ACCESS2021_release/lecture_data/video_edited_gt_34.json'),
                            ('official-tree', None)]:
            url = (f'https://raw.githubusercontent.com/kdavila/lecturemath/{revision}/{path}' if path else
                   f'https://api.github.com/repos/kdavila/lecturemath/git/trees/{revision}?recursive=1')
            item, _ = fetch('lecturemath', label, url)
            item['revision'] = revision
            probes.append(item)
    lm = list(csv.DictReader((OUT / 'lecturemath-id-ledger.csv').open(encoding='utf-8')))
    first = sorted((r for r in lm if r.get('source_link')), key=lambda r: r['id'])[0]
    probes.append(video_probe('lecturemath', first['id'], first['source_link']))
    # Official LectureMath source 00000 is the potential AccessMath bridge, not a verified alignment.
    probes.append(dict(dataset='accessmath', label='potential-official-source-bridge',
                       source_url=first['source_link'], lecturemath_id=first['id'],
                       source_group=first['source_id'], decision='HOLD',
                       reason='LectureMath released source 00000 references AccessMath; multipart camera timebase not verified'))
    item, _ = fetch('eduvidqa', 'pinned-readme',
                    'https://raw.githubusercontent.com/sourjyadip/eduvidqa-emnlp25/aab6cc03e43182cc916f14ed2aca495f57a1ed96/README.md')
    probes.append(item)
    edu = list(csv.DictReader((OUT / 'eduvidqa-source-group-ledger.csv').open(encoding='utf-8')))
    first = sorted(edu, key=lambda r: r['id'])[0]
    probes.append(video_probe('eduvidqa', first['id'], first['source_url']))
    write_json('remaining-datasets-source-probes.json', probes)
    for dataset in ['mlpdataset', 'accessmath', 'lecturemath', 'eduvidqa']:
        path = OUT / (dataset + '-qualification-receipt.json')
        value = json.loads(path.read_text(encoding='utf-8'))
        value['source_probes'] = [p for p in probes if p['dataset'] == dataset]
        value['media_probe_limit'] = 'Bounded deterministic source probes only; no full availability survey or original media decode.'
        write_json(path.name, value)
    print(json.dumps([{k: p.get(k) for k in ['dataset', 'label', 'id', 'status', 'exit_code', 'decision']} for p in probes], indent=2))


if __name__ == '__main__':
    if '--clips' in sys.argv:
        probes = json.loads((OUT / 'remaining-datasets-source-probes.json').read_text(encoding='utf-8'))
        clips = [clip_probe(p['dataset'], p['id'], p['url']) for p in probes if p.get('exit_code') == 0]
        write_json('remaining-datasets-media-clips.json', clips)
        for dataset in ['mlpdataset', 'accessmath', 'lecturemath', 'eduvidqa']:
            path = OUT / (dataset + '-qualification-receipt.json')
            value = json.loads(path.read_text(encoding='utf-8'))
            value['bounded_media_samples'] = [p for p in clips if p['dataset'] == dataset]
            value['source_aligned_media_valid'] = 0
            write_json(path.name, value)
        print(json.dumps(clips, indent=2))
    else:
        main()
