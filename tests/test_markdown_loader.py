"""Unit tests for src.ingest.markdown_loader using in-memory fixtures."""
import tempfile
from pathlib import Path

import pytest

from src.ingest.markdown_loader import (
    _extract_title,
    _stem_to_slug,
    _title_to_section,
    load_owasp_documents,
)

SAMPLE_MD = """\
# SQL Injection Prevention Cheat Sheet

## Introduction

SQL injection is a web security vulnerability.

## Defense 1: Prepared Statements

Use parameterized queries to separate code from data.

## Defense 2: Stored Procedures

Stored procedures can also prevent SQL injection.
"""


@pytest.fixture
def owasp_dir(tmp_path: Path) -> Path:
    """Create a tiny data/raw/owasp/ directory with one fixture cheat sheet."""
    d = tmp_path / "owasp"
    d.mkdir()
    (d / "SQL_Injection_Prevention_Cheat_Sheet.md").write_text(SAMPLE_MD, encoding="utf-8")
    (d / "XSS_Prevention_Cheat_Sheet.md").write_text(
        "# Cross Site Scripting Prevention Cheat Sheet\n\nEscape output.\n",
        encoding="utf-8",
    )
    return tmp_path  # raw_dir is the parent


def test_stem_to_slug() -> None:
    assert _stem_to_slug("SQL_Injection_Prevention_Cheat_Sheet") == "sql-injection-prevention-cheat-sheet"
    assert _stem_to_slug("XSS_Prevention_Cheat_Sheet") == "xss-prevention-cheat-sheet"


def test_extract_title() -> None:
    assert _extract_title(SAMPLE_MD) == "SQL Injection Prevention Cheat Sheet"


def test_extract_title_no_h1() -> None:
    assert _extract_title("## Only H2 here\n\nSome text.") == ""


def test_title_to_section() -> None:
    assert _title_to_section("SQL Injection Prevention Cheat Sheet") == "SQL Injection Prevention"
    assert _title_to_section("XSS Prevention Cheat Sheet") == "XSS Prevention"
    # No "Cheat Sheet" suffix – return as-is
    assert _title_to_section("Authentication") == "Authentication"


def test_load_owasp_documents(owasp_dir: Path) -> None:
    docs = load_owasp_documents(owasp_dir)
    assert len(docs) == 2

    sql_doc = next(d for d in docs if "sql" in d.doc_id)
    assert sql_doc.doc_id == "owasp-sql-injection-prevention-cheat-sheet"
    assert sql_doc.source == "owasp"
    assert sql_doc.title == "SQL Injection Prevention Cheat Sheet"
    assert sql_doc.section == "SQL Injection Prevention"
    assert "cheatsheetseries.owasp.org" in sql_doc.url
    assert sql_doc.date is None
    assert "parameterized queries" in sql_doc.text


def test_load_owasp_documents_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_owasp_documents(tmp_path)  # no owasp/ subdirectory
