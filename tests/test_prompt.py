from src.common.schemas import Chunk, RetrievalResult
from src.generation.prompt import build_prompt


def test_build_prompt_numbers_sources():
    chunk = Chunk(
        chunk_id="c1", doc_id="d1", title="SQL Injection", source="owasp",
        section="Overview", date=None, position=0,
        text="SQL injection inserts malicious SQL into a query.",
    )
    prompt = build_prompt("What is SQL injection?", [RetrievalResult(chunk=chunk, score=1.0)])
    assert "[1] SQL Injection - Overview (OWASP)" in prompt
    assert "What is SQL injection?" in prompt