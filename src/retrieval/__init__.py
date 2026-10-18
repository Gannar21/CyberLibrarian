"""
Public retrieval interface.  Import retrieve() from here.
Implemented by Person 3 via src.retrieval.hybrid.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.common.schemas import RetrievalResult


def retrieve(
    query: str,
    k: int = 5,
    filters: dict | None = None,
) -> list["RetrievalResult"]:
    """Return the top-k chunks for *query* using hybrid retrieval.

    Args:
        query:   Natural-language question or search string.
        k:       Number of results to return.
        filters: Optional dict with keys 'source' (str) and/or 'year' (int).

    Returns:
        List of RetrievalResult sorted by score descending.
    """
    raise NotImplementedError(
        "retrieve() must be implemented by Person 3 in src/retrieval/hybrid.py"
    )
