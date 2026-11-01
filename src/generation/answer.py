"""Owner: Person 4. Full RAG answer: retrieve -> prompt -> LLM -> parse citations."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from functools import lru_cache
from src.generation.answer_cache import AnswerCache
from src.common.config import REPO_ROOT, Config
from src.common.schemas import AnswerResponse, Citation, RetrievalResult
from src.generation.prompt import NO_ANSWER, build_prompt

LOG_PATH = REPO_ROOT / "logs" / "requests.jsonl"
MAX_TOKENS = 500
ANSWER_CACHE = AnswerCache(
    maxsize=Config.ANSWER_CACHE_MAXSIZE,
    ttl_seconds=Config.ANSWER_CACHE_TTL_SECONDS,
)
# Price in USD per 1 million tokens. Check Anthropic's pricing page for the
# model in LLM_MODEL and override in .env if these defaults are wrong.
PRICE_IN_PER_M = float(os.getenv("LLM_PRICE_INPUT_PER_M", "1.0"))
PRICE_OUT_PER_M = float(os.getenv("LLM_PRICE_OUTPUT_PER_M", "5.0"))


# ---------- 0a. small talk (no retrieval, no LLM call) ----------
# Patterns are matched against the WHOLE message after lowercasing and
# stripping punctuation (apostrophes removed: "how's" -> "hows").
_SMALL_TALK = [
    (
        re.compile(
            r"(hi+|hello+|hey+|hiya|yo|howdy|salam|bonjour|hola"
            r"|good (morning|afternoon|evening))( there| librarian| cyberlibrarian)?"
        ),
        "Hi there! 👋 I'm CyberLibrarian. Ask me anything about cybersecurity "
        "and I'll answer using OWASP, NIST and MITRE ATT&CK documents.",
    ),
    (
        re.compile(r"(how are you|how are you doing|hows it going|whats up|sup)"),
        "I'm doing great, thanks for asking! 😊 What cybersecurity question can I help with?",
    ),
    (
        re.compile(r"(who are you|what are you|what can you do|help|help me)"),
        "I'm CyberLibrarian, a cybersecurity assistant. I answer questions using OWASP cheat "
        "sheets, NIST publications and MITRE ATT&CK, and I always show my sources. "
        "Try: \"How do I prevent SQL injection?\"",
    ),
    (
        re.compile(r"(thanks|thank you|thx|ty|thank you so much)"),
        "You're welcome! 💙 Ask me another one anytime.",
    ),
    (
        re.compile(r"(bye|goodbye|see you|cya)"),
        "Bye! Stay secure. 🔐",
    ),
]


def small_talk_reply(question: str) -> str | None:
    """Return a friendly canned reply if the whole message is small talk, else None."""
    q = question.lower().replace("'", "").replace("\u2019", "")
    q = re.sub(r"[^\w\s]", "", q)
    q = re.sub(r"\s+", " ", q).strip()
    for pattern, reply in _SMALL_TALK:
        if pattern.fullmatch(q):
            return reply
    return None


# ---------- 0b. filters ----------
def normalize_filters(filters: dict | None) -> dict | None:
    """Translate the UI's year_min/year_max into the retriever's 'year' format."""
    if not filters:
        return None
    f = dict(filters)
    lo, hi = f.pop("year_min", None), f.pop("year_max", None)
    if lo is not None or hi is not None:
        f["year"] = {
            "min": lo if lo is not None else -10**9,
            "max": hi if hi is not None else 10**9,
        }
    return f or None


# ---------- 1. retrieval (lazy import so tests don't need torch) ----------
def _retrieve(question: str, k: int, filters: dict | None) -> list[RetrievalResult]:
    from src.retrieval.retriever import retrieve
    return retrieve(question, k=k, filters=filters)


# ---------- 2. LLM call ----------
def call_llm(prompt: str) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    if os.getenv("FAKE_LLM", "").lower() in ("1", "true", "yes"):
        return (
            "(fake LLM) This is a test answer based on the sources [1].",
            len(prompt) // 4,
            20,
        )

    key = Config.LLM_API_KEY or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Set LLM_API_KEY in .env (or FAKE_LLM=true to test without a key)"
        )

    from openai import OpenAI

    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=Config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )

    text = response.choices[0].message.content or ""
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0

    return text, input_tokens, output_tokens


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


def _answer_cache_key(
    question: str,
    filters: dict | None,
) -> str:
    """Create a stable cache key for a question and its settings."""
    payload = {
        "question": " ".join(question.strip().split()).casefold(),
        "filters": filters,
        "index_version": Config.INDEX_VERSION,
        "embedding_model": Config.EMBEDDING_MODEL,
        "chunk_size": Config.CHUNK_SIZE,
        "chunk_overlap": Config.CHUNK_OVERLAP,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------- 5. the main function ----------
def answer(question: str, filters: dict | None = None) -> AnswerResponse:
    """Run the RAG pipeline, reusing cached answers when enabled."""
    t0 = time.perf_counter()

    # 0. Greetings / small talk: answer directly, skip retrieval and the LLM.
    reply = small_talk_reply(question)
    if reply is not None:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return AnswerResponse(
            answer=reply,
            citations=[],
            chunks=[],
            latency_ms=latency_ms,
            tokens=0,
            cost=0.0,
            answerable=True,  # True so the UI doesn't show the "I don't know" banner
            cache_hit=False,
        )

    normalized = normalize_filters(filters)

    cache_enabled = Config.USE_CACHE
    cache_key = _answer_cache_key(question, normalized)

    # 1. Return a cached response if one is available.
    if cache_enabled:
        cached = ANSWER_CACHE.get(cache_key)

        if cached is not None:
            latency_ms = int((time.perf_counter() - t0) * 1000)

            log_request({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "question": question,
                "retrieval_ms": 0,
                "generation_ms": 0,
                "total_ms": latency_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "answerable": cached.answerable,
                "n_chunks": len(cached.chunks),
                "cache_hit": True,
            })

            return cached.model_copy(update={
                "latency_ms": latency_ms,
                "tokens": 0,
                "cost": 0.0,
                "cache_hit": True,
            })

    # 2. Cache miss: run the normal RAG pipeline.
    results = _retrieve(
        question,
        Config.RERANK_TOP_N,
        normalized,
    )
    t1 = time.perf_counter()

    if not results:
        text, in_tok, out_tok = NO_ANSWER, 0, 0
    else:
        text, in_tok, out_tok = call_llm(
            build_prompt(question, results)
        )

    t2 = time.perf_counter()

    answerable = (
        bool(results)
        and not text.strip().lower().startswith("i don't know")
    )
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
        "cache_hit": False,
    })

    response = AnswerResponse(
        answer=text,
        citations=citations,
        chunks=results,
        latency_ms=latency_ms,
        tokens=in_tok + out_tok,
        cost=cost,
        answerable=answerable,
        cache_hit=False,
    )

    # 3. Save the complete response for subsequent requests.
    if cache_enabled:
        ANSWER_CACHE.set(cache_key, response)

    return response