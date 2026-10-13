"""Offline recovery contracts; fixture scores are never benchmark evidence."""
import copy
import json

import pytest

from experiments.scripts import rq2_tib_rescore_runtime as recovery
from experiments.scripts.rq2_tib_frozen_analysis import seal, verify
from experiments.scripts import rq2_tib_frozen_runtime as frozen
from test_rq2_tib_frozen_runtime import data, offline, Backend


class Scorer:
    device = 'cpu'
    calls = 0

    @property
    def metadata(self):
        from experiments.scripts.rq2_tib_semantic_v2 import SemanticScorerV2
        return SemanticScorerV2(device=self.device).metadata

    def score_pair(self, arms, reference, source):
        self.calls += 1
        return {name: {'S1': .1, 'S3': .2, 'S3_minus_S1': .1}
                for name in ('bertscore', 'sbertscore')}


@pytest.fixture
def origin(data, offline, tmp_path):
    path = tmp_path / 'origin'
    frozen.run_frozen(Backend(), *data, path)
    return path


def test_all120_recomputed_original_immutable_and_resources_preserved(data, origin, tmp_path):
    before = {p.name: p.read_bytes() for p in origin.iterdir()}
    source = json.loads((origin / 'frozen-receipt.json').read_text())
    # Simulate retained semantic results from the old implementation.
    source['rows'][0]['semantic_scores'] = {'obsolete': True}
    source = seal(source)
    (origin / 'frozen-receipt.json').write_text(json.dumps(source), encoding='utf-8')
    before['frozen-receipt.json'] = (origin / 'frozen-receipt.json').read_bytes()
    scorer = Scorer()
    receipt = recovery.run_rescore(origin, data[0], scorer, tmp_path / 'rescore', device='cpu')
    assert scorer.calls == 120
    assert receipt['counts']['completed'] == 120
    assert receipt['origin'] == source
    assert receipt['rows'][0]['semantic_scores']['bertscore']['S1'] == .1
    assert {p.name: p.read_bytes() for p in origin.iterdir()} == before
    summary = recovery.summarize_rescore(receipt)
    assert summary['metrics']['bertscore']['overall']['paired_scored'] == 120
    assert summary['metrics']['rouge_l']['overall']['paired_scored'] == 120
    old_summary = frozen.summarize_frozen(source, data[1], data[2])
    assert summary['resources_by_arm'] == old_summary['resources_by_arm']
    assert summary['dispatch_usage'] == old_summary['dispatch_usage']
    assert summary['rescore_cost']['attempts'] == 120


def test_failure_continues_resume_skips_and_explicit_retry(data, origin, tmp_path):
    class Failing(Scorer):
        def score_pair(self, *args):
            if self.calls == 0:
                self.calls += 1
                raise ValueError('offline scoring failure')
            return super().score_pair(*args)
    output = tmp_path / 'rescore'
    first = recovery.run_rescore(origin, data[0], Failing(), output, device='cpu')
    assert first['counts']['completed'] == 119
    assert first['rows'][0]['status'] == 'evaluation_failed'
    resumed = Scorer()
    recovery.run_rescore(origin, data[0], resumed, output, device='cpu')
    assert resumed.calls == 0
    last = recovery.run_rescore(origin, data[0], resumed, output, device='cpu', retry_failed=True)
    assert resumed.calls == 1
    assert last['counts']['completed'] == 120
    assert [a['status'] for a in last['rows'][0]['attempts']] == ['evaluation_failed', 'completed']


def test_interrupt_resume_retains_attempt(data, origin, tmp_path):
    class Interrupt(Scorer):
        def score_pair(self, *args):
            raise KeyboardInterrupt('offline interruption')
    output = tmp_path / 'rescore'
    first = recovery.run_rescore(origin, data[0], Interrupt(), output, device='cpu')
    assert first['counts']['interrupted'] == 1
    assert first['counts']['not_attempted'] == 119
    assert not (output / '.rescore.lock').exists()
    scorer = Scorer()
    last = recovery.run_rescore(origin, data[0], scorer, output, device='cpu')
    assert scorer.calls == 120
    assert [a['status'] for a in last['rows'][0]['attempts']] == ['interrupted', 'completed']


def test_unknown_process_interruption_is_not_zero_duration(data, origin, tmp_path):
    class ProcessLoss(BaseException):
        pass
    class Crash(Scorer):
        def score_pair(self, *args):
            raise ProcessLoss()
    output = tmp_path / 'rescore'
    with pytest.raises(ProcessLoss):
        recovery.run_rescore(origin, data[0], Crash(), output, device='cpu')
    last = recovery.run_rescore(origin, data[0], Scorer(), output, device='cpu')
    assert last['rows'][0]['attempts'][0]['seconds'] is None
    assert last['rows'][0]['attempts'][0]['status'] == 'interrupted'
    assert recovery.summarize_rescore(last)['rescore_cost']['unknown_duration_attempts'] == 1


def test_origin_hash_dispatch_summary_and_source_validation(data, origin):
    path = origin / 'frozen-receipt.json'
    original = json.loads(path.read_text())
    for key, value in (('generation_source_sha256', 'wrong'), ('scores', {})):
        changed = copy.deepcopy(original)
        changed['rows'][0][key] = value
        path.write_text(json.dumps(seal(changed)), encoding='utf-8')
        with pytest.raises(ValueError):
            recovery.validate_origin(origin, data[0])
    path.write_text(json.dumps(original), encoding='utf-8')
    (origin / 'dispatches.jsonl').write_text('{}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='ledger'):
        recovery.validate_origin(origin, data[0])


def test_resume_identity_seal_and_lock_rejection(data, origin, tmp_path):
    output = tmp_path / 'rescore'
    receipt = recovery.run_rescore(origin, data[0], Scorer(), output, device='cpu')
    scorer = Scorer()
    scorer.device = 'cuda'
    with pytest.raises(ValueError, match='identity changed'):
        recovery.run_rescore(origin, data[0], scorer, output, device='cuda')
    receipt['rows'][0]['semantic_scores']['bertscore']['S1'] = .9
    (output / 'rescore-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    with pytest.raises(ValueError, match='checksum'):
        recovery.run_rescore(origin, data[0], Scorer(), output, device='cpu')
    (output / '.rescore.lock').write_text('active', encoding='utf-8')
    with pytest.raises(FileExistsError):
        recovery.run_rescore(origin, data[0], Scorer(), output, device='cpu')


def test_reject_origin_output_and_wrong_scorer(data, origin, tmp_path):
    with pytest.raises(ValueError, match='separate'):
        recovery.run_rescore(origin, data[0], Scorer(), origin, device='cpu')
    class OldScorer(Scorer):
        metadata = {'version': 'tib_semantic_v1', 'test_adapters': False}
    with pytest.raises(ValueError, match='Amended'):
        recovery.run_rescore(origin, data[0], OldScorer(), tmp_path / 'rescore', device='cpu')
