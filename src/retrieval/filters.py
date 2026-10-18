"""Metadata filters. filters = {"source": "OWASP" | [..], "year": 2021 | [2020, 2021] | {"min":2019,"max":2022}}"""
from __future__ import annotations

from .backend import chunk_meta


def _as_list(v):
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _year(meta) -> int | None:
    y = meta.get("year")
    if y is None and meta.get("date"):
        y = str(meta["date"])[:4]
    try:
        return int(y)
    except (TypeError, ValueError):
        return None


def matches(chunk, filters: dict | None) -> bool:
    if not filters:
        return True
    meta = chunk_meta(chunk)
    for key, want in filters.items():
        if want in (None, "", "All", []):
            continue
        if key == "year":
            y = _year(meta)
            if y is None:
                return False
            if isinstance(want, dict):
                if y < want.get("min", -10**9) or y > want.get("max", 10**9):
                    return False
            elif y not in {int(w) for w in _as_list(want)}:
                return False
        else:
            have = str(meta.get(key, "")).lower()
            if have not in {str(w).lower() for w in _as_list(want)}:
                return False
    return True
