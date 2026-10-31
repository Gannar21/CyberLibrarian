"""Tests that all Pydantic models validate and round-trip through JSON."""
import json
import pytest

from src.common.schemas import (
    AnswerResponse,
    Citation,
    Chunk,
    Document,
    RetrievalResult,
    answer,
    retrieve,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_document() -> Document:
    return Document(
        doc_id="owasp-sql-injection",
        title="SQL Injection Prevention",
        source="owasp",
        section="Defense 1: Prepared Statements",
        date="2024-01-15",
        url="https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
        text="Use parameterized queries to prevent SQL injection.",
    )


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        chunk_id="owasp-sql-injection-0",
        doc_id="owasp-sql-injection",
        title="SQL Injection Prevention",
        source="owasp",
        section="Defense 1: Prepared Statements",
        date="2024-01-15",
        position=0,
        text="Use parameterized queries to prevent SQL injection.",
    )


@pytest.fixture
def sample_retrieval_result(sample_chunk: Chunk) -> RetrievalResult:
    return RetrievalResult(chunk=sample_chunk, score=0.92)


@pytest.fixture
def sample_citation() -> Citation:
    return Citation(
        id=1,
        chunk_id="owasp-sql-injection-0",
        title="SQL Injection Prevention",
        source="owasp",
        section="Defense 1: Prepared Statements",
        url="https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
    )


@pytest.fixture
def sample_answer_response(
    sample_retrieval_result: RetrievalResult,
    sample_citation: Citation,
) -> AnswerResponse:
    return AnswerResponse(
        answer="Use parameterized queries [1].",
        citations=[sample_citation],
        chunks=[sample_retrieval_result],
        latency_ms=250,
        tokens=128,
        cost=0.0003,
        answerable=True,
    )


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_document_validates(sample_document: Document) -> None:
    assert sample_document.doc_id == "owasp-sql-injection"
    assert sample_document.source == "owasp"


def test_document_roundtrip(sample_document: Document) -> None:
    json_str = sample_document.to_jsonl()
    restored = Document.from_jsonl(json_str)
    assert restored == sample_document


def test_document_date_none() -> None:
    doc = Document(
        doc_id="nist-sp800-61r3-p1",
        title="Computer Security Incident Handling Guide",
        source="nist",
        section="",
        date=None,
        url="https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        text="Sample text.",
    )
    assert doc.date is None
    # round-trip
    assert Document.from_jsonl(doc.to_jsonl()).date is None


def test_chunk_validates(sample_chunk: Chunk) -> None:
    assert sample_chunk.position == 0
    assert sample_chunk.doc_id == "owasp-sql-injection"


def test_chunk_roundtrip(sample_chunk: Chunk) -> None:
    data = json.loads(sample_chunk.model_dump_json())
    restored = Chunk.model_validate(data)
    assert restored == sample_chunk


def test_retrieval_result_roundtrip(sample_retrieval_result: RetrievalResult) -> None:
    data = json.loads(sample_retrieval_result.model_dump_json())
    restored = RetrievalResult.model_validate(data)
    assert restored == sample_retrieval_result
    assert restored.score == pytest.approx(0.92)


def test_citation_roundtrip(sample_citation: Citation) -> None:
    data = json.loads(sample_citation.model_dump_json())
    restored = Citation.model_validate(data)
    assert restored == sample_citation
    assert restored.id == 1


def test_answer_response_defaults() -> None:
    # answerable defaults to True
    ar = AnswerResponse(
        answer="I don't know.",
        citations=[],
        chunks=[],
        latency_ms=10,
        tokens=5,
        cost=0.0,
        answerable=False,
    )
    assert ar.answerable is False


def test_answer_response_roundtrip(sample_answer_response: AnswerResponse) -> None:
    data = json.loads(sample_answer_response.model_dump_json())
    restored = AnswerResponse.model_validate(data)
    assert restored == sample_answer_response


def test_invalid_source_rejected() -> None:
    with pytest.raises(Exception):
        Document(
            doc_id="bad-source-doc",
            title="Test",
            source="unknown_source",   # not in SourceName
            section="",
            date=None,
            url="https://example.com",
            text="text",
        )


# ---------------------------------------------------------------------------
# Delegation tests (monkeypatched backends – no network, no API key)
# ---------------------------------------------------------------------------

def test_retrieve_returns_list(monkeypatch, sample_chunk: Chunk) -> None:
    """retrieve() should delegate to the retrieval backend and return list[RetrievalResult]."""
    import sys
    from types import ModuleType

    fake_result = RetrievalResult(chunk=sample_chunk, score=0.9)
    fake_mod = ModuleType("src.retrieval.retriever")
    fake_mod.retrieve = lambda query, **kwargs: [fake_result]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.retrieval.retriever", fake_mod)

    results = retrieve("what is SQL injection?")

    assert isinstance(results, list)
    assert len(results) == 1
    assert isinstance(results[0], RetrievalResult)
    assert results[0].score == pytest.approx(0.9)


def test_answer_returns_answer_response(
    monkeypatch, sample_answer_response: AnswerResponse
) -> None:
    """answer() should delegate to the generation backend and return AnswerResponse."""
    import sys
    from types import ModuleType

    fake_mod = ModuleType("src.generation.answer")
    fake_mod.answer = lambda question, **kwargs: sample_answer_response  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.generation.answer", fake_mod)

    result = answer("what is SQL injection?")

    assert isinstance(result, AnswerResponse)
    assert result.answerable is True
    assert result.answer == "Use parameterized queries [1]."
