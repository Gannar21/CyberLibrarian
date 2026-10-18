#!/usr/bin/env python3
"""
Validate a CyberLibrarian eval question file.

Each line must be a JSON object matching EvalQuestion:
  id             – unique string identifier
  question       – question text
  answer         – expected answer (or "I don't know" for unanswerable)
  source_doc     – doc_id of the supporting document
  source_passage – exact passage from that document
  type           – one of: definition, procedure, multi-part, time-based, unanswerable

Usage
-----
    python data/eval/validate.py <questions_file> [--docs <documents_jsonl>]

Exit code 0 = all checks pass; non-zero = at least one error found.

The --docs path defaults to data/processed/documents.jsonl and falls back to
data/sample/documents_sample.jsonl if the first does not exist.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DOCS = REPO_ROOT / "data" / "processed" / "documents.jsonl"
FALLBACK_DOCS = REPO_ROOT / "data" / "sample" / "documents_sample.jsonl"

QuestionType = Literal["definition", "procedure", "multi-part", "time-based", "unanswerable"]


class EvalQuestion(BaseModel):
    id: str
    question: str
    answer: str
    source_doc: str        # doc_id; may be empty for unanswerable
    source_passage: str    # exact passage; may be empty for unanswerable
    type: QuestionType


def _normalise(text: str) -> str:
    """Collapse whitespace for fuzzy passage matching."""
    return re.sub(r"\s+", " ", text).strip()


def _load_documents(docs_path: Path) -> dict[str, str]:
    """Return {doc_id: text} for all documents in the JSONL file."""
    docs: dict[str, str] = {}
    with open(docs_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            import json
            obj = json.loads(line)
            docs[obj["doc_id"]] = obj["text"]
    return docs


def validate_file(questions_path: Path, docs_path: Path) -> int:
    """Validate *questions_path* against *docs_path*.

    Prints one error line per problem.
    Returns the total number of errors found.
    """
    # Load documents once for passage checks
    doc_texts: dict[str, str] = {}
    if docs_path.exists():
        print(f"Checking passages against {docs_path}")
        doc_texts = _load_documents(docs_path)
    else:
        print(f"WARNING: documents file not found at {docs_path}; skipping passage checks")

    errors = 0
    seen_ids: set[str] = set()

    with open(questions_path, encoding="utf-8") as fh:
        for line_num, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            # 1. Valid JSON
            try:
                import json
                data = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                print(f"  Line {line_num}: invalid JSON – {exc}")
                errors += 1
                continue

            # 2. Valid Pydantic model
            try:
                q = EvalQuestion.model_validate(data)
            except ValidationError as exc:
                for err in exc.errors():
                    field = ".".join(str(x) for x in err["loc"])
                    print(f"  Line {line_num}: field '{field}' – {err['msg']}")
                errors += len(exc.errors())
                continue

            # 3. Unique ID
            if q.id in seen_ids:
                print(f"  Line {line_num}: duplicate id '{q.id}'")
                errors += 1
            seen_ids.add(q.id)

            # Unanswerable questions do not require source_doc / source_passage
            if q.type == "unanswerable":
                continue

            # 4. source_doc exists in documents file
            if doc_texts and q.source_doc not in doc_texts:
                print(f"  Line {line_num} (id={q.id}): source_doc '{q.source_doc}' not found in documents")
                errors += 1
                continue

            # 5. source_passage appears in the document (whitespace-normalised)
            if doc_texts and q.source_doc in doc_texts:
                doc_norm = _normalise(doc_texts[q.source_doc])
                passage_norm = _normalise(q.source_passage)
                if passage_norm and passage_norm not in doc_norm:
                    print(
                        f"  Line {line_num} (id={q.id}): source_passage not found in document "
                        f"'{q.source_doc}' (first 60 chars: {q.source_passage[:60]!r})"
                    )
                    errors += 1

    return errors


def _resolve_docs_path(given: str | None) -> Path:
    if given:
        return Path(given)
    if DEFAULT_DOCS.exists():
        return DEFAULT_DOCS
    if FALLBACK_DOCS.exists():
        print(f"Note: full documents.jsonl not found; using sample at {FALLBACK_DOCS}")
        return FALLBACK_DOCS
    return DEFAULT_DOCS  # will trigger "not found" warning in validate_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a CyberLibrarian eval question file")
    parser.add_argument("questions_file", help="Path to the JSONL question file to validate")
    parser.add_argument("--docs", help="Path to documents.jsonl (defaults to data/processed/documents.jsonl)")
    args = parser.parse_args()

    questions_path = Path(args.questions_file)
    if not questions_path.exists():
        print(f"ERROR: questions file not found: {questions_path}")
        sys.exit(1)

    docs_path = _resolve_docs_path(args.docs)

    print(f"Validating {questions_path} ...")
    n_errors = validate_file(questions_path, docs_path)

    if n_errors == 0:
        print(f"OK – all questions valid.")
        sys.exit(0)
    else:
        print(f"\n{n_errors} error(s) found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
