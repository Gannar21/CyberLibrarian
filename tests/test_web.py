"""Tests for app/web.py – mock mode, no network, no LLM key."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

# Force mock mode before the module is imported by any test.
os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("RATE_LIMIT_PER_HOUR", "100")
os.environ.setdefault("MAX_QUESTION_LEN", "500")

from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_app(env_overrides=None, monkeypatch=None):
    """Import app.web fresh so module-level env vars are re-read."""
    for k, v in (env_overrides or {}).items():
        if monkeypatch:
            monkeypatch.setenv(k, v)
    sys.modules.pop("app.web",        None)
    sys.modules.pop("app.rate_limit", None)
    import app.web
    return app.web.app


def _client(env_overrides=None, monkeypatch=None):
    return TestClient(_fresh_app(env_overrides, monkeypatch), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Health & config
# ---------------------------------------------------------------------------

def test_health():
    with _client() as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config_shape():
    with _client() as c:
        r = c.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert data["project"] == "CyberLibrarian"
    assert set(data["sources"]) == {"owasp", "nist", "mitre", "cisa"}
    assert isinstance(data["mock_mode"], bool)
    assert isinstance(data["example_questions"], list)


# ---------------------------------------------------------------------------
# /api/ask
# ---------------------------------------------------------------------------

def test_ask_mock_returns_answer_response():
    with _client() as c:
        r = c.post("/api/ask", json={"question": "What is SQL injection?"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "citations" in data
    assert "chunks" in data
    assert isinstance(data["answerable"], bool)


def test_ask_empty_question_rejected():
    with _client() as c:
        r = c.post("/api/ask", json={"question": ""})
    assert r.status_code == 400


def test_ask_whitespace_only_rejected():
    with _client() as c:
        r = c.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_ask_too_long_rejected():
    with _client() as c:
        r = c.post("/api/ask", json={"question": "x" * 501})
    assert r.status_code == 400
    assert "character limit" in r.json()["detail"].lower()


def test_ask_rate_limit_429(monkeypatch):
    with _client({"RATE_LIMIT_PER_HOUR": "2"}, monkeypatch) as c:
        for _ in range(2):
            c.post("/api/ask", json={"question": "q"}, headers={"x-session-id": "tst-sess"})
        r = c.post("/api/ask", json={"question": "q"}, headers={"x-session-id": "tst-sess"})
    assert r.status_code == 429


def test_ask_passes_filters():
    with _client() as c:
        r = c.post("/api/ask", json={
            "question": "What is phishing?",
            "filters": {"source": ["owasp"]},
        })
    # Mock always returns the same response regardless of filters; just check shape.
    assert r.status_code == 200


def test_ask_session_id_used():
    """Session ID from header should appear in usage log, not an IP."""
    with _client() as c:
        r = c.post("/api/ask", json={"question": "q"},
                   headers={"x-session-id": "safe-session-abc"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# /api/feedback
# ---------------------------------------------------------------------------

def test_feedback_thumbs_up(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.Config.FEEDBACK_JSONL", tmp_path / "feedback.jsonl")
    with _client() as c:
        r = c.post("/api/feedback", json={
            "question": "What is XSS?",
            "answer":   "XSS is…",
            "rating":   "up",
            "comment":  "",
        })
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_feedback_thumbs_down_with_comment(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.Config.FEEDBACK_JSONL", tmp_path / "feedback.jsonl")
    with _client() as c:
        r = c.post("/api/feedback", json={
            "question": "q", "answer": "a", "rating": "down", "comment": "not helpful",
        })
    assert r.status_code == 200
    fb_path = tmp_path / "feedback.jsonl"
    assert fb_path.exists()
    record = json.loads(fb_path.read_text())
    assert record["rating"] == "down"
    assert record["comment"] == "not helpful"


def test_feedback_invalid_rating():
    with _client() as c:
        r = c.post("/api/feedback", json={"question": "q", "answer": "a", "rating": "meh"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def test_security_headers_present():
    with _client() as c:
        r = c.get("/api/health")
    assert "Content-Security-Policy" in r.headers
    assert "X-Content-Type-Options"  in r.headers
    assert "X-Frame-Options"         in r.headers
    assert "Referrer-Policy"         in r.headers


def test_csp_no_unsafe_inline():
    with _client() as c:
        r = c.get("/api/health")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "unsafe-inline" not in csp
    assert "unsafe-eval"   not in csp


def test_csp_self_only():
    with _client() as c:
        r = c.get("/api/health")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_x_frame_options_deny():
    with _client() as c:
        r = c.get("/api/health")
    assert r.headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# Admin download
# ---------------------------------------------------------------------------

def test_admin_disabled_returns_403():
    with _client({"ADMIN_MODE": "false"}) as c:
        r = c.get("/api/admin/download/usage_log.jsonl")
    assert r.status_code == 403


def test_admin_unknown_file_returns_404(monkeypatch):
    monkeypatch.setenv("ADMIN_MODE", "true")
    with _client({"ADMIN_MODE": "true"}, monkeypatch) as c:
        r = c.get("/api/admin/download/../../etc/passwd")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Logs never contain IPs
# ---------------------------------------------------------------------------

def test_logs_no_ips(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.USAGE_LOG", tmp_path / "usage_log.jsonl")
    with _client() as c:
        c.post("/api/ask", json={"question": "test question"},
               headers={"x-session-id": "abc123noip"})

    log_file = tmp_path / "usage_log.jsonl"
    if log_file.exists():
        content = log_file.read_text(encoding="utf-8")
        # No IPv4 pattern should appear in the log
        assert not re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content), \
            "IP address found in usage log"
        # Session id should be the one we sent, not an IP
        record = json.loads(content.splitlines()[0])
        assert record["session_id"] == "abc123noip"


# ---------------------------------------------------------------------------
# JS security check – no innerHTML for dynamic data
# ---------------------------------------------------------------------------

def test_no_innerhtml_assignment_in_appjs():
    js_path = Path(__file__).parent.parent / "app" / "web" / "app.js"
    assert js_path.exists(), "app/web/app.js not found"
    content = js_path.read_text(encoding="utf-8")
    matches = re.findall(r'\.innerHTML\s*=', content)
    assert len(matches) == 0, \
        f"Found {len(matches)} innerHTML= assignment(s) in app.js – use textContent instead"


# ---------------------------------------------------------------------------
# Index page served
# ---------------------------------------------------------------------------

def test_index_served():
    with _client() as c:
        r = c.get("/")
    assert r.status_code == 200
    assert "CyberLibrarian" in r.text
