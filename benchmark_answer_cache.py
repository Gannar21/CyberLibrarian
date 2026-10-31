import statistics
import time
from unittest.mock import patch

from src.common.config import Config
from src.common.schemas import Chunk, RetrievalResult
from src.generation import answer as answer_module


def make_results():
    chunk = Chunk(
        chunk_id="benchmark-chunk-1",
        doc_id="benchmark-doc-1",
        title="Phishing Prevention",
        source="owasp",
        section="Security",
        date=None,
        position=0,
        text="Phishing is a social engineering attack.",
    )
    return [RetrievalResult(chunk=chunk, score=0.9)]


def run_benchmark(use_cache: bool, iterations: int = 100):
    answer_module.ANSWER_CACHE.clear()
    results = make_results()
    timings = []

    with (
        patch.object(Config, "USE_CACHE", use_cache),
        patch.object(
            answer_module, "_retrieve", return_value=results
        ) as mock_retrieve,
        patch.object(
            answer_module, "build_prompt", return_value="Benchmark prompt"
        ),
        patch.object(
            answer_module,
            "call_llm",
            return_value=("A benchmark answer [1]", 10, 5),
        ) as mock_llm,
        patch.object(
            answer_module, "parse_citations", return_value=[]
        ),
        patch.object(answer_module, "log_request"),
    ):
        for _ in range(iterations):
            start = time.perf_counter()
            answer_module.answer("What is phishing?")
            timings.append((time.perf_counter() - start) * 1000)

        return {
            "cache_enabled": use_cache,
            "iterations": iterations,
            "retrieval_calls": mock_retrieve.call_count,
            "llm_calls": mock_llm.call_count,
            "median_ms": round(statistics.median(timings), 3),
            "p95_ms": round(
                sorted(timings)[int(0.95 * (len(timings) - 1))], 3
            ),
        }


if __name__ == "__main__":
    uncached = run_benchmark(False)
    cached = run_benchmark(True)

    print("\n--- Answer Cache Benchmark ---")
    print(f"Cache disabled: {uncached}")
    print(f"Cache enabled:  {cached}")

    if uncached["median_ms"] > 0:
        reduction = (
            1 - cached["median_ms"] / uncached["median_ms"]
        ) * 100
        print(f"Median latency reduction: {reduction:.2f}%")

    print("\nNote: retrieval and LLM generation are mocked.")
    print("These results measure application/cache overhead,")
    print("not real end-to-end RAG latency.")