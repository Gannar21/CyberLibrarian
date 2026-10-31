#!/usr/bin/env python3
"""
Merge data/eval/questions_p1..p4.jsonl into data/eval/questions_all.jsonl.

tune on dev only; use test only for final numbers.

Validates every input file with validate.py, drops duplicate ids and
exact-duplicate question texts, prints per-file stats, then calls
eval/split.py to regenerate questions_dev.jsonl and questions_test.jsonl.

Exit code 0 = OK.  Exit non-zero if any file fails validation.
Warnings (not errors): total < 100, any file has zero unanswerable questions.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_EVAL  = REPO_ROOT / "data" / "eval"
OUT_FILE   = DATA_EVAL / "questions_all.jsonl"
VALIDATE   = DATA_EVAL / "validate.py"
SPLIT      = REPO_ROOT / "eval" / "split.py"


def _validate_file(qfile: Path, docs_arg: list[str]) -> int:
    """Run validate.py on *qfile*; return its exit code."""
    return subprocess.run(
        [sys.executable, str(VALIDATE), str(qfile)] + docs_arg,
    ).returncode


def run(
    data_eval_dir: Path = DATA_EVAL,
    out_file: Path = OUT_FILE,
    docs_arg: list[str] | None = None,
) -> None:
    """Core logic; separated from argparse so tests can call it directly."""
    if docs_arg is None:
        docs_arg = []

    # ── 1. discover input files ──────────────────────────────────────────────
    input_files = sorted(data_eval_dir.glob("questions_p*.jsonl"))
    if not input_files:
        print("ERROR: no questions_p*.jsonl files found")
        sys.exit(1)

    # ── 2. validate each file ────────────────────────────────────────────────
    print("-- Validation --")
    sys.stdout.flush()
    bad = 0
    for qfile in input_files:
        if _validate_file(qfile, docs_arg) != 0:
            bad += 1
    if bad:
        print(f"\n{bad} file(s) failed validation. Fix errors before merging.")
        sys.exit(1)

    # ── 3. load, deduplicate, merge ──────────────────────────────────────────
    all_questions: list[dict] = []
    seen_ids:   set[str] = set()
    seen_texts: set[str] = set()
    stats: dict[str, dict] = {}

    for qfile in input_files:
        raw = [
            json.loads(l)
            for l in qfile.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        types:    dict[str, int] = {}
        n_unans   = 0
        n_dropped = 0

        for q in raw:
            qid   = str(q.get("id", ""))
            qtext = q.get("question", "").strip().lower()

            if qid in seen_ids:
                print(f"  WARN {qfile.name}: dropping duplicate id '{qid}'")
                n_dropped += 1
                continue
            if qtext in seen_texts:
                print(f"  WARN {qfile.name}: dropping exact-duplicate question '{qid}'")
                n_dropped += 1
                continue

            seen_ids.add(qid)
            seen_texts.add(qtext)
            all_questions.append(q)

            t = q.get("type", "?")
            types[t] = types.get(t, 0) + 1
            if t == "unanswerable":
                n_unans += 1

        stats[qfile.name] = {
            "total": len(raw), "types": types,
            "unanswerable": n_unans, "dropped": n_dropped,
        }

    # ── 4. per-file table ────────────────────────────────────────────────────
    print("\n-- Per-file stats --")
    grand_total = 0
    for fname, s in stats.items():
        dropped_note = f"  (dropped {s['dropped']})" if s["dropped"] else ""
        print(f"  {fname}: {s['total']} q | {s['types']} | "
              f"unanswerable={s['unanswerable']}{dropped_note}")
        grand_total += s["total"]

    merged = len(all_questions)
    print(f"\n  Total across files : {grand_total}")
    print(f"  After deduplication: {merged}")

    # ── 5. warnings ──────────────────────────────────────────────────────────
    if merged < 100:
        print(f"\n  WARN: only {merged} questions; 100+ recommended")
    for fname, s in stats.items():
        if s["unanswerable"] == 0:
            print(f"  WARN: {fname} has no unanswerable questions")

    # ── 6. write questions_all.jsonl ─────────────────────────────────────────
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as fh:
        for q in all_questions:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"\nWrote {merged} questions to {out_file}")

    # ── 7. regenerate dev/test splits ────────────────────────────────────────
    print("\nRegenerating dev/test splits via eval/split.py ...")
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, str(SPLIT), "--input", str(out_file)],
    )
    if result.returncode != 0:
        print("ERROR: eval/split.py exited non-zero")
        sys.exit(1)

    print("\nAll done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge and validate question files.")
    parser.add_argument(
        "--docs", default=None,
        help="Path to documents.jsonl (passed through to validate.py)",
    )
    args = parser.parse_args()
    docs_arg = ["--docs", args.docs] if args.docs else []
    run(docs_arg=docs_arg)


if __name__ == "__main__":
    main()
