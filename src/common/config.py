"""
Central configuration for CyberLibrarian.  Import Config from here; never
hardcode paths, model names, or numeric hyperparameters elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()   # reads .env if it exists; safe to call multiple times

# ---------------------------------------------------------------------------
# Repo root – all paths are relative to this so the project works from any cwd
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent


class Config:
    # ---- Paths ----------------------------------------------------------------
    DATA_RAW: Path = REPO_ROOT / "data" / "raw"
    DATA_PROCESSED: Path = REPO_ROOT / "data" / "processed"
    DATA_SAMPLE: Path = REPO_ROOT / "data" / "sample"
    DATA_EVAL: Path = REPO_ROOT / "data" / "eval"

    DOCUMENTS_JSONL: Path = DATA_PROCESSED / "documents.jsonl"
    SAMPLE_JSONL: Path = DATA_SAMPLE / "documents_sample.jsonl"
    EVAL_QUESTIONS: Path = DATA_EVAL / "questions_p1.jsonl"
    FEEDBACK_JSONL: Path = REPO_ROOT / "data" / "feedback.jsonl"
    REQUEST_LOG: Path = REPO_ROOT / "data" / "requests.jsonl"

    # Index artifacts (gitignored)
    INDEXES_DIR: Path = REPO_ROOT / "indexes"
    BM25_INDEX: Path = INDEXES_DIR / "bm25.pkl"
    VECTOR_INDEX_DIR: Path = REPO_ROOT / "chroma"

    # ---- Chunking (Person 2 uses these) ---------------------------------------
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))

    # ---- Embeddings -----------------------------------------------------------
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # ---- Retrieval ------------------------------------------------------------
    TOP_K: int = int(os.getenv("TOP_K", "10"))       # candidates before rerank
    RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "5"))  # chunks sent to the LLM
    USE_RERANK: bool = os.getenv("USE_RERANK", "true").lower() not in ("false", "0", "no")

    # ---- LLM (Groq) -----------------------------------------------------------
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    # gpt-oss models spend tokens "thinking", so keep this generous
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    # "", "low", "medium" or "high". Empty = model default (the baseline).
    LLM_REASONING_EFFORT: str = os.getenv("LLM_REASONING_EFFORT", "")
    # USD per million tokens: verify against the Groq pricing page for your model
    LLM_INPUT_PRICE_PER_MTOK: float = float(os.getenv("LLM_INPUT_PRICE_PER_MTOK", "0.15"))
    LLM_OUTPUT_PRICE_PER_MTOK: float = float(os.getenv("LLM_OUTPUT_PRICE_PER_MTOK", "0.75"))
    # Model used by eval/generation_eval.py to grade answers (a separate model
    # keeps its tokens out of the generator's daily budget)
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "openai/gpt-oss-20b")

    # ---- API / UI -------------------------------------------------------------
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    # Set USE_MOCK=false in .env to route to the real FastAPI backend
    USE_MOCK: bool = os.getenv("USE_MOCK", "true").lower() not in ("false", "0", "no")