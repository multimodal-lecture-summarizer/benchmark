"""
Unit Tests for Evidence Retrieval and Question Answering Pipelines (Q0 - Q3) and Metrics.
"""

import pytest

from benchmarks.models.retrieval_qa import (
    QAConfig,
    Q0_FlatRetrievalQA,
    Q1_OracleHierarchyRetrievalQA,
    Q2_PredictedHierarchyRetrievalQA,
    Q3_MultimodalHierarchyRetrievalQA,
)


@pytest.fixture
def sample_qa_context():
    sentences = [
        "Welcome to this lecture on deep residual learning.",
        "Deeper neural networks often suffer from vanishing gradients.",
        "ResNet introduces identity shortcut connections to solve this degradation problem.",
        "The residual mapping F(x) is added directly to input x via skip connection.",
        "Experiments on ImageNet show ResNet-152 achieves state-of-the-art accuracy.",
        "In conclusion residual connections enable training of networks with over 1000 layers."
    ]
    question = "How does ResNet solve the gradient degradation problem?"
    ground_truth_answer = "ResNet introduces identity shortcut connections to solve the degradation problem."
    return {
        "sentences": sentences,
        "question": question,
        "gt_answer": ground_truth_answer,
        "ocr_slides": ["Introduction & Outline", "Vanishing Gradient Problem", "Residual Learning Framework", "ImageNet Benchmark Results"]
    }


def test_qa_budget_enforcement():
    valid_cfg = QAConfig(variant_id="Q2_valid", top_k=3, max_context_tokens=1024)
    q2 = Q2_PredictedHierarchyRetrievalQA(valid_cfg)
    assert q2.config.top_k == 3

    with pytest.raises(AssertionError):
        invalid_cfg = QAConfig(variant_id="Q2_invalid", top_k=10)
        Q2_PredictedHierarchyRetrievalQA(invalid_cfg)


def test_q0_flat_retrieval(sample_qa_context):
    cfg = QAConfig(variant_id="Q0")
    qa = Q0_FlatRetrievalQA(cfg)
    res = qa.answer_question(sample_qa_context["question"], sample_qa_context["sentences"])

    assert res.variant_id == "Q0_flat"
    assert len(res.retrieved_chunk_ids) <= 3
    assert res.predicted_timestamp_range is not None
    assert len(res.predicted_answer) > 0


def test_q1_oracle_retrieval(sample_qa_context):
    cfg = QAConfig(variant_id="Q1")
    qa = Q1_OracleHierarchyRetrievalQA(cfg)
    oracle_chapters = [
        {"title": "Intro", "sentences": sample_qa_context["sentences"][:2], "start_sec": 0.0, "end_sec": 120.0},
        {"title": "ResNet Formulation", "sentences": sample_qa_context["sentences"][2:4], "start_sec": 120.0, "end_sec": 240.0},
        {"title": "Results", "sentences": sample_qa_context["sentences"][4:], "start_sec": 240.0, "end_sec": 360.0},
    ]
    res = qa.answer_question(sample_qa_context["question"], oracle_chapters)

    assert res.variant_id == "Q1_oracle_hierarchy"
    assert len(res.retrieved_chunk_ids) <= 3
    assert res.predicted_timestamp_range == (120.0, 240.0)


def test_q2_predicted_hierarchy_retrieval(sample_qa_context):
    cfg = QAConfig(variant_id="Q2")
    qa = Q2_PredictedHierarchyRetrievalQA(cfg)
    boundaries = [120.0, 240.0]
    res = qa.answer_question(
        sample_qa_context["question"],
        sample_qa_context["sentences"],
        boundaries
    )

    assert res.variant_id == "Q2_predicted_hierarchy"
    assert len(res.retrieved_chunk_ids) <= 3
    assert res.predicted_timestamp_range is not None


def test_q3_multimodal_hierarchy_retrieval(sample_qa_context):
    cfg = QAConfig(variant_id="Q3")
    qa = Q3_MultimodalHierarchyRetrievalQA(cfg)
    boundaries = [120.0, 240.0]
    res = qa.answer_question(
        sample_qa_context["question"],
        sample_qa_context["sentences"],
        boundaries,
        ocr_slides=sample_qa_context["ocr_slides"]
    )

    assert res.variant_id == "Q3_multimodal_hierarchy"
    assert "Grounding:" in res.predicted_answer

