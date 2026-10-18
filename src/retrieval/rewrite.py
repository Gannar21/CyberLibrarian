"""Query rewriting + a tiny LLM helper (Anthropic or OpenAI, from env vars)."""
from __future__ import annotations

import json
import os


def complete(prompt: str, max_tokens: int = 400) -> str:
    import anthropic
    from src.common.config import Config
    key = Config.LLM_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set LLM_API_KEY in .env to use LLM features")
    r = anthropic.Anthropic(api_key=key).messages.create(
        model=Config.LLM_MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}])
    return r.content[0].text


PROMPT = """You help a search engine over cybersecurity documents (OWASP, NIST, MITRE ATT&CK).
Rewrite the user question into 1-3 standalone search queries. Expand acronyms and add key terms
if the question is short or vague; split multi-part questions into one query per part.
Return ONLY a JSON list of strings.

Question: {q}"""


def rewrite_query(query: str) -> list[str]:
    """Returns [original, *rewrites]. Falls back to [original] on any failure."""
    try:
        text = complete(PROMPT.format(q=query)).strip().strip("`")
        text = text[text.index("["): text.rindex("]") + 1]
        extra = [s for s in json.loads(text) if isinstance(s, str) and s.strip()]
    except Exception:
        extra = []
    seen, out = set(), []
    for q in [query, *extra][:4]:
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out
