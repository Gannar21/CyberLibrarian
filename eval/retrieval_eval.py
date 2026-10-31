"""Retrieval eval + ablation.

    python -m eval.retrieval_eval                       # keyword / vector / hybrid
    python -m eval.retrieval_eval --full                # + hybrid+rerank (needs sentence-transformers)
    python -m eval.retrieval_eval --rewrite             # + hybrid+rerank+rewrite (needs an LLM key)

Writes eval/results/: ablation.md, ablation.json, failures.jsonl (for your failure-case notes).
A chunk counts as relevant if it covers >= OVERLAP of the gold passage's tokens (passage-level),
or, if a question has no passage, if it comes from the gold document (doc-level).
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import time
from pathlib import Path

from src.retrieval import retrieve
from src.retrieval.backend import chunk_meta, chunk_text, tokenize

KS = (1, 3, 5, 10)
OVERLAP = 0.6
PASSAGE_KEYS = ("source_passage", "passage", "gold_passage", "evidence", "context")
DOC_KEYS = ("source_doc", "doc_id", "document_id", "source_doc_id", "source_id")
RESULTS = Path("eval/results")


def load_questions(pattern: str) -> list[dict]:
    qs = []
    for path in sorted(glob.glob(pattern)):
        for line in Path(path).read_text().splitlines():
            if line.strip():
                qs.append(json.loads(line))
    return [q for q in qs if q.get("answerable", True) is not False and q.get("type") != "unanswerable"]


def _first(q, keys):
    for k in keys:
        if q.get(k):
            v = q[k]
            return v if isinstance(v, str) else " ".join(map(str, v))
    return None


def is_relevant(result_chunk, q: dict) -> bool:
    passage = _first(q, PASSAGE_KEYS)
    if passage:
        gold = set(tokenize(passage))
        if not gold:
            return False
        return len(gold & set(tokenize(chunk_text(result_chunk)))) / len(gold) >= OVERLAP
    doc = _first(q, DOC_KEYS)
    return bool(doc) and str(chunk_meta(result_chunk).get("doc_id")) == doc


def failure_type(q: dict) -> str:
    p = _first(q, PASSAGE_KEYS) or ""
    low = p.lower()
    if p.count("|") >= 4:
        return "table"
    if "```" in p or p.count("{") + p.count(";") >= 4:
        return "code"
    if any(w in low for w in ("see section", "refer to", "see also", "as described in")):
        return "cross-reference"
    if len(p) > 1500:
        return "long-passage"
    return "other"


def run_config(name, questions, **kw):
    hits = {k: 0 for k in KS}
    rr, lat, fails = [], [], []
    for q in questions:
        t0 = time.perf_counter()
        res = retrieve(q["question"], k=max(KS), **kw)
        lat.append((time.perf_counter() - t0) * 1000)
        chunks = [getattr(r, "chunk", r) for r in res]
        rel = [is_relevant(c, q) for c in chunks]
        for k in KS:
            hits[k] += any(rel[:k])
        rr.append(next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0))
        if not any(rel):
            fails.append({"config": name, "id": q.get("id"), "question": q["question"],
                          "type": failure_type(q),
                          "top3": [(chunk_meta(c).get("title"), chunk_text(c)[:120]) for c in chunks[:3]]})
    n = len(questions)
    lat_sorted = sorted(lat)
    return {
        "config": name, "n": n,
        **{f"recall@{k}": round(hits[k] / n, 3) for k in KS},
        "mrr": round(sum(rr) / n, 3),
        "latency_p50_ms": round(statistics.median(lat), 1),
        "latency_p95_ms": round(lat_sorted[min(n - 1, int(0.95 * n))], 1),
    }, fails


def to_markdown(rows) -> str:
    cols = ["config", "n"] + [f"recall@{k}" for k in KS] + ["mrr", "latency_p50_ms", "latency_p95_ms"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--questions",
        default="data/eval/questions_p*.jsonl",
        help="Glob pattern for evaluation question files.",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Add hybrid + reranker.",
    )
    ap.add_argument(
        "--rewrite",
        action="store_true",
        help="Add hybrid + reranker + rewrite.",
    )
    ap.add_argument(
        "--filters",
        default=None,
        help='JSON filters, e.g. \'{"source":"OWASP"}\'',
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. When provided, existing ablation "
             "files are not overwritten.",
    )
    a = ap.parse_args()

    qs = load_questions(a.questions)

    if not qs:
        raise ValueError(
            f"No answerable evaluation questions found: {a.questions}"
        )

    filters = json.loads(a.filters) if a.filters else None

    configs = [
        ("keyword only", dict(mode="keyword")),
        ("vector only", dict(mode="vector")),
        ("hybrid (RRF)", dict(mode="hybrid")),
    ]

    if a.full or a.rewrite:
        configs.append(
            ("hybrid + reranker", dict(mode="hybrid", rerank=True))
        )

    if a.rewrite:
        configs.append(
            (
                "hybrid + reranker + rewrite",
                dict(mode="hybrid", rerank=True, rewrite=True),
            )
        )

    rows, all_fails = [], []

    for name, kw in configs:
        row, fails = run_config(name, qs, filters=filters, **kw)
        rows.append(row)
        all_fails.extend(fails)
        print(f"done: {name}")

    table = to_markdown(rows)
    print("\n" + table)

    if a.output is not None:
        # Write only the requested JSON file.
        # Preserve the existing ablation results and failure reports.
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(
            json.dumps(rows, indent=2),
            encoding="utf-8",
        )
        print(f"\nResults saved to: {a.output}")

    else:
        # Preserve the original behavior when --output is omitted.
        RESULTS.mkdir(parents=True, exist_ok=True)

        (RESULTS / "ablation.json").write_text(
            json.dumps(rows, indent=2),
            encoding="utf-8",
        )
        (RESULTS / "ablation.md").write_text(
            table + "\n",
            encoding="utf-8",
        )
        (RESULTS / "failures.jsonl").write_text(
            "\n".join(json.dumps(f) for f in all_fails),
            encoding="utf-8",
        )

        by_type = {}
        for failure in all_fails:
            if failure["config"] == "hybrid (RRF)":
                kind = failure["type"]
                by_type[kind] = by_type.get(kind, 0) + 1

        print(
            "\nHybrid failure types (paste into your PR notes):",
            by_type or "none",
        )


if __name__ == "__main__":
    main()