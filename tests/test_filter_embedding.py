from src.config import KeywordsConfig
from src.fetchers.pubmed import Paper
from src.filter_embedding import EmbeddingPaperFilter


class FakeSentenceTransformer:
    calls = []

    def __init__(self, _model_name: str):
        pass

    def encode(self, inputs, convert_to_tensor=True):
        FakeSentenceTransformer.calls.append(inputs)
        if inputs is None:
            raise ValueError("None is not allowed")
        if isinstance(inputs, list):
            return "topic-embeddings"
        if inputs == "good title":
            return "title-embedding"
        if inputs == "good abstract":
            return "abstract-embedding"
        return "other-embedding"


def fake_cos_sim(embedding, _topic_embeddings):
    if embedding == "title-embedding":
        return [[0.2]]
    if embedding == "abstract-embedding":
        return [[0.9]]
    return [[0.0]]


def test_filter_paper_ignores_none_title(monkeypatch):
    FakeSentenceTransformer.calls = []
    monkeypatch.setattr("src.filter_embedding.SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr("src.filter_embedding.util.cos_sim", fake_cos_sim)

    paper_filter = EmbeddingPaperFilter(
        KeywordsConfig(topics=["topic"], authors=[]),
        similarity_threshold=0.4,
    )
    result = paper_filter.filter_paper(
        Paper(
            pmid="1",
            title=None,
            authors=[],
            abstract="good abstract",
            journal="j",
            pub_date="2026",
        )
    )

    assert result.matched_topics == ["topic"]
    assert None not in FakeSentenceTransformer.calls


def test_filter_paper_handles_missing_text_fields(monkeypatch):
    FakeSentenceTransformer.calls = []
    monkeypatch.setattr("src.filter_embedding.SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr("src.filter_embedding.util.cos_sim", fake_cos_sim)

    paper_filter = EmbeddingPaperFilter(
        KeywordsConfig(topics=["topic"], authors=[]),
        similarity_threshold=0.4,
    )
    result = paper_filter.filter_paper(
        Paper(
            pmid="1",
            title=None,
            authors=[],
            abstract=None,
            journal="j",
            pub_date="2026",
        )
    )

    assert result.matched_topics == []
