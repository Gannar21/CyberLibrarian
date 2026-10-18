import pytest

from src.common.schemas import Chunk, RetrievalResult
from src.indexing.hybrid_search import hybrid_search


def make_result(chunk_id: str, score: float) -> RetrievalResult:
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_id="test-doc",
        title=f"Document {chunk_id}",
        source="owasp",
        section="Testing",
        date=None,
        position=0,
        text=f"Cybersecurity information for {chunk_id}",
    )

    return RetrievalResult(chunk=chunk, score=score)


def test_hybrid_search_combines_rankings(monkeypatch):
    bm25_results = [
        make_result("chunk-1", 5.0),
        make_result("chunk-2", 3.0),
    ]

    vector_results = [
        make_result("chunk-2", 0.9),
        make_result("chunk-3", 0.8),
    ]

    monkeypatch.setattr(
        "src.indexing.hybrid_search.search_bm25",
        lambda query, index, k: bm25_results[:k],
    )

    monkeypatch.setattr(
        "src.indexing.hybrid_search.search_vector",
        lambda query, index, k: vector_results[:k],
    )

    results = hybrid_search(
        query="test cybersecurity",
        bm25_index={},
        vector_index=None,
        k=3,
        candidate_k=3,
    )

    assert len(results) == 3

    # chunk-2 ranks highly in both methods, so RRF should rank it first.
    assert results[0].chunk.chunk_id == "chunk-2"

    # Results should be ordered from highest to lowest fused score.
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_search_returns_empty_for_blank_query():
    results = hybrid_search(
        query="   ",
        bm25_index={},
        vector_index=None,
    )

    assert results == []


def test_hybrid_search_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        hybrid_search(
            query="test",
            bm25_index={},
            vector_index=None,
            k=0,
        )