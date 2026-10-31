"""
Rate-limiting and input-validation middleware for the CyberLibrarian API.

Person 4 can add this to src/api/main.py without changing any other logic:

    from app.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

Limits enforced (all configurable via environment variables):
  - RATE_LIMIT_PER_HOUR (default 20): max questions per session token per hour
  - MAX_QUESTION_LEN    (default 500): max question length in characters

Identity resolution (in priority order):
  1. X-Session-Id request header  — used as the primary rate-limit key
  2. X-Forwarded-For header        — used ONLY when TRUST_PROXY=true
  3. client.host                   — raw TCP peer address

Loopback addresses (127.0.0.1, ::1) skip the per-IP check entirely; they
represent Streamlit calling the API from inside the same container and should
not be penalised by the IP window.  The per-session limit still applies if
X-Session-Id is present.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_RATE_LIMIT   = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
_MAX_Q_LEN    = int(os.getenv("MAX_QUESTION_LEN",    "500"))
_TRUST_PROXY  = os.getenv("TRUST_PROXY", "false").lower() in ("true", "1", "yes")
_WINDOW_SEC   = 3600   # 1 hour rolling window
_LOOPBACK     = {"127.0.0.1", "::1"}

# In-memory store: {identity: [timestamp, …]}
# Fine for a single-process deployment; swap for Redis in multi-process setups.
_counts: dict[str, list[float]] = defaultdict(list)


def _session_id(request: Request) -> str | None:
    return request.headers.get("x-session-id") or None


def _ip(request: Request) -> str:
    """Return the effective client IP, respecting TRUST_PROXY."""
    if _TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    host = getattr(request.client, "host", None) or ""
    return host


def _within_limit(identity: str) -> bool:
    """Slide the window and return True if the request is within quota."""
    now  = time.monotonic()
    hits = _counts[identity]
    _counts[identity] = [t for t in hits if now - t < _WINDOW_SEC]
    if len(_counts[identity]) >= _RATE_LIMIT:
        return False
    _counts[identity].append(now)
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces rate limits and question-length cap.

    Pass ``protected_path`` to guard a non-default path (e.g. ``/api/ask``).
    Defaults to ``/ask`` so existing Person 4 wiring is unchanged.
    """

    def __init__(self, app, protected_path: str = "/ask", **kwargs):
        super().__init__(app, **kwargs)
        self._protected_path = protected_path

    async def dispatch(self, request: Request, call_next):
        if request.url.path != self._protected_path:
            return await call_next(request)

        # Question-length check (parse body without consuming the stream).
        try:
            body = await request.json()
            question = body.get("question", "")
        except Exception:
            question = ""

        if len(question) > _MAX_Q_LEN:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        f"Question exceeds the {_MAX_Q_LEN}-character limit "
                        f"({len(question)} chars). Please shorten your question."
                    )
                },
            )

        # Per-session rate limit (if X-Session-Id is present).
        session = _session_id(request)
        if session and not _within_limit(session):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"You have reached the limit of {_RATE_LIMIT} questions "
                        f"per hour. Please try again later."
                    )
                },
            )

        # Per-IP rate limit — skip for loopback (Streamlit inside the container).
        ip = _ip(request)
        if ip and ip not in _LOOPBACK:
            if not session:
                # Only apply IP limit when there is no session token.
                if not _within_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": (
                                f"You have reached the limit of {_RATE_LIMIT} questions "
                                f"per hour. Please try again later."
                            )
                        },
                    )

        return await call_next(request)
