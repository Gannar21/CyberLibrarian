"""Find a passage in documents.jsonl and append a valid question line.

Search for passages:
    python -m eval.add_question find "prepared statement"

Add a question:
    python -m eval.add_question add p4-def-01 definition DOC_ID "Question?" "Answer." "exact passage"

Add an unanswerable question:
    python -m eval.add_question unans p4-unans-01 "What is the capital of France?"
"""
import json
import sys
from pathlib import Path

DOCS = Path("data/processed/documents.jsonl")
OUT = Path("data/eval/questions_p4.jsonl")


def find(term: str, limit: int = 5) -> None:
    n = 0
    for line in DOCS.open(encoding="utf-8"):
        d = json.loads(line)
        text = d["text"]
        i = text.lower().find(term.lower())
        if i >= 0:
            print(f"doc_id: {d['doc_id']}")
            print(f"passage: {text[max(0, i - 100): i + 300]!r}\n")
            n += 1
            if n >= limit:
                break
    if n == 0:
        print("no match")


def append(row: dict) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("added", row["id"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "find":
        find(sys.argv[2])
    elif cmd == "add":
        _, _, qid, qtype, doc, q, a, passage = sys.argv
        append({"id": qid, "question": q, "answer": a, "source_doc": doc,
                "source_passage": passage, "type": qtype})
    elif cmd == "unans":
        _, _, qid, q = sys.argv
        append({"id": qid, "question": q, "answer": "I don't know",
                "source_doc": "", "source_passage": "", "type": "unanswerable"})