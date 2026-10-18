import importlib

from src.common.schemas import Chunk, RetrievalResult

gen = importlib.import_module("src.generation.answer")


def make_result(i: int) -> RetrievalResult:
    chunk = Chunk(
        chunk_id=f"c{i}", doc_id=f"d{i}", title=f"Doc {i}", source="owasp",
        section="S", date=None, position=0, text=f"text {i}",
    )
    return RetrievalResult(chunk=chunk, score=1.0)


def test_parse_citations_handles_repeats_commas_and_bad_numbers():
    results = [make_result(1), make_result(2)]
    cites = gen.parse_citations("A [1][2] and again [1], also [9] and [1, 2].", results)
    assert [c.id for c in cites] == [1, 2]
    assert cites[0].chunk_id == "c1"


def test_answer_returns_cited_response(monkeypatch):
    monkeypatch.setattr(gen, "_retrieve", lambda q, k, f: [make_result(1)])
    monkeypatch.setattr(gen, "call_llm", lambda p: ("Use prepared statements [1].", 100, 20))
    monkeypatch.setattr(gen, "log_request", lambda r: None)
    resp = gen.answer("How to stop SQL injection?")
    assert resp.answerable is True
    assert resp.citations[0].chunk_id == "c1"
    assert resp.tokens == 120
    assert resp.cost > 0


def test_answer_with_no_chunks_says_i_dont_know(monkeypatch):
    monkeypatch.setattr(gen, "_retrieve", lambda q, k, f: [])
    monkeypatch.setattr(gen, "log_request", lambda r: None)
    resp = gen.answer("Something unrelated")
    assert resp.answerable is False
    assert resp.citations == []


def test_normalize_filters_translates_year_range():
    out = gen.normalize_filters({"source": ["owasp"], "year_min": 2020, "year_max": 2024})
    assert out == {"source": ["owasp"], "year": {"min": 2020, "max": 2024}}
    assert gen.normalize_filters(None) is None
    assert gen.normalize_filters({}) is None