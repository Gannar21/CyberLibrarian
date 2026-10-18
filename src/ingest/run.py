"""
Ingest runner: load all sources, write data/processed/documents.jsonl.

Usage
-----
    python -m src.ingest.run             # full corpus
    python -m src.ingest.run --sample    # also write data/sample/documents_sample.jsonl

Output
------
    data/processed/documents.jsonl   – one Document JSON per line
    data/sample/documents_sample.jsonl  (--sample only, ~10 docs, committed to git)

Counts per source, total documents, total characters, and approximate page count
(assuming 3 000 chars/page) are printed at the end.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from src.common.config import Config
from src.common.schemas import Document
from src.ingest.attack_loader import load_attack_documents
from src.ingest.markdown_loader import load_owasp_documents
from src.ingest.pdf_loader import load_nist_documents

CHARS_PER_PAGE = 3_000   # rough approximation used for page-count estimate
SAMPLE_SIZE = 10          # docs written to the sample file


def _load_all() -> dict[str, list[Document]]:
    """Run every loader and return results keyed by source name."""
    results: dict[str, list[Document]] = {}
    raw = Config.DATA_RAW

    for source, loader, label in [
        ("owasp", lambda: load_owasp_documents(raw), "OWASP Markdown"),
        ("nist",  lambda: load_nist_documents(raw),   "NIST PDFs"),
        ("mitre", lambda: load_attack_documents(raw),  "MITRE ATT&CK"),
    ]:
        print(f"Loading {label}...")
        try:
            docs = loader()
            results[source] = docs
            print(f"  {source}: {len(docs)} documents")
        except FileNotFoundError as exc:
            print(f"  {source}: SKIPPED – {exc}")
            results[source] = []

    return results


def _pick_sample(docs_by_source: dict[str, list[Document]], n: int) -> list[Document]:
    """Pick a balanced sample of ~n documents across sources."""
    sources = [s for s, docs in docs_by_source.items() if docs]
    per_source = max(1, n // len(sources))
    sample: list[Document] = []
    for docs in docs_by_source.values():
        # Use first few docs (deterministic) rather than random, for reproducibility
        sample.extend(docs[:per_source])
    return sample[:n]


def main(sample: bool = False) -> None:
    docs_by_source = _load_all()

    all_docs: list[Document] = []
    for source_docs in docs_by_source.values():
        all_docs.extend(source_docs)

    if not all_docs:
        print("No documents loaded. Run  python data/download_corpus.py  first.")
        sys.exit(1)

    # Write full corpus
    Config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(Config.DOCUMENTS_JSONL, "w", encoding="utf-8") as fh:
        for doc in all_docs:
            fh.write(doc.to_jsonl() + "\n")
    print(f"\nWrote {len(all_docs)} documents to {Config.DOCUMENTS_JSONL}")

    # Write sample
    if sample:
        Config.DATA_SAMPLE.mkdir(parents=True, exist_ok=True)
        sample_docs = _pick_sample(docs_by_source, SAMPLE_SIZE)
        with open(Config.SAMPLE_JSONL, "w", encoding="utf-8") as fh:
            for doc in sample_docs:
                fh.write(doc.to_jsonl() + "\n")
        print(f"Wrote {len(sample_docs)} sample documents to {Config.SAMPLE_JSONL}")

    # Summary statistics
    total_chars = sum(len(doc.text) for doc in all_docs)
    approx_pages = total_chars // CHARS_PER_PAGE

    print("\n" + "=" * 50)
    print("INGEST SUMMARY")
    print("=" * 50)
    for source, docs in docs_by_source.items():
        chars = sum(len(d.text) for d in docs)
        print(f"  {source:8s}  {len(docs):5d} docs  {chars:10,} chars")
    print(f"  {'TOTAL':8s}  {len(all_docs):5d} docs  {total_chars:10,} chars")
    print(f"  Approximate page count: ~{approx_pages:,} pages")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CyberLibrarian ingest pipeline")
    parser.add_argument("--sample", action="store_true", help="Also write documents_sample.jsonl")
    args = parser.parse_args()
    main(sample=args.sample)
