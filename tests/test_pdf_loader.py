"""Unit tests for src.ingest.pdf_loader using lightweight mocks."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingest.pdf_loader import (
    _clean_page,
    _detect_boilerplate,
    load_pdf_documents,
)


def test_detect_boilerplate_finds_repeated_lines() -> None:
    pages = [
        "NIST SP 800-61r3\nIntroduction\nSome content here.",
        "NIST SP 800-61r3\nIncident Response\nMore content.",
        "NIST SP 800-61r3\nContainment\nEven more content.",
    ]
    boilerplate = _detect_boilerplate(pages)
    assert "NIST SP 800-61r3" in boilerplate
    assert "Introduction" not in boilerplate  # appears only once


def test_clean_page_removes_boilerplate() -> None:
    boilerplate = {"NIST SP 800-61r3", "Page 1"}
    text = "NIST SP 800-61r3\nPage 1\nActual content here.\nMore content."
    result = _clean_page(text, boilerplate)
    assert "NIST SP 800-61r3" not in result
    assert "Page 1" not in result
    assert "Actual content here." in result


def test_clean_page_collapses_blank_lines() -> None:
    text = "Line one.\n\n\n\nLine two."
    result = _clean_page(text, set())
    assert "\n\n\n" not in result


def _make_mock_reader(pages_text: list[str]) -> MagicMock:
    """Build a minimal mock of pypdf.PdfReader with the given page texts."""
    reader = MagicMock()
    mock_pages = []
    for text in pages_text:
        page = MagicMock()
        page.extract_text.return_value = text
        mock_pages.append(page)
    reader.pages = mock_pages
    return reader


@patch("src.ingest.pdf_loader.pypdf.PdfReader")
def test_load_pdf_documents_sp800_61r3(mock_reader_cls: MagicMock, tmp_path: Path) -> None:
    pages = [
        "NIST SP 800-61r3\nA short cover page.",      # skipped: too short
        "NIST SP 800-61r3\n" + "This page has more than eighty characters of meaningful content here. " * 3,
        "NIST SP 800-61r3\n" + "Another page with enough content to pass the minimum threshold check. " * 3,
    ]
    mock_reader_cls.return_value = _make_mock_reader(pages)

    pdf_path = tmp_path / "NIST.SP.800-61r3.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")  # content doesn't matter; PdfReader is mocked

    docs = load_pdf_documents(pdf_path)

    # Page 1 is skipped (too short); pages 2 and 3 are included
    assert len(docs) == 2
    assert docs[0].doc_id == "nist-sp800-61r3-p2"
    assert docs[1].doc_id == "nist-sp800-61r3-p3"
    assert docs[0].source == "nist"
    assert docs[0].date == "2024-08-23"
    assert "nist.gov" in docs[0].url
    assert docs[0].section == "Page 2"


@patch("src.ingest.pdf_loader.pypdf.PdfReader")
def test_load_pdf_documents_unknown_stem(mock_reader_cls: MagicMock, tmp_path: Path) -> None:
    pdf_path = tmp_path / "NIST.SP.800-999.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    with pytest.raises(ValueError, match="Unrecognised NIST PDF"):
        load_pdf_documents(pdf_path)
