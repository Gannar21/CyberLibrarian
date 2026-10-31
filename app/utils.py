"""Shared utilities for both the Streamlit fallback and the web UI."""
from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path

from src.common.config import REPO_ROOT, Config
from src.common.schemas import AnswerResponse

USAGE_LOG: Path = REPO_ROOT / "data" / "usage_log.jsonl"


def new_session_id() -> str:
    return uuid.uuid4().hex


def chunk_url_from_citations(chunk_id: str, citations: list) -> str:
    for c in citations:
        if c.chunk_id == chunk_id:
            return c.url
    return ""


def save_feedback(question: str, answer: str, rating: str, comment: str) -> None:
    Config.FEEDBACK_JSONL.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "question": question,
        "answer": answer[:500],
        "rating": rating,
        "comment": comment,
    }
    with open(Config.FEEDBACK_JSONL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def log_usage(
    session_id: str,
    question: str,
    resp: AnswerResponse,
    rating: str | None = None,
) -> None:
    """Append one entry to data/usage_log.jsonl.

    Never stores IPs, names, or any PII.  session_id is a random UUID hex.
    """
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    record: dict = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": session_id,
        "round": os.getenv("TEST_ROUND", ""),
        "question": question,
        "answerable": resp.answerable,
        "top_source_ids": [r.chunk.chunk_id for r in resp.chunks[:5]],
        "latency_ms": resp.latency_ms,
        "cost": resp.cost,
    }
    if rating is not None:
        record["rating"] = rating
    with USAGE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
