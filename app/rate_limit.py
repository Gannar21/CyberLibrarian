"""
Rate-limiting and input-validation middleware for the CyberLibrarian API.

Person 4 can add this to src/api/main.py without changing any other logic:

    from app.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

Limits enforced (all configurable via environment variables):
  - RATE_LIMIT_PER_HOUR (default 20): max questions per session token per hour
  - MAX_QUESTION_LEN    (default 500): max question length in characters

Session token comes from the X-Session-Id request header (set by the
Streamlit client).  Falls back to the client IP when no header is present.
IP is used only for rate-limiting; it is never stored or logged.

When a limit is exceeded the middleware returns a 429 JSON response with a
friendly message instead of forwarding to the endpoint.  Budget exhaustion
is signalled by the endpoint itself (503) not by this middleware.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_RATE_LIMIT  = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
_MAX_Q_LEN   = int(os.getenv("MAX_QUESTION_LEN",    "500"))
_WINDOW_SEC  = 3600   # 1 hour rolling window

# In-memory store: {identity: [(timestamp, …), …]}
# Fine for a single-process deployment; swap for Redis in multi-process setups.
_counts: dict[str, list[float]] = defaultdict(list)


def _identity(request: Request) -> str:
    """Return the session token from header, or fall back to client IP."""
    return (
        request.headers.get("x-session-id")
        or request.client.host   # type: ignore[union-attr]
        or "unknown"
    )


def _within_limit(identity: str) -> bool:
    """Slide the window and return True if the request is within quota."""
    now  = time.monotonic()
    hits = _counts[identity]
    # Expire entries older than the window.
    _counts[identity] = [t for t in hits if now - t < _WINDOW_SEC]
    if len(_counts[identity]) >= _RATE_LIMIT:
        return False
    _counts[identity].append(now)
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces rate limits and question-length cap."""

    async def dispatch(self, request: Request, call_next):
        # Only guard the /ask endpoint.
        if request.url.path != "/ask":
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

        # Rate-limit check.
        identity = _identity(request)
        if not _within_limit(identity):
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
