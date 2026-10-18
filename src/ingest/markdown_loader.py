"""
Load OWASP Cheat Sheet Series Markdown files from data/raw/owasp/.

One Document per .md file.

doc_id  = "owasp-<file-slug>"
          slug = filename stem lowercased with underscores replaced by hyphens
          e.g. "SQL_Injection_Prevention_Cheat_Sheet.md" → "owasp-sql-injection-prevention-cheat-sheet"

section = the title with any trailing " Cheat Sheet" suffix stripped, giving the
          topic name alone (e.g. "SQL Injection Prevention").  This makes the
          section field useful for filtering by topic without redundancy.

url     = https://cheatsheetseries.owasp.org/cheatsheets/<Stem>.html
          (the published URL mirrors the filename exactly)

date    = None; OWASP cheat sheets do not embed a consistent publication date.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.common.schemas import Document


def _stem_to_slug(stem: str) -> str:
    """Convert a filename stem to a URL-safe slug.

    "SQL_Injection_Prevention_Cheat_Sheet" → "sql-injection-prevention-cheat-sheet"
    """
    return stem.lower().replace("_", "-").replace(" ", "-")


def _extract_title(text: str) -> str:
    """Return the first H1 heading found in the Markdown text, or the stem if none."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _title_to_section(title: str) -> str:
    """Strip trailing 'Cheat Sheet' (case-insensitive) from a title."""
    return re.sub(r"\s*cheat\s+sheet\s*$", "", title, flags=re.IGNORECASE).strip()


def load_owasp_documents(raw_dir: Path) -> list[Document]:
    """Read all *.md files in *raw_dir* and return one Document each."""
    owasp_dir = raw_dir / "owasp"
    if not owasp_dir.exists():
        raise FileNotFoundError(
            f"OWASP source directory not found: {owasp_dir}\n"
            "Run  python data/download_corpus.py  first."
        )

    docs: list[Document] = []
    for md_file in sorted(owasp_dir.glob("*.md")):
        stem = md_file.stem
        slug = _stem_to_slug(stem)
        text = md_file.read_text(encoding="utf-8", errors="replace")

        title = _extract_title(text) or stem.replace("_", " ")
        section = _title_to_section(title)

        # Published URL follows the exact filename stem
        url = f"https://cheatsheetseries.owasp.org/cheatsheets/{stem}.html"

        docs.append(
            Document(
                doc_id=f"owasp-{slug}",
                title=title,
                source="owasp",
                section=section,
                date=None,
                url=url,
                text=text,
            )
        )

    return docs
