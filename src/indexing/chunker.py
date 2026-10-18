"""
Owner: Person 2 (Indexing)

This module must provide a function that splits a Document into a list of
Chunks with configurable size and overlap.  Chunk IDs must be stable and
deterministic so that eval files produced on one machine validate on another.

Relevant signatures (from src.common.schemas):
    class Document(BaseModel):
        doc_id: str
        title: str
        source: str
        section: str
        date: str | None
        url: str
        text: str

    class Chunk(BaseModel):
        chunk_id: str
        doc_id: str
        title: str
        source: str
        section: str
        date: str | None
        position: int   # 0-based index within the parent document
        text: str

Required public interface:
    def chunk_document(
        doc: Document,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[Chunk]: ...
"""
raise NotImplementedError("chunker.py must be implemented by Person 2")
