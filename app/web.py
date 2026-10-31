"""
CyberLibrarian – modern web UI server.

Run in mock mode (no LLM key needed):
    USE_MOCK=true uvicorn app.web:app --port 8501 --reload

Run against the real backend:
    USE_MOCK=false API_URL=http://localhost:8000 uvicorn app.web:app --port 8501

Environment variables:
  PORT             Listen port (default 8501; uvicorn overrides via --port)
  USE_MOCK         true/false (default true)
  API_URL          Backend URL (default http://localhost:8000)
  ADMIN_MODE       true → enables /api/admin/download/* routes
  TEST_ROUND       Tag appended to usage-log entries
  TRUST_PROXY      true → trust X-Forwarded-For for rate limiting
  RATE_LIMIT_PER_HOUR  (default 20)
  MAX_QUESTION_LEN     (default 500)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.client import ask
from app.rate_limit import RateLimitMiddleware
from app.utils import USAGE_LOG, chunk_url_from_citations, log_usage, new_session_id, save_feedback
from src.common.config import Config

_WEB_DIR = Path(__file__).parent / "web"

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)

# Load 4 answerable example questions at startup (no network, local file).
_EXAMPLE_QUESTIONS: list[str] = []
_eq_path = Config.EVAL_QUESTIONS
if _eq_path.exists():
    with _eq_path.open(encoding="utf-8") as _f:
        for _line in _f:
            try:
                _q = json.loads(_line)
                if _q.get("type") in ("definition", "procedure") and _q.get("question"):
                    _EXAMPLE_QUESTIONS.append(_q["question"])
                    if len(_EXAMPLE_QUESTIONS) == 4:
                        break
            except (json.JSONDecodeError, KeyError):
                pass


# ---------------------------------------------------------------------------
# Security-headers middleware
# ---------------------------------------------------------------------------

class _SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="CyberLibrarian", docs_url=None, redoc_url=None)
app.add_middleware(_SecurityHeaders)
app.add_middleware(RateLimitMiddleware, protected_path="/api/ask")

# Static assets: /static/style.css, /static/app.js, etc.
_WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse(str(_WEB_DIR / "index.html"), media_type="text/html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    return {
        "project": "CyberLibrarian",
        "tagline": "AI-powered cybersecurity knowledge assistant",
        "sources": ["owasp", "nist", "mitre", "cisa"],
        "mock_mode": Config.USE_MOCK,
        "test_round": os.getenv("TEST_ROUND", ""),
        "example_questions": _EXAMPLE_QUESTIONS,
        "max_question_len": int(os.getenv("MAX_QUESTION_LEN", "500")),
    }


@app.post("/api/ask")
async def ask_endpoint(request: Request):
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    filters = body.get("filters") or None
    session_id = request.headers.get("x-session-id") or new_session_id()
    try:
        resp = ask(question, filters)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Backend error: {exc}")
    log_usage(session_id, question, resp)
    return resp.model_dump()


@app.post("/api/feedback")
async def feedback_endpoint(request: Request):
    body = await request.json()
    rating = body.get("rating") or ""
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    save_feedback(
        question=(body.get("question") or "")[:500],
        answer=(body.get("answer") or "")[:500],
        rating=rating,
        comment=(body.get("comment") or "")[:500],
    )
    return {"ok": True}


@app.get("/api/admin/download/{filename}")
async def admin_download(filename: str):
    admin_mode = os.getenv("ADMIN_MODE", "false").lower() not in ("false", "0", "no")
    if not admin_mode:
        raise HTTPException(status_code=403, detail="Admin mode not enabled")
    allowed = {
        "usage_log.jsonl": USAGE_LOG,
        "feedback.jsonl": Config.FEEDBACK_JSONL,
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="File not found")
    path = allowed[filename]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return FileResponse(str(path), media_type="application/jsonl", filename=filename)
