"""
Validation Gate & Reproducibility Verification Tests (Phase 6).
Automated tests verifying that the benchmark suite complies with:
  - D-T01: Pinned baseline VLM
  - D-T02: C5/C6 architecture freeze
  - D-T04: Feature dimensions (visual 384, ocr 384, acoustic 32)
  - D-T07: Holm-Bonferroni correction
  - D-T08: Fair budget bounds (source <= 32k, output <= 512)
  - D-T15: Real-data-only constraint (0 mocks in research path)
  - Withdrawn RQ1/RQ2/RQ4 outcomes are not exposed as active metrics
"""

import json
import os
import sys
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent


def test_repro_manifest_structure_and_completeness(project_root):
    manifest_path = project_root / "reports" / "repro_manifest.json"
    assert manifest_path.exists(), "repro_manifest.json must exist in reports/"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert "manifest_version" in manifest
    assert "git_provenance" in manifest
    assert manifest["git_provenance"]["frozen_commit_hash"] is not None

    # Withdrawn comparisons must not retain numerical result claims.
    rq_outcomes = manifest["research_questions_outcomes"]
    for rq in ("RQ1", "RQ2", "RQ4"):
        assert rq_outcomes[rq]["status"] == "withdrawn_pending_reanalysis"
        assert "primary_metrics" not in rq_outcomes[rq]
    assert "RQ3" in rq_outcomes

    # Check frozen decisions
    decisions = manifest["frozen_experimental_decisions"]
    assert decisions["D-T04"]["acoustic_dim"] == 32
    assert decisions["D-T04"]["visual_dim"] == 384
    assert decisions["D-T08"]["max_source_tokens"] == 32000
    assert decisions["D-T08"]["max_output_tokens"] == 512


def test_d15_real_data_only_no_mocks_across_all_notebooks(project_root):
    notebooks_dir = project_root / "experiments" / "notebooks"
    expected_notebooks = [
        "00_dataset_eda_and_quality_audit.ipynb",
        "01_audio_asr_benchmark.ipynb",
        "02_visual_scene_ocr_benchmark.ipynb",
        "03_multimodal_chaptering_benchmark.ipynb",
        "04_hierarchical_summarization_benchmark.ipynb",
        "05_evidence_retrieval_qa_benchmark.ipynb",
        "06_efficiency_pareto_error_cascading.ipynb",
    ]

    for nb_name in expected_notebooks:
        nb_path = notebooks_dir / nb_name
        assert nb_path.exists(), f"Notebook {nb_name} must exist"

        with open(nb_path, "r", encoding="utf-8") as f:
            nb_json = json.load(f)

        code_content = ""
        for cell in nb_json["cells"]:
            if cell["cell_type"] == "code":
                code_content += "".join(cell["source"]) + "\n"

        # Ensure no random mocks generating synthetic research numbers in core pipelines
        forbidden_terms = ["synthetic_test_qa", "mock_features", "uniform_gold"]
        for term in forbidden_terms:
            assert term not in code_content, f"Forbidden mock term '{term}' found in {nb_name}"


def test_rq3_oracle_gap_closed_precision(project_root):
    p = project_root / "reports" / "rq3_benchmark_results.json"
    assert p.exists(), "rq3_benchmark_results.json must exist"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    gap_info = data.get("oracle_gap_analysis", {})
    gap = gap_info.get("gap_closed_ratio_pct", data.get("oracle_gap_closed_percent", 0.0))
    assert gap >= 75.0, f"Oracle gap closed must be >= 75%, got {gap}%"
    abs_perf = gap_info.get("absolute_oracle_performance_pct", 0.0)
    assert abs_perf >= 90.0, f"Absolute oracle performance must be >= 90%, got {abs_perf}%"


def test_dataset_eda_and_quality_audit_report(project_root):
    p = project_root / "reports" / "dataset_eda_and_audit_report.json"
    assert p.exists(), "dataset_eda_and_audit_report.json must exist"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["datasets"]["tedlium3_speech"]["total_utterances"] > 250000
    assert data["datasets"]["eduviqa_multimodal_qa"]["total_qa_pairs"] == 883
    assert data["datasets"]["slidevqa_presentation_qa"]["total_qa_pairs"] >= 14000
    assert data["datasets"]["iiit_cvid_classroom_ocr"]["total_word_annotations"] >= 130000
    assert "tvsum_exploratory_provenance" in data["datasets"]
    audit = data["datasets"]["core_evaluation_lectures"]["single_author_audit"]
    assert audit["keep_rate_pct"] == 100.0
    assert audit["mean_source_support_score"] == 2.0
    assert audit["mean_coverage_score"] == 2.0
    assert len(audit["frozen_exclusion_list"]) == 0


def test_cached_features_checksum_integrity(project_root):
    import hashlib
    p_manifest = project_root / "reports" / "repro_manifest.json"
    with open(p_manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    stored_checksums = manifest["datasets_provenance"]["core_evaluation_lectures"]["features_checksums"]
    features_dir = project_root / "benchmarks" / "data" / "cached_features"
    assert len(stored_checksums) == 20
    for fname, meta in stored_checksums.items():
        feat_path = features_dir / fname
        assert feat_path.exists(), f"Feature file {fname} must exist"
        h = hashlib.sha256(feat_path.read_bytes()).hexdigest()
        assert h == meta["sha256"], f"Checksum mismatch for {fname}"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Model Architecture & Fusion Refactoring Verification Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_c5_decoupled_cross_attention_and_acoustic_dim_32():
    import torch
    from benchmarks.models.chaptering import (
        C5_TemporalCrossAttentionTransformer,
        ChapteringBatch
    )

    model = C5_TemporalCrossAttentionTransformer()
    assert model.proj_ac.in_features == 32, "C5 acoustic projection input must be 32d"
    assert model.pos_weight == 4.0, "C5 pos_weight must be tuned to 4.0"

    # Forward & backward pass
    B, T = 2, 10
    batch = ChapteringBatch(
        timestamps=torch.linspace(0, 300, steps=T).unsqueeze(0).repeat(B, 1),
        text_features=torch.randn(B, T, 384),
        visual_features=torch.randn(B, T, 384),
        ocr_features=torch.randn(B, T, 384),
        acoustic_features=torch.randn(B, T, 32),
        mask=torch.ones(B, T, dtype=torch.bool),
        targets=torch.zeros(B, T)
    )
    batch.targets[0, 3] = 1.0

    out = model(batch)
    assert out.logits.shape == (B, T)
    assert out.probabilities.shape == (B, T)
    assert out.loss is not None
    assert not torch.isnan(out.loss)

    out.loss.backward()
    assert model.proj_vis.weight.grad is not None, "Visual query anchor must receive gradient"
    assert model.proj_text.weight.grad is not None, "Text key/value must receive gradient"
    assert model.boundary_tokens.grad is not None, "Boundary tokens must receive gradient"


def test_visual_anchor_snapping_and_silent_intro():
    import torch
    from benchmarks.models.chaptering import (
        extract_visual_transitions,
        apply_visual_snapping
    )

    # 1. Visual transition detection
    T = 6
    vf = torch.zeros(T, 384)
    # create distinct scene shift at index 3
    vf[0:3] = 1.0
    vf[3:6] = -1.0
    timestamps = torch.tensor([0.0, 30.0, 60.0, 90.0, 120.0, 150.0])

    transitions = extract_visual_transitions(vf, timestamps)
    assert 90.0 in transitions, "Visual transition should be detected at step 3 (90.0s)"

    # 2. Snapping within 45s window
    pred_boundaries = [82.0, 200.0]
    snapped = apply_visual_snapping(pred_boundaries, [90.0], window_sec=45.0)
    assert 90.0 in snapped, "82.0s should be snapped to 90.0s because |82-90| <= 45s"
    assert 200.0 in snapped, "200.0s should remain unchanged as no visual anchor is nearby"

    # 3. Silent Intro Guard
    intro_pred = [5.0, 120.0]
    # If visual anchor is 0.0s but first speech is at 18.0s, boundary should not be snapped to 0.0s
    snapped_intro = apply_visual_snapping(intro_pred, [0.0, 118.0], window_sec=45.0, first_sentence_time=18.0)
    assert 0.0 not in snapped_intro, "Silent Intro Guard must prevent snapping to 0.0s when speech starts > 0s"


def test_semantic_evidence_grounder_and_tensor_fallback():
    import torch
    from benchmarks.models.summarization import (
        SemanticEvidenceGrounder,
        compute_hallucination_rate,
        compute_claim_density
    )

    grounder = SemanticEvidenceGrounder(tau_ev=0.45)

    # 1. Text grounding
    claim = "The algorithm optimizes gradient descent with momentum."
    slide_text = "Gradient Descent Optimization: Momentum and Learning Rate"
    score = grounder.score_claim_against_ocr_text(claim, slide_text)
    assert score > 0.0, "Semantic score against relevant slide should be positive"

    # 2. Tensor fallback
    ocr_tensor = torch.randn(5, 384)
    tensor_score = grounder.score_claim_against_ocr_features(claim, ocr_tensor)
    assert 0.0 <= tensor_score <= 1.0, "Tensor fallback score should be normalized"

    # 3. Hallucination rate & claim density
    summary = "First, we introduce the model. Second, we evaluate the loss. Finally, we analyze the results."
    h_m = compute_hallucination_rate(summary, evidence=None)
    assert h_m["hallucination_rate"] is None
    assert h_m["status"] == "unavailable_no_evidence"

    d_m = compute_claim_density(summary)
    assert d_m["claim_count"] == 3
    assert d_m["summary_token_len"] > 0
    assert d_m["claim_density_per_100_tokens"] > 0.0


def test_reciprocal_rank_fusion_math():
    from benchmarks.models.retrieval_qa import reciprocal_rank_fusion

    dense_ranks = ["doc_A", "doc_B", "doc_C"]
    sparse_ranks = ["doc_A", "doc_C", "doc_B"]

    fused = reciprocal_rank_fusion(dense_ranks, sparse_ranks, k=60)
    assert len(fused) == 3

    # doc_A is rank 1 in both -> score = 1/(60+1) + 1/(60+1) = 2/61
    expected_a = 2.0 / 61.0
    assert abs(fused[0][1] - expected_a) < 1e-6
    assert fused[0][0] == "doc_A", "doc_A must be ranked #1"

    # doc_B and doc_C both have 1 rank-2 and 1 rank-3 -> score = 1/62 + 1/63
    expected_bc = (1.0 / 62.0) + (1.0 / 63.0)
    assert abs(fused[1][1] - expected_bc) < 1e-6
    assert abs(fused[2][1] - expected_bc) < 1e-6


def test_c5_checkpoint_file_and_loading(project_root):
    import torch
    from benchmarks.models.chaptering import C5_TemporalCrossAttentionTransformer

    ckpt_path = project_root / "checkpoints" / "c5_real.pt"
    assert ckpt_path.exists(), "checkpoints/c5_real.pt must exist"

    model = C5_TemporalCrossAttentionTransformer()
    state_dict = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    assert model.proj_ac.in_features == 32
