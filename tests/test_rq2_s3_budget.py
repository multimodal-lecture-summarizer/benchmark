"""Regression checks for the S3 transcript source cap."""

from benchmarks.models.summarization import S3_PredictedHierarchySummarizer, SummarizerConfig


class RecordingEngine:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, max_tokens=512, temperature=0.2):
        self.prompts.append(prompt)
        return "Recorded summary."


def test_s3_chapters_and_prompts_exclude_source_after_budget():
    engine = RecordingEngine()
    summarizer = S3_PredictedHierarchySummarizer(
        SummarizerConfig(variant_id="S3", max_source_tokens=13), llm_engine=engine
    )
    sentences = [
        "alpha one two three",
        "beta four five six",
        "gamma seven EIGHT nine",
        "FORBIDDEN ten eleven twelve",
    ]
    result = summarizer.summarize(sentences, [10.0, 20.0, 30.0], [0.0, 10.0, 20.0, 30.0])

    chapter_sentences = [sentence for chapter in result.hierarchy for sentence in chapter["sentences"]]
    assert chapter_sentences == sentences[:2] + ["gamma seven"]
    assert result.num_chapters == 3
    assert result.token_usage["source_tokens"] == 13
    assert "EIGHT" not in "\n".join(engine.prompts)
    assert "FORBIDDEN" not in "\n".join(engine.prompts)


def test_s3_keeps_original_segments_and_timestamps_within_budget():
    engine = RecordingEngine()
    summarizer = S3_PredictedHierarchySummarizer(
        SummarizerConfig(variant_id="S3", max_source_tokens=100), llm_engine=engine
    )
    sentences = ["First,  sentence intact.", "Second  sentence intact."]
    result = summarizer.summarize(sentences, [10.0], [0.0, 10.0])

    assert [chapter["sentences"] for chapter in result.hierarchy] == [[sentences[0]], [sentences[1]]]
    assert [chapter["timestamp"] for chapter in result.hierarchy] == ["0s", "10s"]
