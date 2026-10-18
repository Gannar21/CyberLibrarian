from src.retrieval.filters import matches
from src.retrieval.fusion import rrf


def test_rrf_prefers_docs_in_both_lists():
    fused = rrf([["a", "b", "c"], ["c", "a", "d"]])
    assert [d for d, _ in fused][:2] == ["a", "c"]


def test_rrf_single_list_keeps_order():
    assert [d for d, _ in rrf([["x", "y", "z"]])] == ["x", "y", "z"]


def test_filters_source_and_year():
    c = {"chunk_id": "1", "metadata": {"source": "OWASP", "year": 2021}}
    assert matches(c, {"source": "owasp"})
    assert matches(c, {"year": {"min": 2020, "max": 2022}})
    assert not matches(c, {"year": 2019})
    assert not matches(c, {"source": "NIST"})
    assert matches(c, None)
