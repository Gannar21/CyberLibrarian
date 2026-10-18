"""Draft Q&A pairs from random chunks with an LLM, for YOU to review and fix.

    python -m eval.draft_questions --n 30 --out data/eval/questions_p3.jsonl

Delete bad questions, rewrite vague ones, keep each answerable from its passage alone.
Then run: python data/eval/validate.py data/eval/questions_p3.jsonl
Adjust the row fields below if your validate.py expects other names.
"""
from __future__ import annotations

import argparse
import json
import random

from src.retrieval import backend
from src.retrieval.rewrite import complete

PROMPT = """Passage from a cybersecurity document:
\"\"\"{p}\"\"\"
Write ONE question a security student might ask that this passage answers, and a short answer.
Return ONLY JSON: {{"question": "...", "answer": "..."}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", default="data/eval/questions_p3.jsonl")
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    random.seed(a.seed)
    chunks = [c for c in backend.all_chunks().values() if 300 < len(backend.chunk_text(c)) < 1500]
    rows = []
    for i, c in enumerate(random.sample(chunks, min(a.n, len(chunks))), start=1):
        text = backend.chunk_text(c)
        try:
            raw = complete(PROMPT.format(p=text)).strip().strip("`")
            qa = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except Exception:
            continue
        meta = backend.chunk_meta(c)
        rows.append({"id": f"p3-{i:03d}", "question": qa["question"], "answer": qa["answer"],
                     "source_passage": text, "source_doc": meta.get("doc_id"), "type": "definition"})
    with open(a.out, "w") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"wrote {len(rows)} drafts to {a.out} -- now REVIEW every one by hand")


if __name__ == "__main__":
    main()
