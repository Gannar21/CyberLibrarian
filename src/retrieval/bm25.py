"""
Owner: Person 3 (Retrieval)

This module must provide BM25 sparse retrieval over the indexed Chunks.
Load the BM25 index via src.indexing.load.load_bm25_index().
Return results in descending score order.

Relevant signatures (from src.common.schemas):
    class Chunk(BaseModel): ...
    class RetrievalResult(BaseModel):
        chunk: Chunk
        score: float

Required public interface:
    def bm25_retrieve(
        query: str,
        k: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievalResult]:
        \"\"\"Return the top-k chunks ranked by BM25 score.
        Supported filter keys: source (str), year (int).
        \"\"\"
        ...
"""
raise NotImplementedError("bm25.py must be implemented by Person 3")
