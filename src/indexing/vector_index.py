"""Build, save, load, and search a ChromaDB vector index."""

from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from src.common.config import Config
from src.common.schemas import Chunk, RetrievalResult


COLLECTION_NAME = "cybersecurity_chunks"


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str) -> SentenceTransformer:
    """Load the embedding model and reuse it when possible."""
    return SentenceTransformer(model_name)


def build_vector_index(
    chunks: list[Chunk],
    persist_directory: str | Path | None = None,
) -> chromadb.Collection:
    """Create a persistent vector index from document chunks."""

    if not chunks:
        raise ValueError("Cannot build a vector index with no chunks.")

    directory = (
        Path(persist_directory)
        if persist_directory is not None
        else Config.VECTOR_INDEX_DIR
    )

    directory.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(directory))

    # Rebuild this collection from the supplied chunks.
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception as exc:
        # Only continue if the collection does not exist.
        if "does not exist" not in str(exc).lower():
            raise

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    model = get_embedding_model(Config.EMBEDDING_MODEL)

    # Process chunks in batches to limit memory usage.
    batch_size = 64

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]

        texts = [chunk.text for chunk in batch]

        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "source": chunk.source,
                    "section": chunk.section,
                    "date": chunk.date or "",
                    "position": chunk.position,
                }
                for chunk in batch
            ],
        )

    return collection


def load_vector_index(
    persist_directory: str | Path | None = None,
) -> chromadb.Collection:
    """Load an existing persistent vector index."""

    directory = (
        Path(persist_directory)
        if persist_directory is not None
        else Config.VECTOR_INDEX_DIR
    )

    if not directory.exists():
        raise FileNotFoundError(
            f"Vector index directory not found: {directory}"
        )

    client = chromadb.PersistentClient(path=str(directory))

    return client.get_collection(name=COLLECTION_NAME)


def search_vector(
    query: str,
    collection: chromadb.Collection,
    k: int = 5,
) -> list[RetrievalResult]:
    """Return the top-k chunks matching a query semantically."""

    if k <= 0:
        raise ValueError("k must be greater than zero.")

    if not query.strip():
        return []

    model = get_embedding_model(Config.EMBEDDING_MODEL)

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for chunk_id, text, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        chunk = Chunk(
            chunk_id=chunk_id,
            doc_id=metadata["doc_id"],
            title=metadata["title"],
            source=metadata["source"],
            section=metadata["section"],
            date=metadata["date"] or None,
            position=metadata["position"],
            text=text,
        )

        # Chroma returns cosine distance; higher similarity is better.
        score = 1.0 - float(distance)

        retrieved.append(
            RetrievalResult(chunk=chunk, score=score)
        )

    return retrieved