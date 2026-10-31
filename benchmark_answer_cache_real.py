import importlib
import time
from unittest.mock import patch

from src.common.config import Config

answer_module = importlib.import_module("src.generation.answer")

QUESTION = "What is phishing?"
FILTERS = None


def run_request(label):
    start = time.perf_counter()
    response = answer_module.answer(QUESTION, FILTERS)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"\n{label}")
    print(f"  Cache hit:        {response.cache_hit}")
    print(f"  Actual time:      {elapsed_ms:.2f} ms")
    print(f"  Reported latency: {response.latency_ms} ms")
    print(f"  Retrieved chunks: {len(response.chunks)}")
    print(f"  Citations:        {len(response.citations)}")
    print(f"  Tokens:           {response.tokens}")
    print(f"  Estimated cost:   ${response.cost:.8f}")

    return response, elapsed_ms


def main():
    print("=== Real Answer Cache Benchmark ===")
    print(f"Model: {Config.LLM_MODEL}")
    print(f"Question: {QUESTION}")
    print("Expected maximum: 2 uncached requests to the LLM.")
    print("The benchmark may incur API charges.")

    answer_module.ANSWER_CACHE.clear()

    # 1. Baseline: cache disabled.
    with patch.object(Config, "USE_CACHE", False):
        baseline, baseline_ms = run_request(
            "1. Cache disabled"
        )

    # 2. Enable caching and make one request to populate the cache.
    answer_module.ANSWER_CACHE.clear()

    with patch.object(Config, "USE_CACHE", True):
        warm, warm_ms = run_request(
            "2. Cache enabled — first request"
        )

        # 3. Repeat the same question twice.
        hit1, hit1_ms = run_request(
            "3. Cache enabled — repeat 1"
        )

        hit2, hit2_ms = run_request(
            "4. Cache enabled — repeat 2"
        )

    if not hit1.cache_hit or not hit2.cache_hit:
        raise RuntimeError(
            "Cache verification failed: repeated requests "
            "did not both return cache hits."
        )

    print("\n=== Summary ===")
    print(f"Baseline latency:       {baseline_ms:.2f} ms")
    print(f"Cache warm-up latency:  {warm_ms:.2f} ms")
    print(f"First cache-hit latency: {hit1_ms:.2f} ms")
    print(f"Second cache-hit latency: {hit2_ms:.2f} ms")

    print(f"\nBaseline tokens: {baseline.tokens}")
    print(f"Cache-hit tokens: {hit1.tokens}")
    print(f"Baseline cost estimate: ${baseline.cost:.8f}")
    print(f"Cache-hit cost estimate: ${hit1.cost:.8f}")

    if baseline_ms > 0:
        reduction = (baseline_ms - hit1_ms) / baseline_ms * 100
        print(f"Latency reduction vs baseline: {reduction:.2f}%")

    print("\nBenchmark completed.")
    print("Remember: timing varies with network and API conditions.")
    print("Cost estimates depend on your configured pricing values.")


if __name__ == "__main__":
    main()