"""answer(question, filters, history) -> AnswerResponse  (Person 4)."""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache

from src.common.config import Config
from src.common.schemas import AnswerResponse, Citation
from src.generation.prompt import IDK_PHRASE, SYSTEM_PROMPT, build_user_prompt
from src.retrieval.retriever import retrieve

_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

# ---------------------------------------------------------------------------
# Normal conversation (no retrieval, no LLM call, zero cost)
# ---------------------------------------------------------------------------
_SMALLTALK = [
    (re.compile(r"^(hi|hello|hey|hola|salam|salut|bonjour|good (morning|afternoon|evening))\b"),
     "Hello! I'm CyberLibrarian. Ask me anything about OWASP, NIST or MITRE ATT&CK, "
     "and I'll answer with sources."),
    (re.compile(r"\b(thanks|thank you|merci|shukran)\b"),
     "You're welcome! Ask me another cybersecurity question anytime."),
    (re.compile(r"\bhow are you\b"),
     "I'm doing well, thanks! What cybersecurity topic can I help you with?"),
    (re.compile(r"\b(who are you|what are you|what can you do|how do you work)\b"),
     "I'm CyberLibrarian, a cybersecurity assistant. I search OWASP cheat sheets, NIST "
     "publications and MITRE ATT&CK, then answer using only those documents, with citations."),
    (re.compile(r"^(bye|goodbye|see you|au revoir)\b"),
     "Goodbye! Stay secure."),
]


def _smalltalk(question: str) -> str | None:
    low = question.lower().strip()
    if len(low.split()) > 8:
        return None
    for pattern, reply in _SMALLTALK:
        if pattern.search(low):
            return reply
    return None


def _effective_question(question: str, history: list[dict] | None) -> str:
    """Short follow-ups ('and how to prevent it?') borrow the previous user question."""
    if history and len(question.split()) <= 6:
        last_user = next((h["content"] for h in reversed(history) if h.get("role") == "user"), None)
        if last_user:
            return f"{last_user} {question}"
    return question


@lru_cache(maxsize=1)
def _doc_urls() -> dict[str, str]:
    """doc_id -> url, because Chunk does not carry the url."""
    urls: dict[str, str] = {}
    if Config.DOCUMENTS_JSONL.exists():
        with open(Config.DOCUMENTS_JSONL, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                urls[d["doc_id"]] = d.get("url", "")
    return urls


@lru_cache(maxsize=1)
def _client():
    from groq import Groq
    return Groq(api_key=Config.LLM_API_KEY)


def _cost(in_tok: int, out_tok: int) -> float:
    return (in_tok * Config.LLM_INPUT_PRICE_PER_MTOK
            + out_tok * Config.LLM_OUTPUT_PRICE_PER_MTOK) / 1_000_000


def _log(entry: dict) -> None:
    try:
        Config.REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(Config.REQUEST_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # logging must never break an answer


def _parse_citations(text: str, chunks) -> tuple[str, list[Citation]]:
    """Keep markers that point to a real source, drop invented ones, build Citation objects."""
    n = len(chunks)
    used: list[int] = []

    def fix(m: re.Match) -> str:
        ids = [int(x) for x in re.split(r"\s*,\s*", m.group(1))]
        valid = [i for i in ids if 1 <= i <= n]
        for i in valid:
            if i not in used:
                used.append(i)
        return "".join(f"[{i}]" for i in valid)

    clean = _CITE_RE.sub(fix, text)
    urls = _doc_urls()
    cites = []
    for i in sorted(used):
        c = chunks[i - 1].chunk
        cites.append(Citation(id=i, chunk_id=c.chunk_id, title=c.title, source=c.source,
                              section=c.section, url=urls.get(c.doc_id, "")))
    return clean, cites


def answer(question: str, filters: dict | None = None,
           history: list[dict] | None = None) -> AnswerResponse:
    t0 = time.perf_counter()

    chat_reply = _smalltalk(question)
    if chat_reply:
        return AnswerResponse(answer=chat_reply, citations=[], chunks=[], latency_ms=0,
                              tokens=0, cost=0.0, answerable=True)

    q = _effective_question(question, history)
    chunks = retrieve(q, k=Config.RERANK_TOP_N, filters=filters, rerank=Config.USE_RERANK)
    t1 = time.perf_counter()

    if not chunks:  # nothing found: skip the LLM call, save money
        _log({"q": question, "retrieval_ms": int((t1 - t0) * 1000), "gen_ms": 0,
              "tokens": 0, "cost": 0.0, "answerable": False})
        return AnswerResponse(answer=IDK_PHRASE, citations=[], chunks=[],
                              latency_ms=int((t1 - t0) * 1000), tokens=0, cost=0.0,
                              answerable=False)

    # Optional: lower reasoning effort for gpt-oss models (Week 8 optimisation).
    # Leave LLM_REASONING_EFFORT empty in .env to keep the baseline behaviour.
    effort = getattr(Config, "LLM_REASONING_EFFORT", "")
    extra = {"reasoning_effort": effort} if effort else {}

    msg = _client().chat.completions.create(
        model=Config.LLM_MODEL,
        max_tokens=Config.LLM_MAX_TOKENS,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(q, chunks)},
        ],
        **extra,
    )
    t2 = time.perf_counter()

    text = (msg.choices[0].message.content or "").strip()
    text = text.replace("【", "[").replace("】", "]")   # some models use full-width brackets
    in_tok, out_tok = msg.usage.prompt_tokens, msg.usage.completion_tokens
    answerable = not text.lower().startswith(IDK_PHRASE.lower()[:20])
    text, cites = _parse_citations(text, chunks) if answerable else (text, [])

    resp = AnswerResponse(
        answer=text, citations=cites, chunks=chunks,
        latency_ms=int((t2 - t0) * 1000), tokens=in_tok + out_tok,
        cost=_cost(in_tok, out_tok), answerable=answerable,
    )
    _log({"q": question, "filters": filters, "model": Config.LLM_MODEL,
          "reasoning_effort": effort or "default",
          "retrieval_ms": int((t1 - t0) * 1000), "gen_ms": int((t2 - t1) * 1000),
          "in_tokens": in_tok, "out_tokens": out_tok, "cost": resp.cost,
          "answerable": answerable, "n_citations": len(cites)})
    return resp