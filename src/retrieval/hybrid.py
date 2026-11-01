"""Thin wrapper kept for the original interface; the logic lives in retriever.py."""
from __future__ import annotations

from .retriever import retrieve


def hybrid_retrieve(query: str, k: int = 5, filters: dict | None = None, **kw):
    return retrieve(query, k=k, filters=filters, mode="hybrid", **kw)