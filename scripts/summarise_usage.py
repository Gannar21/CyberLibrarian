#!/usr/bin/env python3
"""
Summarise data/usage_log.jsonl and data/feedback.jsonl.

Prints: unique sessions, total questions, thumbs-up/down counts,
downvoted questions, p50 and p95 latency, total estimated cost.

Optional CSV export of downvoted questions in the failures_template format:
    python scripts/summarise_usage.py --csv failures_round1.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent
USAGE_LOG    = REPO_ROOT / "data" / "usage_log.jsonl"
FEEDBACK_LOG = REPO_ROOT / "data" / "feedback.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise usage and feedback logs.")
    parser.add_argument(
        "--csv", metavar="FILE", default=None,
        help="Export downvoted questions to FILE in failures_template format",
    )
    args = parser.parse_args()

    usage    = _load_jsonl(USAGE_LOG)
    feedback = _load_jsonl(FEEDBACK_LOG)

    if not usage and not feedback:
        print("No data found. Run the app and ask some questions first.")
        sys.exit(0)

    # ── usage_log stats ──────────────────────────────────────────────────────
    sessions  = len({r.get("session_id") for r in usage if r.get("session_id")})
    latencies = [r["latency_ms"] for r in usage if isinstance(r.get("latency_ms"), (int, float))]
    total_cost = sum(r.get("cost", 0.0) for r in usage)

    p50 = statistics.median(latencies) if latencies else 0
    p95 = (
        sorted(latencies)[int(len(latencies) * 0.95)]
        if len(latencies) >= 2
        else (latencies[0] if latencies else 0)
    )

    # ── feedback stats ───────────────────────────────────────────────────────
    thumbs_up   = sum(1 for r in feedback if r.get("rating") == "up")
    thumbs_down = sum(1 for r in feedback if r.get("rating") == "down")
    downvoted   = [r for r in feedback if r.get("rating") == "down"]

    print(f"Sessions        : {sessions}")
    print(f"Questions logged: {len(usage)}")
    print(f"Thumbs up       : {thumbs_up}")
    print(f"Thumbs down     : {thumbs_down}")
    print(f"Latency p50     : {p50:.0f} ms")
    print(f"Latency p95     : {p95:.0f} ms")
    print(f"Total cost      : ${total_cost:.4f}")

    if downvoted:
        print(f"\nDownvoted questions ({len(downvoted)}):")
        for r in downvoted:
            print(f"  - {r.get('question', '')[:120]}")
            if r.get("comment"):
                print(f"    comment: {r['comment']}")

    # ── optional CSV export ──────────────────────────────────────────────────
    if args.csv:
        out_path = Path(args.csv)
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["round", "question", "expected", "what_happened",
                            "failure_type", "notes"],
            )
            writer.writeheader()
            for r in downvoted:
                writer.writerow({
                    "round":        r.get("round", ""),
                    "question":     r.get("question", ""),
                    "expected":     "",
                    "what_happened": r.get("comment", ""),
                    "failure_type": "other",
                    "notes":        "",
                })
        print(f"\nExported {len(downvoted)} downvoted question(s) to {out_path}")


if __name__ == "__main__":
    main()
