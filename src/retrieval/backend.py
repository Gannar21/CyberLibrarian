"""Adapter between retrieval and Person 2's indexes (src/indexing/bm25_index.py, vector_index.py)."""
from __future__ import annotations

import re
from functools import lru_cache


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def chunk_id_of(chunk) -> str:
    return str(get(chunk, "chunk_id") or get(chunk, "id"))


def chunk_text(chunk) -> str:
    return get(chunk, "text") or get(chunk, "content") or ""


def chunk_meta(chunk) -> dict:
    meta = dict(get(chunk, "metadata", None) or {})
    for key in ("doc_id", "title", "source", "year", "date", "section", "position"):
        v = get(chunk, key)
        if v is not None:
            meta.setdefault(key, v)
    return meta


@lru_cache(maxsize=1)
def _bm25_index():
    from src.indexing.bm25_index import load_bm25_index
    return load_bm25_index()


@lru_cache(maxsize=1)
def _collection():
    from src.indexing.vector_index import load_vector_index
    return load_vector_index()


@lru_cache(maxsize=1)
def all_chunks() -> dict:
    return {c.chunk_id: c for c in _bm25_index()["chunks"]}


def bm25_search(query: str, n: int) -> list[tuple[str, float]]:
    from src.indexing.bm25_index import search_bm25
    res = search_bm25(query, _bm25_index(), k=n)
    return [(r.chunk.chunk_id, r.score) for r in res if r.score > 0]


def vector_search(query: str, n: int) -> list[tuple[str, float]]:
    from src.indexing.vector_index import search_vector
    res = search_vector(query, _collection(), k=n)
    return [(r.chunk.chunk_id, r.score) for r in res]
