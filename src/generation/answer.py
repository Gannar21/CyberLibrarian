"""Owner: Person 4. Full RAG answer: retrieve -> prompt -> LLM -> parse citations."""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache

from src.common.config import REPO_ROOT, Config
from src.common.schemas import AnswerResponse, Citation, RetrievalResult
from src.generation.prompt import NO_ANSWER, build_prompt

LOG_PATH = REPO_ROOT / "logs" / "requests.jsonl"
MAX_TOKENS = 500

# Price in USD per 1 million tokens. Check Anthropic's pricing page for the
# model in LLM_MODEL and override in .env if these defaults are wrong.
PRICE_IN_PER_M = float(os.getenv("LLM_PRICE_INPUT_PER_M", "1.0"))
PRICE_OUT_PER_M = float(os.getenv("LLM_PRICE_OUTPUT_PER_M", "5.0"))


# ---------- 1. retrieval (lazy import so tests don't need torch) ----------
def _retrieve(question: str, k: int, filters: dict | None) -> list[RetrievalResult]:
    from src.retrieval.retriever import retrieve
    return retrieve(question, k=k, filters=filters)


# ---------- 2. LLM call ----------
def call_llm(prompt: str) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    if os.getenv("FAKE_LLM", "").lower() in ("1", "true", "yes"):
        return "(fake LLM) This is a test answer based on the sources [1].", len(prompt) // 4, 20

    key = Config.LLM_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set LLM_API_KEY in .env (or FAKE_LLM=true to test without a key)")
    import anthropic

    r = anthropic.Anthropic(api_key=key).messages.create(
        model=Config.LLM_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text, r.usage.input_tokens, r.usage.output_tokens


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_IN_PER_M + output_tokens * PRICE_OUT_PER_M) / 1_000_000


# ---------- 3. citations ----------
@lru_cache(maxsize=1)
def _doc_urls() -> dict[str, str]:
    """Map doc_id -> url, because Chunk has no url field."""
    path = Config.DOCUMENTS_JSONL if Config.DOCUMENTS_JSONL.exists() else Config.SAMPLE_JSONL
    urls: dict[str, str] = {}
    if not path.exists():
        return urls
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                urls[d["doc_id"]] = d.get("url", "")
            except (ValueError, KeyError):
                continue
    return urls


def parse_citations(text: str, results: list[RetrievalResult]) -> list[Citation]:
    """Find [1], [2], [1, 2] markers in text and build Citation objects."""
    seen: list[int] = []
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", text):
        for num in group.split(","):
            n = int(num)
            if 1 <= n <= len(results) and n not in seen:
                seen.append(n)

    urls = _doc_urls()
    citations = []
    for n in seen:
        c = results[n - 1].chunk
        citations.append(Citation(
            id=n, chunk_id=c.chunk_id, title=c.title, source=c.source,
            section=c.section, url=urls.get(c.doc_id, ""),
        ))
    return citations


# ---------- 4. logging ----------
def log_request(record: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # logging must never break an answer


# ---------- 5. the main function ----------
def answer(question: str, filters: dict | None = None) -> AnswerResponse:
    """Run the full RAG pipeline: retrieve -> prompt -> generate -> parse."""
    t0 = time.perf_counter()
    results = _retrieve(question, Config.RERANK_TOP_N, filters)
    t1 = time.perf_counter()

    if not results:
        text, in_tok, out_tok = NO_ANSWER, 0, 0
    else:
        text, in_tok, out_tok = call_llm(build_prompt(question, results))
    t2 = time.perf_counter()

    answerable = bool(results) and not text.strip().lower().startswith("i don't know")
    citations = parse_citations(text, results) if answerable else []
    cost = compute_cost(in_tok, out_tok)
    latency_ms = int((t2 - t0) * 1000)

    log_request({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "question": question,
        "retrieval_ms": int((t1 - t0) * 1000),
        "generation_ms": int((t2 - t1) * 1000),
        "total_ms": latency_ms,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost": cost,
        "answerable": answerable,
        "n_chunks": len(results),
    })

    return AnswerResponse(
        answer=text, citations=citations, chunks=results,
        latency_ms=latency_ms, tokens=in_tok + out_tok, cost=cost, answerable=answerable,
    )