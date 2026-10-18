"""Build, save, load, and search a BM25 keyword index."""

import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.common.config import Config
from src.common.schemas import Chunk, RetrievalResult


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase tokens."""
    return re.findall(r"\w+", text.lower())


def build_bm25_index(chunks: list[Chunk]) -> BM25Okapi:
    """Build a BM25 index from document chunks."""

    if not chunks:
        raise ValueError("Cannot build a BM25 index with no chunks.")

    tokenized_chunks = [tokenize(chunk.text) for chunk in chunks]

    return BM25Okapi(tokenized_chunks)


def save_bm25_index(
    chunks: list[Chunk],
    index_path: str | Path | None = None,
) -> None:
    """Save the BM25 index and its chunks to disk."""

    path = Path(index_path) if index_path is not None else Config.BM25_INDEX

    path.parent.mkdir(parents=True, exist_ok=True)

    tokenized_chunks = [tokenize(chunk.text) for chunk in chunks]
    bm25 = build_bm25_index(chunks)

    data = {
        "bm25": bm25,
        "chunks": chunks,
        "tokenized_chunks": tokenized_chunks,
    }

    with path.open("wb") as file:
        pickle.dump(data, file)


def load_bm25_index(
    index_path: str | Path | None = None,
) -> dict:
    """Load a previously saved BM25 index."""

    path = Path(index_path) if index_path is not None else Config.BM25_INDEX

    if not path.exists():
        raise FileNotFoundError(
            f"BM25 index not found at {path}. Build the index first."
        )

    with path.open("rb") as file:
        return pickle.load(file)


def search_bm25(
    query: str,
    index: dict,
    k: int = 5,
) -> list[RetrievalResult]:
    """Return the top-k chunks matching a query using BM25."""

    if k <= 0:
        raise ValueError("k must be greater than zero.")

    query_tokens = tokenize(query)

    if not query_tokens:
        return []

    chunks = index["chunks"]
    bm25 = index["bm25"]

    scores = bm25.get_scores(query_tokens)

    ranked_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:k]

    return [
        RetrievalResult(
            chunk=chunks[i],
            score=float(scores[i]),
        )
        for i in ranked_indices
    ]