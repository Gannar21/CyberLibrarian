import pytest
import numpy as np
from src.common.schemas import Chunk
from src.indexing.vector_index import (
    build_vector_index,
    search_vector,
)


class FakeEmbeddingModel:
    """Small fake model for testing without downloading a real model."""

    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            return np.array([1.0, 0.0, 0.0])

        return np.array(
            [[1.0, 0.0, 0.0] for _ in texts]
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


def test_vector_search_returns_results(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.indexing.vector_index.get_embedding_model",
        lambda model_name: FakeEmbeddingModel(),
    )

    chunks = [
        make_chunk("chunk-1", "SQL injection prevention"),
        make_chunk("chunk-2", "Password security"),
    ]

    collection = build_vector_index(
        chunks,
        persist_directory=tmp_path / "chroma",
    )

    results = search_vector(
        "How can SQL injection be prevented?",
        collection,
        k=2,
    )

    assert len(results) == 2
    assert all(result.chunk.chunk_id for result in results)
    assert all(isinstance(result.score, float) for result in results)


def test_vector_search_returns_empty_for_blank_query(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.indexing.vector_index.get_embedding_model",
        lambda model_name: FakeEmbeddingModel(),
    )

    chunks = [
        make_chunk("chunk-1", "SQL injection prevention"),
    ]

    collection = build_vector_index(
        chunks,
        persist_directory=tmp_path / "chroma",
    )

    assert search_vector("   ", collection) == []


def test_vector_search_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        search_vector("SQL injection", None, k=0)


def test_vector_index_rejects_empty_chunks(tmp_path):
    with pytest.raises(ValueError):
        build_vector_index(
            [],
            persist_directory=tmp_path / "chroma",
        )