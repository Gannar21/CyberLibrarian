"""Cost model from the request log.
    python -m eval.cost_model --users 50 --per-day 5 [--log data/requests.jsonl]"""
from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "requests.jsonl"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def norm(r: dict) -> dict:
    tin, tout = r.get("in_tokens", 0), r.get("out_tokens", 0)
    tokens = tin + tout if (tin or tout) else r.get("tokens", 0)
    ret, gen = r.get("retrieval_ms", 0), r.get("gen_ms", 0)
    cached = bool(r.get("cached"))
    return {"ret": ret, "gen": gen, "total": ret + gen, "tokens": tokens,
            "cost": r.get("cost", 0.0), "cached": cached,
            "llm": tokens > 0 and not cached, "skipped": r.get("skipped")}


def lat(rows, key):
    if not rows:
        return "n/a"
    xs = [r[key] for r in rows]
    return f"p50 {pct(xs, 50):.0f} / p95 {pct(xs, 95):.0f} ms"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(DEFAULT))
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--per-day", type=float, default=5, help="requests per user per day")
    ap.add_argument("--scale", type=int, default=100)
    ap.add_argument("--hosting-month", type=float, default=0.0, help="fixed USD/month today")
    ap.add_argument("--hosting-month-scaled", type=float, default=None,
                    help="fixed USD/month at scale (default: 10x today's, a rough guess)")
    a = ap.parse_args()

    rows = [norm(json.loads(line)) for line in open(a.log, encoding="utf-8") if line.strip()]
    if not rows:
        raise SystemExit("request log is empty")
    llm = [r for r in rows if r["llm"]]
    hits = sum(r["cached"] for r in rows)
    free = len(rows) - len(llm) - hits
    cost_all = st.mean(r["cost"] for r in rows)
    cost_llm = st.mean(r["cost"] for r in llm) if llm else 0.0
    tok_llm = st.mean(r["tokens"] for r in llm) if llm else 0.0

    reqs = a.users * a.per_day * 30
    llm_today, llm_scaled = reqs * cost_all, reqs * cost_all * a.scale
    host_scaled = (a.hosting_month_scaled if a.hosting_month_scaled is not None
                   else a.hosting_month * 10)
    skipped = [r["skipped"] for r in llm if r["skipped"] is not None]
    skip_line = (f"\nReranker skipped on {sum(skipped)}/{len(skipped)} LLM requests"
                 if skipped else "")

    print(f"""# Cost model ({a.log})
Requests: {len(rows)} | answered by the LLM: {len(llm)} | cache hits: {hits} | free (small talk / don't know): {free}{skip_line}

Latency, LLM-answered requests: retrieval {lat(llm, 'ret')} | generation {lat(llm, 'gen')} | total {lat(llm, 'total')}
Latency, all requests: total {lat(rows, 'total')}

Per LLM request: {tok_llm:.0f} tokens, ${cost_llm:.5f}
Per request, all traffic (includes free ones): ${cost_all:.5f}

| Scale | Requests/month | LLM $/month | Hosting $/month | Total $/month |
|---|---|---|---|---|
| Today ({a.users} users x {a.per_day:g}/day) | {reqs:,.0f} | {llm_today:.2f} | {a.hosting_month:.2f} | {llm_today + a.hosting_month:.2f} |
| {a.scale}x | {reqs * a.scale:,.0f} | {llm_scaled:.2f} | {host_scaled:.2f} | {llm_scaled + host_scaled:.2f} |

Assumptions: reranker and embeddings run locally ($0 per request); the LLM is billed per token at the
prices in config.py; the traffic mix and cache hit rate stay the same at {a.scale}x (conservative: the
hit rate should rise). At {a.scale}x, API rate limits matter more than the bill: check your tier.
""")


if __name__ == "__main__":
    main()