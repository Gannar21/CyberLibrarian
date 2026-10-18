"""
Shared Pydantic models and function stubs for the CyberLibrarian RAG pipeline.
All teammates import from here; do not redefine these models elsewhere.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

SourceName = Literal["owasp", "nist", "mitre", "cisa"]


class Document(BaseModel):
    """A single source document as produced by a loader in src/ingest/."""

    doc_id: str
    title: str
    source: SourceName
    section: str       # may be empty string
    date: str | None   # ISO date string, e.g. "2024-02-26", or None
    url: str
    text: str

    def to_jsonl(self) -> str:
        """Serialize to a single JSON line for documents.jsonl."""
        return self.model_dump_json()

    @classmethod
    def from_jsonl(cls, line: str) -> "Document":
        """Deserialize from a single JSON line."""
        return cls.model_validate_json(line)


class Chunk(BaseModel):
    """A sub-document unit stored in the vector and BM25 indexes."""

    chunk_id: str
    doc_id: str
    title: str
    source: SourceName
    section: str
    date: str | None
    position: int   # 0-based index of this chunk within its parent document
    text: str


class RetrievalResult(BaseModel):
    """A retrieved chunk paired with its relevance score."""

    chunk: Chunk
    score: float


class Citation(BaseModel):
    """One inline citation displayed in the answer."""

    id: int         # 1-based, matches the [1] marker in the answer text
    chunk_id: str
    title: str
    source: SourceName
    section: str
    url: str


class AnswerResponse(BaseModel):
    """The full response returned by the /ask endpoint and the answer() function."""

    answer: str                     # LLM text with inline [1] [2] markers
    citations: list[Citation]
    chunks: list[RetrievalResult]   # raw retrieval results for the UI
    latency_ms: int
    tokens: int
    cost: float
    answerable: bool = True         # False when the model cannot answer from the docs


# ---------------------------------------------------------------------------
# Entry points (declared here so callers can import them from one stable place)
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    k: int = 5,
    filters: dict | None = None,
) -> list[RetrievalResult]:
    """Return the top-k chunks for *query* using hybrid retrieval.

    Args:
        query:   Natural-language question or search string.
        k:       Number of results to return.
        filters: Optional dict.  Supported keys:
                   'source' – one of SourceName values
                   'year'   – integer, filters by document date year
    """
    from src.retrieval.retriever import retrieve as _retrieve

    return _retrieve(query, k=k, filters=filters)


def answer(
    question: str,
    filters: dict | None = None,
) -> AnswerResponse:
    """Run the full RAG pipeline for *question* and return a structured response.

    Args:
        question: The user's natural-language question.
        filters:  Same filter keys as retrieve().
    """
    from src.generation.answer import answer as _answer

    return _answer(question, filters=filters)