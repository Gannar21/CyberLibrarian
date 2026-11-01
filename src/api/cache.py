"""In-memory answer cache: normalised question + filters + config fingerprint -> AnswerResponse.
Single worker only (the cache lives in process memory)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import OrderedDict

ENABLED = os.getenv("ANSWER_CACHE", "true").lower() in ("true", "1", "yes")
TTL_S = int(os.getenv("CACHE_TTL_S", "86400"))
MAX_ITEMS = int(os.getenv("CACHE_MAX", "500"))

_lock = threading.Lock()
_store: "OrderedDict[str, tuple[float, object]]" = OrderedDict()
stats = {"hits": 0, "misses": 0}


def _key(question: str, filters: dict | None) -> str:
    q = re.sub(r"\s+", " ", question.strip().lower()).rstrip("?!. ")
    f = json.dumps(filters or {}, sort_keys=True, default=str)
    # changing model/retrieval settings must not serve stale answers
    fp = "|".join(os.getenv(k, "") for k in
                  ("LLM_MODEL", "USE_RERANK", "SKIP_RERANK", "RERANK_TOP_N", "TOP_K"))
    return hashlib.sha256(f"{q}|{f}|{fp}".encode()).hexdigest()


def cached_answer(question: str, filters: dict | None, history: list | None, compute):
    """compute(question, filters=..., history=...) -> AnswerResponse. Returns (response, was_hit).
    Conversations with history are never cached (the answer depends on earlier turns)."""
    if not ENABLED or history:
        return compute(question, filters=filters, history=history), False
    key, t0 = _key(question, filters), time.perf_counter()
    with _lock:
        hit = _store.get(key)
        if hit and time.time() - hit[0] < TTL_S:
            _store.move_to_end(key)
            stats["hits"] += 1
            resp = hit[1]
            return resp.model_copy(update={
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "tokens": 0, "cost": 0.0}), True
        stats["misses"] += 1
    resp = compute(question, filters=filters, history=history)   # outside the lock: LLM calls are slow
    if getattr(resp, "answerable", True) and resp.tokens > 0:    # cache only real LLM answers
        with _lock:
            _store[key] = (time.time(), resp)
            while len(_store) > MAX_ITEMS:
                _store.popitem(last=False)
    return resp, False


def clear() -> None:
    with _lock:
        _store.clear()