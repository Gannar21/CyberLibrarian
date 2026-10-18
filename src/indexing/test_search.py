"""Test BM25, vector, hybrid search, and reranking."""

from src.indexing.bm25_index import load_bm25_index
from src.indexing.vector_index import load_vector_index
from src.indexing.hybrid_search import hybrid_search
from src.indexing.reranker import rerank_results


def main():
    query = "How do attackers use scheduled tasks to maintain persistence?"

    bm25_index = load_bm25_index()
    vector_index = load_vector_index()

    print("\n========== HYBRID SEARCH ==========")

    results = hybrid_search(
        query=query,
        bm25_index=bm25_index,
        vector_index=vector_index,
        k=10,
        candidate_k=10,
    )

    for result in results:
        print(f"{result.chunk.title} | RRF Score: {result.score:.6f}")

    print("\n========== RERANKED RESULTS ==========")

    reranked_results = rerank_results(
        query=query,
        results=results,
        k=5,
    )

    for result in reranked_results:
        print(f"\nTitle: {result.chunk.title}")
        print(f"Source: {result.chunk.source}")
        print(f"Chunk ID: {result.chunk.chunk_id}")
        print(f"Reranker Score: {result.score:.4f}")
        print(f"Text: {result.chunk.text[:300]}")


if __name__ == "__main__":
    main()