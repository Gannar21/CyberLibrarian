"""Generation eval: 'I don't know' behaviour, faithfulness, citation accuracy, correctness.

    python -m eval.generation_eval --n-dev 10

Runs all of data/eval/questions_p4.jsonl plus a spread sample of questions_dev.jsonl
through answer() (cache OFF), then uses the LLM as a judge. Costs real money: start small.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.common.config import Config

JUDGE_PROMPT = """You grade an answer produced by a retrieval-augmented system.

SOURCES (numbered exactly as the system saw them):
{sources}

QUESTION: {question}
REFERENCE ANSWER: {reference}
SYSTEM ANSWER: {answer}

Score with 0 or 1:
- faithfulness: 1 if every claim in the system answer is supported by the sources, else 0.
- citation_accuracy: 1 if every [n] marker points to a source that really says what is claimed, else 0 (0 if there are no markers).
- correctness: 1 if the system answer agrees in meaning with the reference answer, else 0.

Return ONLY JSON: {{"faithfulness": 0, "citation_accuracy": 0, "correctness": 0, "note": "short reason"}}"""


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8"):
        if line.strip():
            rows.append(json.loads(line))
    return rows


def judge(question: str, reference: str, resp) -> dict:
    from src.generation.answer import call_llm
    sources = "\n\n".join(
        f"[{i}] {r.chunk.text[:1500]}" for i, r in enumerate(resp.chunks, start=1)
    )
    prompt = JUDGE_PROMPT.format(sources=sources, question=question,
                                 reference=reference, answer=resp.answer)
    text, _, _ = call_llm(prompt)
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return {"faithfulness": 0, "citation_accuracy": 0, "correctness": 0,
                "note": "judge output unreadable"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-dev", type=int, default=10, help="questions sampled from questions_dev.jsonl")
    ap.add_argument("--out", default="eval/results/generation_eval")
    a = ap.parse_args()

    eval_dir = Path("data/eval")
    qs = load(eval_dir / "questions_p4.jsonl")
    dev = load(eval_dir / "questions_dev.jsonl")
    step = max(1, len(dev) // max(1, a.n_dev))
    seen = {q["id"] for q in qs}
    qs += [q for q in dev[::step][: a.n_dev] if q["id"] not in seen]

    Config.USE_CACHE = False                       # never evaluate cached answers
    Path("eval/results").mkdir(parents=True, exist_ok=True)
    Config.REQUEST_LOG = Path("eval/results/requests_generation_eval.jsonl")
    Config.REQUEST_LOG.write_text("")

    from src.generation.answer import answer
    print(f"model={Config.LLM_MODEL} questions={len(qs)}")

    rows = []
    for i, q in enumerate(qs, 1):
        try:
            resp = answer(q["question"])
        except Exception as e:
            print(f"\n{q['id']} failed: {type(e).__name__}: {e}")
            continue
        row = {"id": q["id"], "type": q["type"], "question": q["question"],
               "answerable_pred": resp.answerable, "answer": resp.answer,
               "cost": resp.cost, "latency_ms": resp.latency_ms}
        if q["type"] == "unanswerable":
            row["refusal_correct"] = not resp.answerable
        else:
            row["false_refusal"] = not resp.answerable
            if resp.answerable:
                row.update(judge(q["question"], q["answer"], resp))
        rows.append(row)
        print(f"\r{i}/{len(qs)}", end="", flush=True)
    print()

    unans = [r for r in rows if r["type"] == "unanswerable"]
    ans = [r for r in rows if r["type"] != "unanswerable"]
    judged = [r for r in ans if "faithfulness" in r]

    def rate(items, key):
        return round(sum(r[key] for r in items) / len(items), 3) if items else None

    summary = {
        "n_questions": len(rows),
        "n_unanswerable": len(unans),
        "n_answerable": len(ans),
        "correct_refusals": rate(unans, "refusal_correct"),
        "false_refusal_rate": rate(ans, "false_refusal"),
        "faithfulness": rate(judged, "faithfulness"),
        "citation_accuracy": rate(judged, "citation_accuracy"),
        "correctness": rate(judged, "correctness"),
        "avg_cost_per_question": round(sum(r["cost"] for r in rows) / len(rows), 6) if rows else None,
        "avg_latency_ms": int(sum(r["latency_ms"] for r in rows) / len(rows)) if rows else None,
        "model": Config.LLM_MODEL,
    }
    Path(a.out + ".json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    md = ["| metric | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items()]
    Path(a.out + ".md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    bad = [r for r in rows if r.get("false_refusal") or r.get("refusal_correct") is False
           or r.get("correctness") == 0 or r.get("faithfulness") == 0]
    print(f"\n{len(bad)} problem questions, see {a.out}.json")


if __name__ == "__main__":
    main()
    