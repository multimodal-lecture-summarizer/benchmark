"""Freeze a targeted review queue from saved EDA outputs, never from predictions."""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT/'benchmark/experiments/outputs/mlpdataset_eda_review_261019'
HISTORY = ROOT/'benchmark/experiments/outputs/mlpdataset_dense_executed_review_261017'
NOTEBOOK = ROOT/'benchmark/experiments/notebooks/diagnostics/mlpdataset_slide_transition_eda_colab.ipynb'
REGISTRY = ROOT/'benchmark/experiments/registry/datasets'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_queue():
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf8'))
    states = receipt = None
    for output in notebook['cells'][31]['outputs']:
        if output.get('output_type') != 'stream':
            continue
        try:
            value = json.loads(''.join(output.get('text', [])))
        except ValueError:
            continue
        if isinstance(value, dict) and 'artifacts' in value:
            receipt = value
        elif isinstance(value, list) and len(value) == 333 and 'identity' in value[0]:
            states = {s['identity']['video_id']: s for s in value}
    assert receipt and states and len(states) == 333
    marks = pd.read_csv(EDA/'cell29-output3-table0.csv')
    videos = pd.read_csv(EDA/'cell29-output1-table0.csv').set_index('video_id')
    observed = pd.read_csv(EDA/'detailed-visual-observations.csv')
    old_rows = pd.read_csv(HISTORY/'table-28-132.csv')
    old_frames = pd.read_csv(HISTORY/'table-28-134.csv')
    old_receipt = json.loads((HISTORY/'receipt.json').read_text())
    old_artifacts = {a['path']: a for a in old_receipt['artifacts']}
    reasons = {}

    def add(vid, index, reason):
        reasons.setdefault((str(vid), int(index)), set()).add(reason)

    for row in observed.itertuples():
        if row.observation_category != 'visible_content_change':
            add(row.video_id, row.index, 'visually_ambiguous_sparse_window')
    for row in marks[marks.nonincreasing].itertuples():
        add(row.video_id, row.index, 'nonincreasing_original_row')
        for neighbor in (row.index-1, row.index+1):
            if ((marks.video_id == row.video_id) & (marks['index'] == neighbor)).any():
                add(row.video_id, neighbor, 'original_neighbor_of_nonincreasing_row')
    for row in marks[marks.observed_duration_check.eq('at_or_after_reported_video_end')].itertuples():
        add(row.video_id, row.index, 'at_or_after_measured_source_end')
    for row in marks[marks.source_start_mark].itertuples():
        add(row.video_id, row.index, 'source_start_zero_mark')
    for row in old_rows.itertuples():
        add(row.video_id, row.annotation_index, 'historical_dense_control')

    # Reviewed from all14verified local clips; these are coarse observations, not GT.
    categories = ['credits_then_fade', 'intro_to_presenter', 'presenter_to_outro',
                  'instructional_slide_with_delayed_effect', 'instructional_slide_with_delayed_effect',
                  'instructional_slide_to_end_card', 'instructional_slide_change',
                  'instructional_slide_change', 'instructional_slide_to_summary',
                  'source_end_context_no_new_slide', 'instructional_slide_change',
                  'instructional_slide_to_end_card', 'content_to_blank_unresolved',
                  'source_start_context']
    history = {}
    for position, row in enumerate(old_rows.itertuples(), 1):
        key = (row.video_id, int(row.annotation_index))
        mark = marks[(marks.video_id == row.video_id) & (marks['index'] == row.annotation_index)].iloc[0]
        clip = HISTORY/f'clip-{position:02d}.mp4'
        state = states[row.video_id]
        assert row.source_sha256 == state['sha256']
        assert abs(mark.time_s-row.annotation_s) < 1e-8
        assert digest(clip) == row.clip_sha256 == old_artifacts[row.clip_path]['sha256']
        frames = old_frames[(old_frames.video_id == row.video_id) &
                            (old_frames.annotation_index == row.annotation_index)]
        assert len(frames) == row.frame_count
        assert frames.source_sha256.eq(row.source_sha256).all()
        assert frames.source_elapsed_s.is_monotonic_increasing
        history[key] = dict(event_observation=categories[position-1],
            source_sha256=row.source_sha256, annotation_s=float(row.annotation_s),
            clip_local_path=str(clip.relative_to(ROOT)).replace('\\','/'),
            clip_drive_relative_path='analysis/'+row.clip_path,
            clip_sha256=row.clip_sha256, frame_ledger_sha256=digest(HISTORY/'table-28-134.csv'),
            old_receipt_sha256=digest(HISTORY/'receipt.json'),
            contact_sheet=str((ROOT/'benchmark/experiments/outputs/mlpdataset_targeted_review_261019'/
                               f'historical-window-{position:02d}.jpg').relative_to(ROOT)).replace('\\','/'),
            measured_window=dict(effective_start_s=float(row.effective_start_s),
                                 effective_end_s=float(row.effective_end_s)),
            reviewer='Codex visual diagnostic review', reviewed_date='2026-10-19',
            timing_status='coarse_only_no_native_endpoint_certification',
            gt_disposition='hold', reviewed_point_s=None)
    cases = []
    for (vid, index), why in sorted(reasons.items()):
        mark = marks[(marks.video_id == vid) & (marks['index'] == index)].iloc[0]
        state = states[vid]
        annotation = videos.loc[vid].annotation_sha256
        edge = 'at_or_after_measured_source_end' in why or 'source_start_zero_mark' in why
        historical = history.get((vid, index))
        # Historical±5s already reviewed; edge rows need native/policy resolution, not repeated coarse extraction.
        action = ('historical_coarse_review_available' if historical else
                  'source_edge_policy_hold' if edge else 'needs_dense_context')
        cases.append(dict(video_id=vid, annotation_index=index, annotation_s=float(mark.time_s),
            source_sha256=state['sha256'], source_relative_path=f"videos/{vid}/{state['file_name']}",
            duration_s=float(state['probe']['duration_s']), group=str(mark.speaker),
            annotation_sha256=str(annotation), original_source_line=int(mark.source_line),
            reasons=sorted(why), review_action=action,
            requires_new_dense_context=action == 'needs_dense_context',
            semantic_review_status='pending_native_endpoint_or_policy', gt_disposition='hold',
            historical_evidence=historical))
    export_map = {a['path']: a for a in receipt['artifacts']}
    bound_names = ['boundary-ledger.csv', 'video-ledger.csv', 'full-release-mark-coverage.csv',
                   'full-release-video-coverage.csv']
    queue = dict(schema_version=1, queue_id='mlpdataset-targeted-review-v1',
        created='2026-10-19', selection='observations_plus_all_structural_edges_and_original_neighbors',
        hardcoded_sample_cap=None, inventory=dict(videos=333, marks=9021, excluded_inventory_rows=0),
        input_notebook_sha256=digest(NOTEBOOK),
        legacy_archive_sha256=receipt['legacy_archive_sha256'],
        updated_release=receipt['updated_release'],
        drive_run_name='mlpdataset-eda-261017-v3',
        required_drive_exports=[dict(relative_path='analysis/'+name, **export_map[name]) for name in bound_names],
        protocol_id='mlpdataset-slide-transition-protocol-v1',
        annotation_repairs_applied=0, semantic_certified_events=0,
        evaluation_ready=False, cases=cases,
        summary=dict(selected_marks=len(cases), videos=len({c['video_id'] for c in cases}),
                     groups=len({c['group'] for c in cases}),
                     historical_verified_clips=len(history),
                     new_dense_contexts=sum(c['requires_new_dense_context'] for c in cases),
                     policy_only_edges=sum(c['review_action']=='source_edge_policy_hold' for c in cases)))
    assert len(marks) == 9021 and len(videos) == 333
    path = REGISTRY/'mlpdataset-targeted-review-queue-v1.json'
    path.write_text(json.dumps(queue, indent=2, allow_nan=False), encoding='utf8')
    print(json.dumps(queue['summary']))
    return queue


if __name__ == '__main__':
    build_queue()
