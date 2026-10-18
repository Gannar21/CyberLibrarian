from __future__ import annotations


def rrf(ranked_lists: list[list[str]], k0: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k0 + rank)."""
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, cid in enumerate(lst, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k0 + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
