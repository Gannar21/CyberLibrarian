"""retrieve(query, k, filters) -> list[RetrievalResult]  (the contract from schemas.py)."""
from __future__ import annotations

import inspect

from . import backend
from .filters import matches
from .fusion import rrf

MODES = ("keyword", "vector", "hybrid")


def _make_result(chunk, score: float, rank: int, method: str):
    from src.common.schemas import RetrievalResult
    meta = backend.chunk_meta(chunk)
    cand = {
        "chunk": chunk, "score": score, "rank": rank, "chunk_id": backend.chunk_id_of(chunk),
        "text": backend.chunk_text(chunk), "metadata": meta,
        "retriever": method, "method": method, "source": meta.get("source"),
        "title": meta.get("title"), "section": meta.get("section"),
    }
    params = inspect.signature(RetrievalResult).parameters
    kwargs = {k: v for k, v in cand.items() if k in params}
    return RetrievalResult(**kwargs)


def retrieve(query: str, k: int = 5, filters: dict | None = None, mode: str = "hybrid",
             rerank: bool = False, rewrite: bool = False, pool: int = 50, rerank_pool: int = 30):
    """mode: keyword | vector | hybrid. rerank: cross-encoder on top rerank_pool. rewrite: LLM query rewrite."""
    assert mode in MODES, mode
    n = pool * 4 if filters else pool  # over-fetch so filters don't starve results
    chunks = backend.all_chunks()

    queries = [query]
    if rewrite:
        from .rewrite import rewrite_query
        queries = rewrite_query(query)

    ranked_lists = []
    for q in queries:
        if mode in ("keyword", "hybrid"):
            ranked_lists.append([c for c, _ in backend.bm25_search(q, n)])
        if mode in ("vector", "hybrid"):
            ranked_lists.append([c for c, _ in backend.vector_search(q, n)])

    if len(ranked_lists) == 1:
        fused = [(cid, 1.0 / (i + 1)) for i, cid in enumerate(ranked_lists[0])]
    else:
        fused = rrf(ranked_lists)

    fused = [(cid, s) for cid, s in fused if cid in chunks and matches(chunks[cid], filters)]
    method = mode

    if rerank:
        from .rerank import rerank as _rerank
        head = fused[:rerank_pool]
        top = _rerank(query, [chunks[cid] for cid, _ in head], k)
        method += "+rerank"
        return [_make_result(c, s, i + 1, method) for i, (c, s) in enumerate(top)]

    return [_make_result(chunks[cid], s, i + 1, method) for i, (cid, s) in enumerate(fused[:k])]
