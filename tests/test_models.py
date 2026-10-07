"""
Unit Tests for Multimodal Chaptering Models (C1 - C6) and Extractors.
"""

import pytest
import torch
from dataclasses import replace

from benchmarks.models.chaptering import (
    ChapteringBatch,
    ChapteringOutput,
    C1_TextOnlyChapterer,
    C2_AcousticChapterer,
    C3_VisualChapterer,
    C4_OCRChapterer,
    C5_TemporalCrossAttentionTransformer,
    C6_LateFusionChapterer,
)


@pytest.fixture
def sample_batch():
    """Create a synthetic multimodal chaptering batch for testing."""
    B, T = 2, 20
    timestamps = torch.linspace(0, 600, steps=T).unsqueeze(0).repeat(B, 1) # [B, T]
    text_feat = torch.randn(B, T, 384)
    vis_feat = torch.randn(B, T, 384)
    ocr_feat = torch.randn(B, T, 384)
    ac_feat = torch.randn(B, T, 64)
    mask = torch.ones(B, T, dtype=torch.bool)
    mask[0, 18:] = False # Simulate variable length
    targets = torch.zeros(B, T)
    targets[0, 5] = 1.0
    targets[0, 12] = 1.0
    targets[1, 8] = 1.0

    return ChapteringBatch(
        timestamps=timestamps,
        text_features=text_feat,
        visual_features=vis_feat,
        ocr_features=ocr_feat,
        acoustic_features=ac_feat,
        mask=mask,
        targets=targets
    )


def test_c1_text_only_forward_and_loss(sample_batch):
    model = C1_TextOnlyChapterer(d_text=384, d_hidden=256, n_layers=2)
    out = model(sample_batch)

    assert isinstance(out, ChapteringOutput)
    assert out.logits.shape == (2, 20)
    assert out.probabilities.shape == (2, 20)
    assert out.loss is not None
    assert not torch.isnan(out.loss)
    assert out.loss.item() > 0.0
    assert len(out.predicted_boundaries) == 2

    # Verify backward gradient
    out.loss.backward()
    assert model.proj.weight.grad is not None


def test_c2_acoustic_forward(sample_batch):
    model = C2_AcousticChapterer(d_ac=64, d_hidden=256)
    out = model(sample_batch)
    assert out.logits.shape == (2, 20)
    assert out.loss is not None


def test_c3_visual_forward(sample_batch):
    model = C3_VisualChapterer(d_vis=384, d_hidden=256)
    out = model(sample_batch)
    assert out.logits.shape == (2, 20)
    assert out.loss is not None


def test_c4_ocr_forward(sample_batch):
    model = C4_OCRChapterer(d_ocr=384, d_hidden=256)
    out = model(sample_batch)
    assert out.logits.shape == (2, 20)
    assert out.loss is not None


@pytest.mark.parametrize(
    ("model_factory", "modality_field", "modality_dim"),
    [
        (lambda: C2_AcousticChapterer(d_ac=64), "acoustic_features", 64),
        (lambda: C3_VisualChapterer(d_vis=384), "visual_features", 384),
        (lambda: C4_OCRChapterer(d_ocr=384), "ocr_features", 384),
    ],
)
def test_rq1_added_modality_models_require_and_use_text(
    sample_batch, model_factory, modality_field, modality_dim
):
    model = model_factory().eval()
    assert model.proj.in_features == 384 + modality_dim
    assert len(model.transformer.layers) == 2
    with pytest.raises(ValueError, match="text_features"):
        model(replace(sample_batch, text_features=None))
    with pytest.raises(ValueError, match=modality_field):
        model(replace(sample_batch, **{modality_field: None}))
    with torch.no_grad():
        original = model(sample_batch).logits
        no_text = model(replace(sample_batch, text_features=torch.zeros_like(sample_batch.text_features))).logits
    assert not torch.allclose(original, no_text)


def test_c5_proposed_cross_attention_transformer(sample_batch):
    model = C5_TemporalCrossAttentionTransformer(
        d_text=384,
        d_vis=384,
        d_ocr=384,
        d_ac=64,
        d_model=256,
        n_layers=4,
        n_heads=8,
        num_boundary_tokens=3
    )
    out = model(sample_batch, threshold=0.4)

    assert isinstance(out, ChapteringOutput)
    assert out.logits.shape == (2, 20)
    assert out.probabilities.shape == (2, 20)
    assert out.loss is not None
    assert not torch.isnan(out.loss)
    assert len(out.predicted_boundaries) == 2

    # Backward gradient check
    out.loss.backward()
    assert model.boundary_tokens.grad is not None
    assert model.proj_text.weight.grad is not None
    assert model.proj_vis.weight.grad is not None


def test_c6_late_fusion_forward_and_loss(sample_batch):
    model = C6_LateFusionChapterer(
        d_text=384,
        d_vis=384,
        d_ocr=384,
        d_ac=64,
        d_hidden=256
    )
    out = model(sample_batch)
    assert out.logits.shape == (2, 20)
    assert out.loss is not None
    out.loss.backward()
    assert model.fusion_proj.weight.grad is not None
    assert len(model.multimodal_encoder.layers) == 4
    assert model.boundary_tokens.grad is not None
    assert not hasattr(model, "cross_attn")


@pytest.mark.parametrize("model_factory", [
    lambda: C2_AcousticChapterer(d_ac=64),
    lambda: C3_VisualChapterer(d_vis=384),
    lambda: C4_OCRChapterer(d_ocr=384),
])
def test_rq1_single_modality_models_backward(sample_batch, model_factory):
    model = model_factory()
    output = model(sample_batch)
    assert torch.isfinite(output.loss)
    output.loss.backward()
    assert model.proj.weight.grad is not None
    assert model.transformer.layers[0].self_attn.in_proj_weight.grad is not None
