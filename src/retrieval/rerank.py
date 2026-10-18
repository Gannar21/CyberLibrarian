from __future__ import annotations

from functools import lru_cache

from .backend import chunk_text

MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(MODEL)


def rerank(query: str, chunks: list, top_n: int) -> list[tuple[object, float]]:
    """Score (query, chunk) pairs with a cross-encoder; return top_n [(chunk, score)]."""
    if not chunks:
        return []
    scores = _model().predict([(query, chunk_text(c)[:2000]) for c in chunks])
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [(c, float(s)) for c, s in ranked[:top_n]]
