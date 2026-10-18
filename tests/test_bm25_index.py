import pytest

from src.common.schemas import Chunk
from src.indexing.bm25_index import (
    save_bm25_index,
    load_bm25_index,
    search_bm25,
)


def make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id="test-doc",
        title=f"Document {chunk_id}",
        source="owasp",
        section="Testing",
        date=None,
        position=0,
        text=text,
    )


def test_bm25_returns_relevant_chunk_first(tmp_path):
    chunks = [
        make_chunk(
            "chunk-1",
            "SQL injection occurs when queries use unsafe input",
        ),
        make_chunk(
            "chunk-2",
            "A password should be stored securely",
        ),
        make_chunk(
            "chunk-3",
            "SQL injection can be prevented with parameterized queries",
        ),
    ]

    index_path = tmp_path / "bm25.pkl"

    save_bm25_index(chunks, index_path)
    index = load_bm25_index(index_path)

    results = search_bm25("SQL injection", index, k=3)

    assert len(results) == 3
    assert results[0].chunk.chunk_id in {"chunk-1", "chunk-3"}


def test_bm25_rejects_empty_chunks():
    with pytest.raises(ValueError):
        save_bm25_index([], "empty_bm25.pkl")


def test_bm25_rejects_nonpositive_k(tmp_path):
    chunks = [
        make_chunk("chunk-1", "Example cybersecurity text"),
    ]

    index_path = tmp_path / "bm25.pkl"
    save_bm25_index(chunks, index_path)
    index = load_bm25_index(index_path)

    with pytest.raises(ValueError):
        search_bm25("cybersecurity", index, k=0)