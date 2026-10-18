"""
Owner: Person 2 (Indexing)

This module must provide functions that load the persisted vector and BM25
indexes that were built by build_index.py.  Callers (src.retrieval.*) import
these loaders; they must not hard-code index paths—use src.common.config.

Required public interface:
    def load_vector_index() -> Any:
        \"\"\"Return the vector index object (e.g. a chromadb.Collection).\"\"\"
        ...

    def load_bm25_index() -> Any:
        \"\"\"Return the BM25 index object (e.g. a rank_bm25.BM25Okapi).\"\"\"
        ...
"""
raise NotImplementedError("load.py must be implemented by Person 2")
