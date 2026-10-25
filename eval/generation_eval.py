"""Generation eval: correctness, faithfulness, citation accuracy, IDK, latency, cost.

Resumable: every finished question is saved immediately and skipped on rerun.

Run from the project root:
    python3 -m eval.generation_eval --limit 5 --tag smoke
    python3 -m eval.generation_eval --split dev --tag baseline
    python3 -m eval.generation_eval --split test --tag baseline
Use the same --split and a new --tag after Week 8 changes for before/after numbers.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import time
from pathlib import Path

from src.common.config import Config
from src.generation.answer import _client, answer

RESULTS_DIR = Path(__file__).resolve().parent / "results"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", Config.LLM_MODEL)

JUDGE_PROMPT = """You are a strict grader for a retrieval-augmented QA system.
Return ONLY a JSON object, no other text.

Question: {question}

Reference answer: {gold}

Reference passage: {passage}

System answer: {system}

Cited sources (numbered as in the system answer):
{sources}

Grade:
- correct: 1 if the system answer agrees with the reference answer on the key facts, else 0.
- faithful: 1 if EVERY claim in the system answer is supported by the cited sources above, else 0.
- supported_citations: how many of the cited sources actually support the claim they are attached to (integer).

Output format: {{"correct": 0 or 1, "faithful": 0 or 1, "supported_citations": integer}}"""


class DailyLimit(Exception):
    """Groq daily token budget exhausted: stop and resume later."""


# ---------------------------------------------------------------- helpers
def first(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return default


def is_unanswerable(q: dict) -> bool:
    a = q.get("answerable")
    if a is not None:
        return a is False or str(a).lower() == "false"
    t = str(first(q, "type", "question_type", "category", default="")).lower()
    return any(w in t for w in ("unanswerable", "out_of_scope", "out-of-scope",
                                "no_answer", "adversarial", "refusal"))


def in_split(question: str, split: str) -> bool:
    if split == "all":
        return True
    h = int(hashlib.md5(question.encode("utf-8")).hexdigest(), 16) % 100
    return h < 30 if split == "test" else h >= 30   # test = 30% held out, dev = 70%


def pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))]


def with_retry(fn, tries: int = 5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if "tokens per day" in msg or "(TPD)" in msg:
                raise DailyLimit(msg)
            if i == tries - 1:
                raise
            wait = 5 * (i + 1)
            m = re.search(r"try again in (?:(\d+)m)?\s*([\d.]+)s", msg)
            if m:
                wait = min(90, int(m.group(1) or 0) * 60 + float(m.group(2)) + 1)
            print(f"   retry in {wait:.0f}s after {type(e).__name__}")
            time.sleep(wait)


def judge(q: dict, resp) -> dict:
    sources = []
    for c in resp.citations:
        if 1 <= c.id <= len(resp.chunks):
            sources.append(f"[{c.id}] {resp.chunks[c.id - 1].chunk.text[:1500]}")
    prompt = JUDGE_PROMPT.format(
        question=first(q, "question", "q"),
        gold=first(q, "answer", "gold_answer", "expected_answer", "reference_answer", default="(none)"),
        passage=str(first(q, "source_passage", "passage", "evidence", "context", default="(none)"))[:1500],
        system=resp.answer,
        sources="\n\n".join(sources) or "(no citations)",
    )

    def call():
        r = _client().chat.completions.create(
            model=JUDGE_MODEL, temperature=0, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content or ""

    text = with_retry(call)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        j = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        j = {}
    return {"correct": int(j.get("correct", 0)), "faithful": int(j.get("faithful", 0)),
            "supported": int(j.get("supported_citations", 0))}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def write_summary(rows: list[dict], args, total: int) -> dict:
    ans = [r for r in rows if not r["unanswerable"]]
    un = [r for r in rows if r["unanswerable"]]
    answered = [r for r in ans if r["answerable_pred"]]
    lat = [r["latency_ms"] for r in rows]
    costs = [r["cost"] for r in rows]
    cited = sum(r["n_citations"] for r in answered)

    summary = {
        "tag": args.tag, "split": args.split, "model": Config.LLM_MODEL, "judge": JUDGE_MODEL,
        "n_done": len(rows), "n_planned": total,
        "n_answerable": len(ans), "n_unanswerable": len(un),
        "answer_correctness": mean([r.get("correct") for r in ans]),
        "faithfulness": mean([r.get("faithful") for r in answered]),
        "citation_accuracy": round(sum(r.get("supported", 0) for r in answered) / cited, 3) if cited else None,
        "answers_with_citation": mean([1 if r["n_citations"] else 0 for r in answered]),
        "idk_recall": mean([0 if r["answerable_pred"] else 1 for r in un]),
        "false_refusal_rate": mean([0 if r["answerable_pred"] else 1 for r in ans]),
        "latency_p50_ms": pct(lat, 50), "latency_p95_ms": pct(lat, 95),
        "avg_tokens": mean([r["tokens"] for r in rows]),
        "cost_per_request": round(sum(costs) / len(costs), 6) if costs else 0,
    }
    summary["cost_per_1k_requests"] = round(summary["cost_per_request"] * 1_000, 4)
    summary["cost_per_100k_requests"] = round(summary["cost_per_request"] * 100_000, 2)

    (RESULTS_DIR / f"generation_{args.tag}.json").write_text(json.dumps(summary, indent=2))
    md = ["| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items()]
    (RESULTS_DIR / f"generation_{args.tag}.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md))
    return summary


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(Config.DATA_EVAL / "questions_p*.jsonl"))
    ap.add_argument("--split", choices=["all", "dev", "test"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between questions")
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()

    questions = []
    for path in sorted(glob.glob(args.file)):
        with open(path, encoding="utf-8") as f:
            questions += [json.loads(l) for l in f if l.strip()]
    if not questions:
        raise SystemExit(f"No questions found at {args.file}")
    if not first(questions[0], "question", "q"):
        raise SystemExit(f"Cannot find the question field. Keys: {list(questions[0].keys())}")

    questions = [q for q in questions if in_split(first(q, "question", "q"), args.split)]
    if args.limit:
        questions = questions[: args.limit]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    details_path = RESULTS_DIR / f"generation_{args.tag}_details.jsonl"
    done: dict[str, dict] = {}
    if details_path.exists():
        with open(details_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    done[r["question"]] = r

    print(f"{len(questions)} questions | split={args.split} | model={Config.LLM_MODEL} | "
          f"judge={JUDGE_MODEL} | already done: {len(done)}")

    stopped = False
    with open(details_path, "a", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            text = first(q, "question", "q")
            if text in done:
                continue
            unans = is_unanswerable(q)
            try:
                resp = with_retry(lambda: answer(text))
                row = {"question": text, "unanswerable": unans, "answerable_pred": resp.answerable,
                       "answer": resp.answer, "n_citations": len(resp.citations),
                       "latency_ms": resp.latency_ms, "tokens": resp.tokens, "cost": resp.cost}
                if not unans and resp.answerable:
                    row.update(judge(q, resp))
                elif not unans:
                    row.update({"correct": 0, "faithful": None, "supported": 0})
            except DailyLimit as e:
                print(f"\nDaily token limit reached at question {i}. Progress is saved.\n"
                      f"Rerun the SAME command later to continue.\n{str(e)[:200]}")
                stopped = True
                break
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            done[text] = row
            print(f"[{i}/{len(questions)}] {'UNANS' if unans else 'ANS  '} "
                  f"{resp.latency_ms / 1000:5.1f}s ${resp.cost:.5f} | {text[:60]}")
            time.sleep(args.sleep)

    rows = [done[first(q, "question", "q")] for q in questions if first(q, "question", "q") in done]
    if rows:
        write_summary(rows, args, len(questions))
        if stopped:
            print("\n(partial summary: do not report these numbers until all questions are done)")
    print(f"\nSaved to {RESULTS_DIR}/generation_{args.tag}.*")


if __name__ == "__main__":
    main()