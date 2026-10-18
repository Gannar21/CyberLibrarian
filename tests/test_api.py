from fastapi.testclient import TestClient

from src.api import main
from src.common.schemas import AnswerResponse

client = TestClient(main.app)


def fake_answer(question, filters=None):
    return AnswerResponse(
        answer="Use prepared statements [1].", citations=[], chunks=[],
        latency_ms=5, tokens=10, cost=0.0, answerable=True,
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_ask_returns_answer_response(monkeypatch):
    monkeypatch.setattr(main, "answer", fake_answer)
    r = client.post("/ask", json={"question": "What is SQL injection?"})
    assert r.status_code == 200
    assert r.json()["answer"].startswith("Use prepared")


def test_ask_rejects_empty_question():
    assert client.post("/ask", json={"question": "  "}).status_code == 400