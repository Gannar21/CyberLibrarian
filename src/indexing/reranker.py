"""Rerank retrieved chunks using a cross-encoder model."""

from functools import lru_cache

from sentence_transformers import CrossEncoder

from src.common.schemas import RetrievalResult


RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """Load the reranker model once and reuse it."""
    return CrossEncoder(RERANKER_MODEL)


def rerank_results(
    query: str,
    results: list[RetrievalResult],
    k: int = 5,
) -> list[RetrievalResult]:
    """Reorder retrieved chunks by their relevance to the query."""

    if k <= 0:
        raise ValueError("k must be greater than zero.")

    if not query.strip() or not results:
        return []

    reranker = get_reranker()

    pairs = [
        (query, result.chunk.text)
        for result in results
    ]

    scores = reranker.predict(pairs)

    ranked_results = [
        RetrievalResult(
            chunk=result.chunk,
            score=float(score),
        )
        for result, score in zip(results, scores)
    ]

    ranked_results.sort(
        key=lambda result: result.score,
        reverse=True,
    )

    return ranked_results[:k]