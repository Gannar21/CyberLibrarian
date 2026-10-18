"""
Owner: Person 3 (Retrieval)

This module must provide dense vector retrieval over the indexed Chunks.
Load the vector index via src.indexing.load.load_vector_index().
Embed the query using the model name from src.common.config.
Return results in descending similarity score order.

Relevant signatures (from src.common.schemas):
    class Chunk(BaseModel): ...
    class RetrievalResult(BaseModel):
        chunk: Chunk
        score: float

Required public interface:
    def vector_retrieve(
        query: str,
        k: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievalResult]:
        \"\"\"Return the top-k chunks ranked by embedding similarity.
        Supported filter keys: source (str), year (int).
        \"\"\"
        ...
"""
raise NotImplementedError("vector.py must be implemented by Person 3")
