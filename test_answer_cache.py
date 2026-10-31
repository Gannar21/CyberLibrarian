import time

from src.common.schemas import AnswerResponse
from src.generation.answer_cache import AnswerCache


def make_response() -> AnswerResponse:
    return AnswerResponse(
        answer="Test answer [1]",
        citations=[],
        chunks=[],
        latency_ms=100,
        tokens=20,
        cost=0.001,
        answerable=True,
        cache_hit=False,
    )


def test_cache_hit():
    cache = AnswerCache(maxsize=10, ttl_seconds=5)
    response = make_response()

    cache.set("question-1", response)

    result = cache.get("question-1")

    assert result is not None
    assert result.answer == response.answer
    assert result.cache_hit is False


def test_different_questions_are_separate():
    cache = AnswerCache(maxsize=10, ttl_seconds=5)

    cache.set("question-1", make_response())

    assert cache.get("question-2") is None


def test_expiration():
    cache = AnswerCache(maxsize=10, ttl_seconds=1)

    cache.set("question-1", make_response())
    time.sleep(1.1)

    assert cache.get("question-1") is None


def test_maximum_size():
    cache = AnswerCache(maxsize=2, ttl_seconds=5)

    cache.set("question-1", make_response())
    cache.set("question-2", make_response())
    cache.set("question-3", make_response())

    assert len(cache) == 2
    assert cache.get("question-1") is None
    assert cache.get("question-3") is not None


def test_clear():
    cache = AnswerCache(maxsize=10, ttl_seconds=5)

    cache.set("question-1", make_response())
    cache.clear()

    assert len(cache) == 0
    assert cache.get("question-1") is None


if __name__ == "__main__":
    test_cache_hit()
    test_different_questions_are_separate()
    test_expiration()
    test_maximum_size()
    test_clear()

    print("All 5 answer-cache tests passed.")