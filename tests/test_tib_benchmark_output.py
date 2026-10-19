import pytest

from experiments.scripts.tib_benchmark_output import derive_word_cap, select_delivered, sentence_spans


def test_delivery_preserves_complete_sentence_prefix_and_raw_span():
    text = "  Alpha beta. Gamma delta! Epsilon zeta eta.  "
    result = select_delivered(text, 5)
    assert result['text'] == 'Alpha beta. Gamma delta!'
    assert result['delivered_words'] == 4 and result['capped']
    assert not result['forced_word_boundary']
    assert text[slice(*result['raw_character_span'])] == result['text']
    assert result['raw_sha256'] != result['delivered_sha256']


def test_long_runon_fallback_is_explicit_and_does_not_append_content():
    result = select_delivered('one two three four five', 3)
    assert result['text'] == 'one two three'
    assert result['forced_word_boundary'] and result['delivered_words'] == 3


def test_exact_cap_short_and_newline_boundaries():
    assert select_delivered('one two.\nThree four.', 4)['capped'] is False
    text = '  One!  Two?\nThree. '
    assert [text[a:b] for a,b in sentence_spans(text)] == ['One!','Two?','Three.']
    assert select_delivered(text, 2)['text'] == 'One!  Two?'


@pytest.mark.parametrize('value', ['', '  \n\t'])
def test_empty_output_is_failure_not_zero_quality(value):
    with pytest.raises(ValueError, match='Empty'):
        select_delivered(value, 350)


@pytest.mark.parametrize('cap', [0, -1, True, 2.5])
def test_invalid_caps_fail_closed(cap):
    with pytest.raises(ValueError):
        select_delivered('Text.', cap)


def test_train_only_nearest_rank_derivation_and_rounding():
    result = derive_word_cap(list(range(1,101)))
    assert result['percentile_words'] == 95 and result['word_cap'] == 100
    assert derive_word_cap([346]*100)['word_cap'] == 350
    with pytest.raises(ValueError):
        derive_word_cap([1,0])
