"""
Load NIST PDF files from data/raw/nist/.

One Document per page (pages with < 80 usable characters are skipped).

doc_id  = "nist-<pub-slug>-p<page-number>"
          e.g. "nist-sp800-61r3-p12"

slug    = publication identifier derived from the filename:
          NIST.SP.800-61r3  → sp800-61r3
          NIST.CSWP.29      → cswp29
          NIST.SP.800-63-3  → sp800-63-3
          NIST.SP.800-63b   → sp800-63b

section = "Page N"   (page number is the most reliable, always-detectable unit;
          section headings would require layout analysis beyond plain-text pypdf)

url     = the public NIST URL where the PDF is hosted (hardcoded per filename)

date    = known publication date per filename (ISO format)
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pypdf

from src.common.schemas import Document

MIN_PAGE_CHARS = 80   # pages with fewer usable chars are skipped (cover, blank pages)

# Known metadata per PDF filename stem → (slug, url, date)
_PDF_META: dict[str, tuple[str, str, str]] = {
    "NIST.SP.800-61r3": (
        "sp800-61r3",
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        "2024-08-23",
    ),
    "NIST.CSWP.29": (
        "cswp29",
        "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "2024-02-26",
    ),
    "NIST.SP.800-63-3": (
        "sp800-63-3",
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63-3.pdf",
        "2017-06-22",
    ),
    "NIST.SP.800-63b": (
        "sp800-63b",
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b.pdf",
        "2017-06-22",
    ),
}


def _detect_boilerplate(pages_text: list[str]) -> set[str]:
    """Return lines that appear on ≥40 % of pages and are short (≤70 chars).

    These are almost certainly headers, footers, or page-number lines.
    """
    line_counts: Counter[str] = Counter()
    for page in pages_text:
        for line in set(page.splitlines()):
            stripped = line.strip()
            if stripped:
                line_counts[stripped] += 1

    threshold = max(2, len(pages_text) * 0.4)
    return {
        line
        for line, count in line_counts.items()
        if count >= threshold and len(line) <= 70
    }


def _clean_page(text: str, boilerplate: set[str]) -> str:
    """Remove boilerplate lines and collapse excessive blank lines."""
    lines = []
    for line in text.splitlines():
        if line.strip() not in boilerplate:
            lines.append(line)
    cleaned = "\n".join(lines)
    # Collapse 3+ blank lines into 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def load_pdf_documents(pdf_path: Path) -> list[Document]:
    """Extract text from *pdf_path* and return one Document per page.

    Skips cover/blank pages with fewer than MIN_PAGE_CHARS usable characters.
    """
    stem = pdf_path.stem  # e.g. "NIST.SP.800-61r3"
    if stem not in _PDF_META:
        raise ValueError(
            f"Unrecognised NIST PDF: {pdf_path.name}. "
            f"Add an entry to _PDF_META in pdf_loader.py."
        )

    slug, url, date = _PDF_META[stem]
    # Build a human-readable title from the slug
    title = stem.replace(".", " ").replace("-", " rev ")

    reader = pypdf.PdfReader(str(pdf_path))
    raw_pages = []
    for page in reader.pages:
        raw_pages.append(page.extract_text() or "")

    boilerplate = _detect_boilerplate(raw_pages)

    docs: list[Document] = []
    for page_idx, raw_text in enumerate(raw_pages):
        page_num = page_idx + 1
        clean = _clean_page(raw_text, boilerplate)
        if len(clean) < MIN_PAGE_CHARS:
            continue  # skip cover pages, blank pages, pure-image pages

        docs.append(
            Document(
                doc_id=f"nist-{slug}-p{page_num}",
                title=title,
                source="nist",
                section=f"Page {page_num}",
                date=date,
                url=url,
                text=clean,
            )
        )

    return docs


def load_nist_documents(raw_dir: Path) -> list[Document]:
    """Load all recognised NIST PDFs from *raw_dir*/nist/ and return Documents."""
    nist_dir = raw_dir / "nist"
    if not nist_dir.exists():
        raise FileNotFoundError(
            f"NIST source directory not found: {nist_dir}\n"
            "Run  python data/download_corpus.py  first."
        )

    docs: list[Document] = []
    for stem in _PDF_META:
        pdf_path = nist_dir / f"{stem}.pdf"
        if not pdf_path.exists():
            print(f"  pdf_loader: {pdf_path.name} not found, skipping")
            continue
        page_docs = load_pdf_documents(pdf_path)
        docs.extend(page_docs)

    return docs
