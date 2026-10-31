from unittest.mock import patch

from src.common.config import Config
from src.common.schemas import AnswerResponse, Chunk, RetrievalResult
from src.generation import answer as answer_module


def make_retrieval_result():
    chunk = Chunk(
        chunk_id="test-chunk-1",
        doc_id="test-doc-1",
        title="Phishing Prevention",
        source="owasp",
        section="Security",
        date=None,
        position=0,
        text="Phishing is a social engineering attack.",
    )
    return [RetrievalResult(chunk=chunk, score=0.9)]


def test_repeated_question_uses_cache():
    answer_module.ANSWER_CACHE.clear()
    results = make_retrieval_result()

    with (
        patch.object(Config, "USE_CACHE", True),
        patch.object(
            answer_module, "_retrieve", return_value=results
        ) as mock_retrieve,
        patch.object(
            answer_module, "build_prompt", return_value="Test prompt"
        ),
        patch.object(
            answer_module,
            "call_llm",
            return_value=("A test answer [1]", 10, 5),
        ) as mock_llm,
        patch.object(
            answer_module, "parse_citations", return_value=[]
        ),
    ):
        first = answer_module.answer("What is phishing?")
        second = answer_module.answer("What is phishing?")

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert first.answer == second.answer
        assert mock_retrieve.call_count == 1
        assert mock_llm.call_count == 1

    print("PASS: Repeated question uses the cache.")


def test_different_filters_use_separate_entries():
    answer_module.ANSWER_CACHE.clear()
    results = make_retrieval_result()

    with (
        patch.object(Config, "USE_CACHE", True),
        patch.object(
            answer_module, "_retrieve", return_value=results
        ) as mock_retrieve,
        patch.object(
            answer_module, "build_prompt", return_value="Test prompt"
        ),
        patch.object(
            answer_module,
            "call_llm",
            return_value=("A test answer", 10, 5),
        ),
        patch.object(
            answer_module, "parse_citations", return_value=[]
        ),
    ):
        answer_module.answer(
            "What is phishing?", filters={"source": "owasp"}
        )
        answer_module.answer(
            "What is phishing?", filters={"source": "nist"}
        )

        assert mock_retrieve.call_count == 2

    print("PASS: Different filters use separate cache entries.")

def test_cache_disabled():
    answer_module.ANSWER_CACHE.clear()
    results = make_retrieval_result()

    with (
        patch.object(Config, "USE_CACHE", False),
        patch.object(
            answer_module, "_retrieve", return_value=results
        ) as mock_retrieve,
        patch.object(
            answer_module, "build_prompt", return_value="Test prompt"
        ),
        patch.object(
            answer_module,
            "call_llm",
            return_value=("A test answer", 10, 5),
        ) as mock_llm,
        patch.object(
            answer_module, "parse_citations", return_value=[]
        ),
    ):
        first = answer_module.answer("What is phishing?")
        second = answer_module.answer("What is phishing?")

        assert first.cache_hit is False
        assert second.cache_hit is False
        assert mock_retrieve.call_count == 2
        assert mock_llm.call_count == 2
        assert len(answer_module.ANSWER_CACHE) == 0

    print("PASS: Disabling the cache bypasses it.")
if __name__ == "__main__":
    test_repeated_question_uses_cache()
    test_different_filters_use_separate_entries()
    test_cache_disabled()
    answer_module.ANSWER_CACHE.clear()
    print("All 3 answer-cache integration tests passed.")