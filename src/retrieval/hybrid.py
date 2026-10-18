"""
Owner: Person 3 (Retrieval)

This module must fuse the BM25 and vector retrieval results into a single
ranked list.  A common approach is Reciprocal Rank Fusion (RRF).
Optionally apply a cross-encoder reranker to the fused top-n results.

Relevant signatures (from src.common.schemas):
    class RetrievalResult(BaseModel):
        chunk: Chunk
        score: float

Required public interface:
    def hybrid_retrieve(
        query: str,
        k: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievalResult]:
        \"\"\"Fuse BM25 and vector results; return the top-k after reranking.
        Supported filter keys: source (str), year (int).
        \"\"\"
        ...
"""
raise NotImplementedError("hybrid.py must be implemented by Person 3")
