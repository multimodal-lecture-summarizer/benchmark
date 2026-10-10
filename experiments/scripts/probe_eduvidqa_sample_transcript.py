"""One bounded author-recommended transcript retrieval; no retrieval GT creation."""
from datetime import datetime, timezone
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from dataset_qualification_io import OUT, write_json
import json

record = dict(dataset='eduvidqa', video_id='-Lw8isQCi4g',
              observed_at_utc=datetime.now(timezone.utc).isoformat(),
              scope='One deterministic source; no independent evidence-span labels')
session = requests.Session()
original_request = session.request
session.request = lambda *a, **kw: original_request(*a, **dict(kw, timeout=20))
try:
    result = YouTubeTranscriptApi(http_client=session).fetch(record['video_id'])
    data = result.to_raw_data()
    artifact = write_json('eduvidqa-sample-transcript--Lw8isQCi4g.json', data)
    record.update(status='recovered', segments=len(data), artifact=artifact)
except Exception as error:
    record.update(status='HOLD', error_type=type(error).__name__, error=str(error))
artifact = write_json('eduvidqa-sample-transcript-probe.json', record)
path = OUT / 'eduvidqa-qualification-receipt.json'
receipt = json.loads(path.read_text(encoding='utf-8'))
receipt['sampled_transcript_probe'] = record
receipt['artifacts'] = [a for a in receipt['artifacts'] if a['path'] != artifact['path']] + [artifact]
write_json(path.name, receipt)
print(json.dumps(record, indent=2))
