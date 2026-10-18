"""
Owner: Person 3 (Retrieval)

This script must evaluate retrieval quality using the Q&A pairs in
data/eval/questions_p1.jsonl (or another eval file passed as an argument).

Metrics to compute:
    - Recall@k for k = 1, 3, 5, 10
      (was the correct source_doc in the top-k retrieved chunks?)
    - Mean search latency in milliseconds

Relevant signatures (from src.common.schemas):
    retrieve(query: str, k: int = 5, filters: dict | None = None)
        -> list[RetrievalResult]

    class RetrievalResult(BaseModel):
        chunk: Chunk
        score: float

    class Chunk(BaseModel):
        doc_id: str
        ...

Usage:
    python eval/retrieval_eval.py [--eval-file data/eval/questions_p1.jsonl]

Output:
    Print a table of Recall@k values and mean latency.
    Write results to eval/results/<timestamp>.json.
"""
raise NotImplementedError("retrieval_eval.py must be implemented by Person 3")
