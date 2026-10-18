import pytest

from src.common.schemas import Chunk, RetrievalResult
from src.indexing.reranker import rerank_results


class FakeReranker:
    """Fake cross-encoder for testing without loading a model."""

    def predict(self, pairs):
        # Higher scores indicate greater relevance.
        return [0.2, 0.9, -0.1][:len(pairs)]


def make_result(chunk_id: str) -> RetrievalResult:
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_id="test-doc",
        title=f"Document {chunk_id}",
        source="owasp",
        section="Testing",
        date=None,
        position=0,
        text=f"Test cybersecurity text for {chunk_id}",
    )

    return RetrievalResult(chunk=chunk, score=0.5)


def test_reranker_sorts_by_relevance(monkeypatch):
    monkeypatch.setattr(
        "src.indexing.reranker.get_reranker",
        lambda: FakeReranker(),
    )

    results = [
        make_result("chunk-1"),
        make_result("chunk-2"),
        make_result("chunk-3"),
    ]

    reranked = rerank_results(
        query="test cybersecurity",
        results=results,
        k=3,
    )

    assert len(reranked) == 3
    assert reranked[0].chunk.chunk_id == "chunk-2"
    assert reranked[1].chunk.chunk_id == "chunk-1"
    assert reranked[2].chunk.chunk_id == "chunk-3"

    scores = [result.score for result in reranked]
    assert scores == sorted(scores, reverse=True)


def test_reranker_returns_only_top_k(monkeypatch):
    monkeypatch.setattr(
        "src.indexing.reranker.get_reranker",
        lambda: FakeReranker(),
    )

    results = [
        make_result("chunk-1"),
        make_result("chunk-2"),
        make_result("chunk-3"),
    ]

    reranked = rerank_results(
        query="test cybersecurity",
        results=results,
        k=2,
    )

    assert len(reranked) == 2
    assert reranked[0].chunk.chunk_id == "chunk-2"


def test_reranker_returns_empty_for_blank_query():
    assert rerank_results("   ", [make_result("chunk-1")]) == []


def test_reranker_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        rerank_results(
            query="test",
            results=[make_result("chunk-1")],
            k=0,
        )