#!/usr/bin/env python3
"""
Download raw corpus files for CyberLibrarian into data/raw/.

Sources
-------
owasp  OWASP Cheat Sheet Series (Markdown, GitHub)        CC BY-SA 4.0
mitre  MITRE ATT&CK Enterprise (STIX JSON, GitHub)        Apache 2.0
nist   NIST SP 800-61r3, CSF 2.0, SP 800-63-3, SP 800-63B  Public domain

Usage
-----
    python data/download_corpus.py

Idempotent: skips files that already exist.
On failure, prints manual download instructions and continues.
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path
from typing import NamedTuple

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

DELAY = 0.5          # seconds between HTTP requests (rate-limit courtesy)
TIMEOUT_SMALL = 60   # seconds for small requests
TIMEOUT_LARGE = 300  # seconds for large downloads (MITRE STIX file)

LICENSES = {
    "owasp": "CC BY-SA 4.0  https://creativecommons.org/licenses/by-sa/4.0/",
    "mitre": "Apache 2.0    https://github.com/mitre-attack/attack-stix-data/blob/master/LICENSE",
    "nist":  "Public domain / U.S. Government work  https://www.nist.gov/open/license",
}


class NistEntry(NamedTuple):
    url: str
    filename: str
    title: str


NIST_PDFS: list[NistEntry] = [
    NistEntry(
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        "NIST.SP.800-61r3.pdf",
        "SP 800-61 Rev 3: Computer Security Incident Handling Guide",
    ),
    NistEntry(
        "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "NIST.CSWP.29.pdf",
        "NIST Cybersecurity Framework 2.0",
    ),
    NistEntry(
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63-3.pdf",
        "NIST.SP.800-63-3.pdf",
        "SP 800-63-3: Digital Identity Guidelines",
    ),
    NistEntry(
        "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b.pdf",
        "NIST.SP.800-63b.pdf",
        "SP 800-63B: Authentication and Lifecycle Management",
    ),
]


# ---------------------------------------------------------------------------
# OWASP
# ---------------------------------------------------------------------------

def download_owasp(raw_dir: Path) -> tuple[int, int]:
    """Download OWASP Cheat Sheet Series via GitHub zipball.

    Returns (new_files_written, total_bytes_on_disk).
    """
    out = raw_dir / "owasp"
    out.mkdir(parents=True, exist_ok=True)

    existing = list(out.glob("*.md"))
    if len(existing) > 50:
        size = sum(f.stat().st_size for f in existing)
        print(f"  owasp: {len(existing)} files already present, skipping download")
        return 0, size

    url = "https://codeload.github.com/OWASP/CheatSheetSeries/zip/refs/heads/master"
    print(f"  owasp: downloading zipball from GitHub (this may take a moment)...")
    r = requests.get(url, timeout=TIMEOUT_LARGE)
    r.raise_for_status()

    downloaded = 0
    total = 0
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        entries = [n for n in zf.namelist() if "/cheatsheets/" in n and n.endswith(".md")]
        for entry in entries:
            name = Path(entry).name
            dest = out / name
            if dest.exists():
                total += dest.stat().st_size
                continue
            data = zf.read(entry)
            dest.write_bytes(data)
            total += len(data)
            downloaded += 1

    count = len(list(out.glob("*.md")))
    print(f"  owasp: {downloaded} new files written ({count} total Markdown files)")
    return downloaded, total


# ---------------------------------------------------------------------------
# MITRE ATT&CK
# ---------------------------------------------------------------------------

def _find_latest_attack_file() -> str:
    """Return the download URL of the latest enterprise-attack-*.json via GitHub API."""
    api = "https://api.github.com/repos/mitre-attack/attack-stix-data/contents/enterprise-attack"
    r = requests.get(api, timeout=TIMEOUT_SMALL, headers={"Accept": "application/vnd.github.v3+json"})
    r.raise_for_status()
    items = r.json()
    json_files = [f for f in items if isinstance(f, dict) and f.get("name", "").endswith(".json")]
    if not json_files:
        raise ValueError("No JSON files found in mitre-attack/attack-stix-data/enterprise-attack")
    # Lexicographic sort gives the highest version last (e.g. enterprise-attack-16.1 > enterprise-attack-16.0)
    latest = sorted(json_files, key=lambda f: f["name"])[-1]
    print(f"  mitre: latest file is {latest['name']}")
    return latest["download_url"]


def download_mitre(raw_dir: Path) -> tuple[int, int]:
    """Download MITRE ATT&CK Enterprise STIX JSON (latest version).

    Saves as enterprise-attack.json so loaders always find the same path.
    Returns (new_files_written, total_bytes_on_disk).
    """
    out = raw_dir / "mitre"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "enterprise-attack.json"

    if dest.exists():
        size = dest.stat().st_size
        print(f"  mitre: enterprise-attack.json already present ({size / 1_048_576:.1f} MB), skipping")
        return 0, size

    download_url = _find_latest_attack_file()
    time.sleep(DELAY)
    print(f"  mitre: streaming download (file can be 60-100 MB)...")
    r = requests.get(download_url, timeout=TIMEOUT_LARGE, stream=True)
    r.raise_for_status()

    total = 0
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
            total += len(chunk)

    print(f"  mitre: wrote enterprise-attack.json ({total / 1_048_576:.1f} MB)")
    return 1, total


# ---------------------------------------------------------------------------
# NIST
# ---------------------------------------------------------------------------

def download_nist(raw_dir: Path) -> tuple[int, int]:
    """Download NIST PDFs from nvlpubs.nist.gov.

    Returns (new_files_written, total_bytes_on_disk).
    """
    out = raw_dir / "nist"
    out.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    total = 0
    failed: list[NistEntry] = []

    for entry in NIST_PDFS:
        dest = out / entry.filename
        if dest.exists():
            total += dest.stat().st_size
            print(f"  nist: {entry.filename} already present, skipping")
            continue

        print(f"  nist: downloading {entry.title} ...")
        time.sleep(DELAY)
        try:
            r = requests.get(
                entry.url,
                timeout=TIMEOUT_SMALL,
                headers={"User-Agent": "CyberLibrarian-academic-research/1.0"},
            )
            r.raise_for_status()
            dest.write_bytes(r.content)
            total += len(r.content)
            downloaded += 1
            print(f"         saved {entry.filename} ({len(r.content) / 1024:.0f} KB)")
        except Exception as exc:
            print(f"         FAILED: {exc}")
            failed.append(entry)

    if failed:
        print("\n  !! The following NIST PDFs could not be downloaded automatically.")
        print("     Please download them manually:")
        for e in failed:
            print(f"\n     Title : {e.title}")
            print(f"     URL   : {e.url}")
            print(f"     Target: data/raw/nist/{e.filename}")

    return downloaded, total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sources = [
        ("owasp", download_owasp),
        ("mitre", download_mitre),
        ("nist",  download_nist),
    ]

    results: dict[str, tuple[int, int]] = {}

    for source, fn in sources:
        print(f"\n[{source.upper()}]")
        try:
            new_files, total_bytes = fn(RAW_DIR)
            results[source] = (new_files, total_bytes)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results[source] = (0, 0)
            _print_manual_instructions(source)

    print("\n" + "=" * 64)
    print("DOWNLOAD SUMMARY")
    print("=" * 64)
    grand_total = 0
    for source, (new_files, total_bytes) in results.items():
        grand_total += total_bytes
        mb = total_bytes / 1_048_576
        print(f"  {source:8s}  {new_files:3d} new   {mb:8.1f} MB on disk")
        print(f"            License: {LICENSES[source]}")
    print(f"\n  Grand total on disk: {grand_total / 1_048_576:.1f} MB")
    print("=" * 64)


def _print_manual_instructions(source: str) -> None:
    print(f"\n  Manual download instructions for {source}:")
    if source == "owasp":
        print("    1. Visit https://github.com/OWASP/CheatSheetSeries")
        print("    2. Code → Download ZIP")
        print("    3. Extract cheatsheets/*.md to data/raw/owasp/")
    elif source == "mitre":
        print("    1. Visit https://github.com/mitre-attack/attack-stix-data/tree/master/enterprise-attack")
        print("    2. Download the latest enterprise-attack-*.json file")
        print("    3. Rename it to enterprise-attack.json")
        print("    4. Place it at data/raw/mitre/enterprise-attack.json")
    elif source == "nist":
        for e in NIST_PDFS:
            print(f"\n     Title : {e.title}")
            print(f"     URL   : {e.url}")
            print(f"     Target: data/raw/nist/{e.filename}")


if __name__ == "__main__":
    main()
