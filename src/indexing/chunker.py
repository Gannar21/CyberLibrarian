
from src.common.config import Config
from src.common.schemas import Document, Chunk


def chunk_document(
    doc: Document,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split one document into overlapping word-based chunks."""

    size = Config.CHUNK_SIZE if chunk_size is None else chunk_size
    overlap = (
        Config.CHUNK_OVERLAP
        if chunk_overlap is None
        else chunk_overlap
    )

    if size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0 or overlap >= size:
        raise ValueError(
            "chunk_overlap must be between 0 and chunk_size - 1"
        )

    words = doc.text.split()

    if not words:
        return []

    chunks = []
    start = 0
    position = 0
    step = size - overlap

    while start < len(words):
        end = min(start + size, len(words))

        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}-chunk-{position}",
                doc_id=doc.doc_id,
                title=doc.title,
                source=doc.source,
                section=doc.section,
                date=doc.date,
                position=position,
                text=" ".join(words[start:end]),
            )
        )

        if end == len(words):
            break

        start += step
        position += 1

    return chunks