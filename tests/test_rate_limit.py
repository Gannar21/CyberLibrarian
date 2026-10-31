"""Tests for app/rate_limit.py – no network, no API key."""
from __future__ import annotations

import importlib
import sys
import time

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(env_overrides: dict[str, str] | None = None, monkeypatch=None):
    """Build a minimal Starlette app with RateLimitMiddleware.

    Re-imports app.rate_limit so per-test env vars take effect.
    env_overrides are applied via monkeypatch before the import.
    """
    for key, val in (env_overrides or {}).items():
        if monkeypatch:
            monkeypatch.setenv(key, val)

    # Force fresh module so module-level constants re-read env.
    sys.modules.pop("app.rate_limit", None)
    from app.rate_limit import RateLimitMiddleware  # noqa: PLC0415

    async def ask(request: Request):
        body = await request.json()
        return JSONResponse({"answer": "ok", "question": body.get("question", "")})

    app = Starlette(routes=[Route("/ask", ask, methods=["POST"])])
    app.add_middleware(RateLimitMiddleware)
    return app


def _post(client: TestClient, question: str, session: str | None = None,
          forwarded_for: str | None = None):
    headers = {}
    if session:
        headers["x-session-id"] = session
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for
    return client.post("/ask", json={"question": question}, headers=headers)


# ---------------------------------------------------------------------------
# Length cap
# ---------------------------------------------------------------------------

def test_question_within_limit_passes(monkeypatch):
    app = _make_app({"MAX_QUESTION_LEN": "20", "RATE_LIMIT_PER_HOUR": "100"}, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = _post(client, "short question ok?", session="s1")
    assert r.status_code == 200


def test_question_too_long_rejected(monkeypatch):
    app = _make_app({"MAX_QUESTION_LEN": "10", "RATE_LIMIT_PER_HOUR": "100"}, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = _post(client, "this is too long for the limit", session="s1")
    assert r.status_code == 400
    assert "character limit" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Per-session rate limit
# ---------------------------------------------------------------------------

def test_session_rate_limit_enforced(monkeypatch):
    app = _make_app({"RATE_LIMIT_PER_HOUR": "3", "MAX_QUESTION_LEN": "500"}, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(3):
            r = _post(client, "ok?", session="sess-abc")
            assert r.status_code == 200
        r = _post(client, "ok?", session="sess-abc")
    assert r.status_code == 429


def test_different_sessions_independent(monkeypatch):
    app = _make_app({"RATE_LIMIT_PER_HOUR": "2", "MAX_QUESTION_LEN": "500"}, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(2):
            _post(client, "q", session="alice")
        # alice is now blocked; bob should still pass
        r = _post(client, "q", session="bob")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Loopback bypass – unit test _ip() directly with a mock request
# ---------------------------------------------------------------------------

def test_loopback_ip_not_rate_limited(monkeypatch):
    """127.0.0.1 is in _LOOPBACK; the IP check must be skipped for it."""
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "2")
    monkeypatch.setenv("MAX_QUESTION_LEN", "500")
    monkeypatch.setenv("TRUST_PROXY", "false")
    sys.modules.pop("app.rate_limit", None)
    import app.rate_limit as rl

    # Verify the constant is populated correctly.
    assert "127.0.0.1" in rl._LOOPBACK
    assert "::1" in rl._LOOPBACK

    # _ip() with a loopback client and TRUST_PROXY=false returns the raw host.
    from unittest.mock import MagicMock
    mock_req = MagicMock()
    mock_req.client.host = "127.0.0.1"
    mock_req.headers.get.return_value = ""
    ip = rl._ip(mock_req)
    assert ip in rl._LOOPBACK


# ---------------------------------------------------------------------------
# TRUST_PROXY behaviour
# ---------------------------------------------------------------------------

def test_trust_proxy_false_groups_clients_by_peer_address(monkeypatch):
    """When TRUST_PROXY=false, different X-Forwarded-For values share one limit bucket."""
    app = _make_app(
        {"RATE_LIMIT_PER_HOUR": "2", "MAX_QUESTION_LEN": "500", "TRUST_PROXY": "false"},
        monkeypatch,
    )
    # TestClient peers as "testclient" – not a loopback, so IP limit applies.
    # Both requests use a different X-Forwarded-For, yet they exhaust the same
    # "testclient" bucket (because the header is ignored).
    with TestClient(app, raise_server_exceptions=False) as client:
        r1 = _post(client, "q", forwarded_for="1.2.3.4")
        r2 = _post(client, "q", forwarded_for="5.6.7.8")
        r3 = _post(client, "q", forwarded_for="9.10.11.12")   # same bucket → blocked
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_trust_proxy_true_uses_x_forwarded_for(monkeypatch):
    """When TRUST_PROXY=true, the first X-Forwarded-For address is the identity."""
    app = _make_app(
        {"RATE_LIMIT_PER_HOUR": "2", "MAX_QUESTION_LEN": "500", "TRUST_PROXY": "true"},
        monkeypatch,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(2):
            r = _post(client, "q", forwarded_for="5.6.7.8")
            assert r.status_code == 200
        # Third request from same proxy IP should be blocked.
        r = _post(client, "q", forwarded_for="5.6.7.8")
    assert r.status_code == 429


def test_trust_proxy_true_loopback_via_forwarded_still_exempt(monkeypatch):
    """127.0.0.1 in X-Forwarded-For is still a loopback → exempt from IP limit."""
    app = _make_app(
        {"RATE_LIMIT_PER_HOUR": "2", "MAX_QUESTION_LEN": "500", "TRUST_PROXY": "true"},
        monkeypatch,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(5):
            r = _post(client, "q", forwarded_for="127.0.0.1")
    assert r.status_code == 200
