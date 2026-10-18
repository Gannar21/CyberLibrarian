"""
Owner: Person 2 (Indexing)

This script must:
  - Read data/processed/documents.jsonl (one Document JSON per line).
  - Call src.indexing.chunker to split each Document into Chunks.
  - Build and persist a vector (dense) index from the Chunks.
  - Build and persist a BM25 (sparse) index from the Chunks.
  - Save both indexes to paths defined in src.common.config.

Relevant schemas (from src.common.schemas):
  Document  – the unit read from documents.jsonl
  Chunk     – the unit stored in both indexes

Usage:
    python build_index.py

Expected side-effects:
    indexes/bm25.pkl   (or path from config)
    indexes/chroma/    (or path from config)
"""
raise NotImplementedError("build_index.py must be implemented by Person 2")
