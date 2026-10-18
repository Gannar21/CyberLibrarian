"""Combine BM25 and vector search using Reciprocal Rank Fusion."""

from src.common.schemas import RetrievalResult
from src.indexing.bm25_index import search_bm25
from src.indexing.vector_index import search_vector


def hybrid_search(
    query: str,
    bm25_index: dict,
    vector_index,
    k: int = 5,
    candidate_k: int = 10,
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    """Combine keyword and semantic rankings using RRF."""

    if k <= 0:
        raise ValueError("k must be greater than zero.")

    if candidate_k <= 0:
        raise ValueError("candidate_k must be greater than zero.")

    if rrf_k <= 0:
        raise ValueError("rrf_k must be greater than zero.")

    if not query.strip():
        return []

    # Retrieve candidates independently from both indexes.
    bm25_results = search_bm25(
        query,
        bm25_index,
        k=candidate_k,
    )

    vector_results = search_vector(
        query,
        vector_index,
        k=candidate_k,
    )

    # Store each chunk and its combined ranking score.
    fused = {}

    def add_ranked_results(results):
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk.chunk_id

            if chunk_id not in fused:
                fused[chunk_id] = {
                    "chunk": result.chunk,
                    "score": 0.0,
                }

            # Reciprocal Rank Fusion:
            # contribution = 1 / (rrf_k + rank)
            fused[chunk_id]["score"] += 1.0 / (rrf_k + rank)

    add_ranked_results(bm25_results)
    add_ranked_results(vector_results)

    # Sort by combined score, highest first.
    ranked = sorted(
        fused.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    return [
        RetrievalResult(
            chunk=item["chunk"],
            score=item["score"],
        )
        for item in ranked[:k]
    ]