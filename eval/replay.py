"""Replay eval questions through answer() to build a before/after request log.

    USE_RERANK=true  python3 -m eval.replay --log data/requests_before.jsonl
    USE_RERANK=false python3 -m eval.replay --log data/requests_after.jsonl

Then: python3 -m eval.cost_model --log data/requests_before.jsonl   (and the _after one)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from eval.retrieval_eval import load_questions
from src.common.config import Config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="data/eval/questions_p*.jsonl")
    ap.add_argument("--log", required=True)
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()

    qs = load_questions(a.questions)
    qs = qs[:: max(1, len(qs) // a.n)][: a.n]          # spread across the question files

    from src.retrieval.retriever import retrieve
    retrieve("warm up", k=5, rerank=Config.USE_RERANK)  # load models; no LLM call, no log entry

    log = Path(a.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("")
    Config.REQUEST_LOG = log                            # answer() now logs here

    from src.generation.answer import answer
    print(f"USE_RERANK={Config.USE_RERANK} model={Config.LLM_MODEL} questions={len(qs)}")
    for i, q in enumerate(qs, 1):
        try:
            answer(q["question"])
        except Exception as e:
            print(f"\nquestion {q.get('id')} failed: {type(e).__name__}: {e}")
        print(f"\r{i}/{len(qs)}", end="", flush=True)
    print()


if __name__ == "__main__":
    main()