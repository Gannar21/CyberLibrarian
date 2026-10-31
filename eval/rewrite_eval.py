
from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from src.retrieval import retrieve
from src.retrieval.backend import chunk_meta, chunk_text, tokenize
from eval.retrieval_eval import (
    KS,
    OVERLAP,
    PASSAGE_KEYS,
    DOC_KEYS,
    _first,
    is_relevant,
)

QUESTIONS = Path("data/eval/questions_dev.jsonl")
RESULTS_DIR = Path("eval/results")
OUTPUT = RESULTS_DIR / "p2_rewrite_dev.json"


def evaluate(questions: list[dict], rewrite: bool) -> dict:
    hits = {k: 0 for k in KS}
    reciprocal_ranks = []
    latencies = []

    for index, question in enumerate(questions, start=1):
        start = time.perf_counter()

        results = retrieve(
            question["question"],
            k=max(KS),
            mode="hybrid",
            rerank=False,
            rewrite=rewrite,
        )

        latencies.append((time.perf_counter() - start) * 1000)

        chunks = [getattr(result, "chunk", result) for result in results]
        relevant = [is_relevant(chunk, question) for chunk in chunks]

        for k in KS:
            if any(relevant[:k]):
                hits[k] += 1

        reciprocal_ranks.append(
            next(
                (1 / (rank + 1) for rank, is_rel in enumerate(relevant) if is_rel),
                0.0,
            )
        )

        if index % 10 == 0:
            print(
                f"{'rewrite' if rewrite else 'baseline'}: "
                f"{index}/{len(questions)} questions"
            )

    n = len(questions)
    if n == 0:
        raise ValueError("No answerable development questions were found.")

    sorted_latencies = sorted(latencies)

    return {
        "config": "hybrid + rewrite" if rewrite else "hybrid baseline",
        "n": n,
        **{
            f"recall@{k}": round(hits[k] / n, 3)
            for k in KS
        },
        "mrr": round(sum(reciprocal_ranks) / n, 3),
        "latency_p50_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": round(
            sorted_latencies[min(n - 1, int(0.95 * n))], 1
        ),
    }


def main() -> None:
    questions = []

    with QUESTIONS.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                question = json.loads(line)

                if (
                    question.get("answerable", True) is not False
                    and question.get("type") != "unanswerable"
                ):
                    questions.append(question)

    if not questions:
        raise ValueError(f"No answerable questions found in {QUESTIONS}")

    print(f"Evaluating {len(questions)} development questions.")

    baseline = evaluate(questions, rewrite=False)
    rewritten = evaluate(questions, rewrite=True)

    # Breakdown by question type.
    by_type = defaultdict(list)

    for question in questions:
        by_type[question.get("type", "unknown")].append(question)

    type_results = {}

    for question_type, typed_questions in sorted(by_type.items()):
        print(f"Evaluating question type: {question_type}")

        type_results[question_type] = {
            "n": len(typed_questions),
            "baseline": evaluate(typed_questions, rewrite=False),
            "rewrite": evaluate(typed_questions, rewrite=True),
        }

    output = {
        "dataset": str(QUESTIONS),
        "total_questions": len(questions),
        "overall": [baseline, rewritten],
        "by_type": type_results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("\nOverall results:")
    print(json.dumps(output["overall"], indent=2))

    print(f"\nResults saved to: {OUTPUT}")


if __name__ == "__main__":
    main()