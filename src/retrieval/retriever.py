"""retrieve(query, k, filters) -> list[RetrievalResult]  (the contract from schemas.py)."""
from __future__ import annotations

import inspect
import os
import re

from . import backend
from .filters import matches
from .fusion import rrf

MODES = ("keyword", "vector", "hybrid")
PIN_SCORE = 100.0                      # marks pinned results; real scores are far lower
MAX_PINS = 3
_TECH_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.I)
_doc_cache: tuple | None = None


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


def _doc_index(chunks) -> dict[str, list[tuple[int, str]]]:
    """doc slug -> [(chunk position, chunk_id)] sorted by position. Cached."""
    global _doc_cache
    if _doc_cache is None or _doc_cache[0] != len(chunks):
        idx: dict[str, list[tuple[int, str]]] = {}
        for cid in chunks:
            m = re.match(r"(.+)-chunk-(\d+)$", cid)
            if m:
                idx.setdefault(m.group(1), []).append((int(m.group(2)), cid))
        for lst in idx.values():
            lst.sort()
        _doc_cache = (len(chunks), idx)
    return _doc_cache[1]


def _pins(query: str, chunks, filters) -> list[str]:
    """Chunks to force into the results: named MITRE techniques and named OWASP cheat sheets."""
    idx = _doc_index(chunks)
    low = query.lower()
    pins: list[str] = []

    # 1) MITRE technique ids, e.g. T1486 or T1059.001
    for tid in {t.lower() for t in _TECH_RE.findall(query)}:
        for slug, lst in idx.items():
            if slug.lower() == f"mitre-{tid}":
                pins.append(lst[0][1])

    # 2) OWASP cheat sheets named in the question, e.g. "Authentication Cheat Sheet"
    named: dict[str, str] = {}
    for slug in idx:
        if slug.startswith("owasp-") and slug.endswith("-cheat-sheet"):
            phrase = slug[len("owasp-"):].replace("-", " ")
            if phrase in low:
                named[phrase] = slug
    for p in named:
        if any(p != o and p in o for o in named):   # keep only the most specific title
            continue
        pins += [cid for _, cid in idx[named[p]][:2]]

    out: list[str] = []
    for cid in pins:
        if cid not in out and cid in chunks and matches(chunks[cid], filters):
            out.append(cid)
    return out[:MAX_PINS]


def retrieve(query: str, k: int = 5, filters: dict | None = None, mode: str = "hybrid",
             rerank: bool = False, rewrite: bool = False, pool: int = 50, rerank_pool: int = 30):
    """mode: keyword | vector | hybrid. rerank: cross-encoder on top rerank_pool.
    rewrite: LLM query rewrite. Pinning of named documents is on unless PIN_NAMED=false."""
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

    pin_on = os.getenv("PIN_NAMED", "true").lower() not in ("false", "0", "no")
    pins = _pins(query, chunks, filters)[:k] if pin_on else []
    method = mode + ("+pin" if pins else "")
    pinned = [_make_result(chunks[cid], PIN_SCORE, i + 1, method) for i, cid in enumerate(pins)]
    rest = [(cid, s) for cid, s in fused if cid not in pins]
    slots = k - len(pins)

    if rerank:
        from .rerank import rerank as _rerank
        method += "+rerank"
        head = rest[:rerank_pool]
        top = _rerank(query, [chunks[cid] for cid, _ in head], slots) if slots > 0 else []
        return pinned + [_make_result(c, s, len(pins) + i + 1, method) for i, (c, s) in enumerate(top)]

    return pinned + [_make_result(chunks[cid], s, len(pins) + i + 1, method)
                     for i, (cid, s) in enumerate(rest[:max(slots, 0)])]